import json
import shutil
import sqlite3
import time
import uuid
from contextlib import contextmanager

from .config import Settings, settings
from .errors import ServiceError


class Store:
    def __init__(self, config: Settings = settings):
        self.config = config
        config.prepare()
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued', operation TEXT NOT NULL DEFAULT 'waiting',
                    payload TEXT NOT NULL, result TEXT, error TEXT,
                    progress REAL, speed REAL, eta REAL, cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL, expires_at REAL
                );
                CREATE INDEX IF NOT EXISTS tasks_queue ON tasks(state, created_at);
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, task_id TEXT, path TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL, size INTEGER NOT NULL, metadata TEXT, expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runtime (name TEXT PRIMARY KEY, updated_at REAL NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.config.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            raise ServiceError("not_found", "Task not found.", 404)
        item = dict(row)
        for field in ("payload", "result", "error"):
            item[field] = json.loads(item[field]) if item[field] else None
        return item

    def create(self, kind, title, payload):
        task_id, now = uuid.uuid4().hex, time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "SELECT count(*) FROM tasks WHERE state IN ('queued','running')"
                ).fetchone()[0]
                >= 50
            ):
                raise ServiceError(
                    "queue_full", "The queue is full. Wait for a task to finish.", 429
                )
            db.execute(
                "INSERT INTO tasks(id,kind,title,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (task_id, kind, title, json.dumps(payload), now, now),
            )
        return self.get(task_id)

    def get(self, task_id):
        with self.connect() as db:
            return self.decode(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def list(self):
        with self.connect() as db:
            return [
                self.decode(row)
                for row in db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 200")
            ]

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM tasks WHERE state='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE tasks SET state='running',operation='starting',updated_at=? WHERE id=?",
                (time.time(), row[0]),
            )
        return self.get(row[0])

    def progress(self, task_id, operation, progress=None, speed=None, eta=None):
        with self.connect() as db:
            db.execute(
                "UPDATE tasks SET operation=?,progress=?,speed=?,eta=?,updated_at=? WHERE id=? AND state='running'",
                (operation, progress, speed, eta, time.time(), task_id),
            )

    def finish(self, task_id, state, result=None, error=None):
        now = time.time()
        with self.connect() as db:
            row = db.execute(
                "SELECT cancel_requested,state FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if row is None or row[1] != "running":
                return False
            if row[0]:
                state, result, error = "cancelled", None, None
            db.execute(
                "UPDATE tasks SET state=?,operation=?,result=?,error=?,progress=NULL,speed=NULL,eta=NULL,updated_at=?,expires_at=? WHERE id=?",
                (
                    state,
                    "ready" if state == "completed" else state,
                    json.dumps(result) if result is not None else None,
                    json.dumps(error) if error else None,
                    now,
                    now + self.config.ttl,
                    task_id,
                ),
            )
        return state == "completed"

    def cancel(self, task_id):
        with self.connect() as db:
            db.execute(
                "UPDATE tasks SET cancel_requested=1,state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END,operation=CASE WHEN state='queued' THEN 'cancelled' ELSE operation END,updated_at=?,expires_at=? WHERE id=? AND state IN ('queued','running')",
                (time.time(), time.time() + self.config.ttl, task_id),
            )
        return self.get(task_id)

    def recover(self):
        with self.connect() as db:
            interrupted = [
                row[0] for row in db.execute("SELECT id FROM tasks WHERE state='running'")
            ]
            db.execute(
                "UPDATE tasks SET state=CASE WHEN cancel_requested=1 THEN 'cancelled' ELSE 'failed' END,operation='interrupted',error=?,updated_at=?,expires_at=? WHERE state='running'",
                (
                    json.dumps(
                        {
                            "code": "worker_interrupted",
                            "message": "The worker stopped. Retry this task.",
                        }
                    ),
                    time.time(),
                    time.time() + self.config.ttl,
                ),
            )
        for task_id in interrupted:
            self.discard_task_files(task_id)

    def heartbeat(self):
        with self.connect() as db:
            db.execute(
                "INSERT INTO runtime VALUES('worker',?) ON CONFLICT(name) DO UPDATE SET updated_at=excluded.updated_at",
                (time.time(),),
            )

    def worker_online(self):
        with self.connect() as db:
            row = db.execute("SELECT updated_at FROM runtime WHERE name='worker'").fetchone()
        return bool(row and time.time() - row[0] < 8)

    def add_asset(self, path, name, metadata=None, task_id=None):
        asset_id = uuid.uuid4().hex
        relative = str(path.resolve().relative_to(self.config.data_dir))
        with self.connect() as db:
            db.execute(
                "INSERT INTO assets VALUES(?,?,?,?,?,?,?)",
                (
                    asset_id,
                    task_id,
                    relative,
                    name,
                    path.stat().st_size,
                    json.dumps(metadata) if metadata else None,
                    time.time() + self.config.ttl,
                ),
            )
        return asset_id

    def asset(self, asset_id, allow_expired=False):
        with self.connect() as db:
            row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ServiceError(
                "file_expired",
                "The file is no longer available. Upload it or download it again.",
                410,
            )
        item = dict(row)
        path = (self.config.data_dir / item["path"]).resolve()
        if (
            not path.is_relative_to(self.config.data_dir / "files")
            or not path.is_file()
            or (not allow_expired and item["expires_at"] < time.time())
        ):
            raise ServiceError(
                "file_expired", "This file has expired. Upload it or run the download again.", 410
            )
        item["path"] = path
        item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else None
        return item

    def update_asset(self, asset_id, metadata):
        with self.connect() as db:
            db.execute("UPDATE assets SET metadata=? WHERE id=?", (json.dumps(metadata), asset_id))

    def discard_task_files(self, task_id):
        with self.connect() as db:
            db.execute("DELETE FROM assets WHERE task_id=?", (task_id,))
        shutil.rmtree(self.config.data_dir / "files" / task_id, ignore_errors=True)

    def cleanup(self):
        now = time.time()
        with self.connect() as db:
            expired = db.execute(
                """SELECT * FROM assets a WHERE expires_at < ? AND NOT EXISTS (
                SELECT 1 FROM tasks t WHERE t.state IN ('queued','running')
                AND (json_extract(t.payload,'$.asset_id')=a.id OR EXISTS (
                    SELECT 1 FROM json_each(t.payload,'$.asset_ids') refs WHERE refs.value=a.id
                )))""",
                (now,),
            ).fetchall()
            for row in expired:
                path = (self.config.data_dir / row["path"]).resolve()
                if path.is_relative_to(self.config.data_dir / "files"):
                    path.unlink(missing_ok=True)
                    try:
                        path.parent.rmdir()
                    except OSError:
                        pass
                db.execute("DELETE FROM assets WHERE id=?", (row["id"],))
            db.execute(
                "UPDATE tasks SET result=NULL WHERE kind='analyze' AND expires_at < ?", (now,)
            )
            registered = {
                str((self.config.data_dir / row[0]).parent)
                for row in db.execute("SELECT path FROM assets")
            }
            active = {
                row[0]
                for row in db.execute("SELECT id FROM tasks WHERE state IN ('queued','running')")
            }
        for path in (self.config.data_dir / "files").iterdir():
            if (
                path.is_dir()
                and not path.is_symlink()
                and path.name not in active
                and str(path) not in registered
                and path.stat().st_mtime < now - self.config.ttl
            ):
                shutil.rmtree(path, ignore_errors=True)
