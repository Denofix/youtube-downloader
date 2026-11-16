import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "data")).resolve()
    max_file_bytes: int = int(os.getenv("MAX_FILE_BYTES", str(512 * 1024**2)))
    max_storage_bytes: int = int(os.getenv("MAX_STORAGE_BYTES", str(5 * 1024**3)))
    job_timeout: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))
    ttl: int = int(os.getenv("RESULT_TTL_SECONDS", "86400"))
    cookie_file: str | None = os.getenv("COOKIE_FILE") or None
    use_system_ca: bool = os.getenv("YTDLP_USE_SYSTEM_CA", "0") == "1"
    allowed_hosts: tuple[str, ...] = tuple(
        os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    )

    @property
    def db_path(self):
        return self.data_dir / "service.sqlite3"

    def prepare(self):
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.data_dir / "files").mkdir(exist_ok=True, mode=0o700)


settings = Settings()
