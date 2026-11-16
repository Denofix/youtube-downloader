import time

import httpx
from local_instance import running_instance
from service.media import verify


def test_real_api_worker_child_and_result_delivery(files, tmp_path):
    with running_instance() as base, httpx.Client(base_url=base, trust_env=False) as client:

        def wait(task):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                result = client.get("/api/tasks/" + task["id"]).json()
                if result["state"] not in {"queued", "running"}:
                    assert result["state"] == "completed", result
                    return result
                time.sleep(0.1)
            raise AssertionError("The real worker did not finish")

        upload = client.post(
            "/api/uploads",
            content=(files / "sample.mp4").read_bytes(),
            headers={"X-Filename": "generated-clip.mp4"},
        )
        assert upload.status_code == 202
        inspected = wait(upload.json())
        conversion = client.post(
            "/api/conversions",
            json={"asset_id": inspected["result"]["asset_id"], "parameters": {"output": "mp3"}},
        )
        assert conversion.status_code == 202
        result = wait(conversion.json())
        response = client.get("/api/assets/" + result["result"]["asset_id"] + "/file")
        assert response.status_code == 200
        path = tmp_path / "result.mp3"
        path.write_bytes(response.content)
        assert verify(path)["audio_codec"] == "mp3"
