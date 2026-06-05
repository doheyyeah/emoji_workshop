import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import replicate_service
from services.replicate_service import ReplicateService
from utils.config_manager import ConfigManager


class _FakeResponse:
    def __init__(self, json_data=None, content=b""):
        self._json_data = json_data
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_data


def test_generate_sticker_poll_and_download(monkeypatch, tmp_path):
    service = ReplicateService(
        base_url="https://api.replicate.com/v1",
        api_key="r8_test",
        model="fofr/sticker-maker",
    )

    poll_payloads = iter(
        [
            {"id": "pred-1", "status": "processing"},
            {
                "id": "pred-1",
                "status": "succeeded",
                "output": [
                    "https://cdn.example.com/output.png",
                    "https://cdn.example.com/output.gif",
                ],
            },
        ]
    )
    progress = []

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == "https://api.replicate.com/v1/models/fofr/sticker-maker/predictions"
        assert headers["Authorization"] == "Token r8_test"
        assert json == {"input": {"prompt": "happy cat"}}
        return _FakeResponse({"id": "pred-1", "status": "starting"})

    def fake_get(url, headers=None, timeout=None):
        if url == "https://api.replicate.com/v1/predictions/pred-1":
            return _FakeResponse(next(poll_payloads))
        if url == "https://cdn.example.com/output.gif":
            return _FakeResponse(content=b"GIF89a")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(replicate_service.requests, "post", fake_post)
    monkeypatch.setattr(replicate_service.requests, "get", fake_get)
    monkeypatch.setattr(replicate_service.time, "sleep", lambda _: None)

    output_path = tmp_path / "sticker.gif"
    saved = service.generate_sticker(
        prompt="happy cat",
        output_path=str(output_path),
        timeout=10,
        progress_callback=progress.append,
    )

    assert saved == str(output_path)
    assert output_path.read_bytes() == b"GIF89a"
    assert progress == ["正在提交任务…", "正在生成中…", "正在生成中…", "正在下载…"]


def test_replicate_config_defaults_and_setter(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    ConfigManager._instance = None

    cfg = ConfigManager(config_name="test_replicate_config.json")
    assert cfg.get_replicate_config() == {
        "base_url": "",
        "api_key": "",
        "model": "",
    }

    cfg.set_replicate_config(
        base_url="https://api.replicate.com/v1",
        api_key="r8_test",
        model="fofr/sticker-maker",
    )

    assert cfg.get_replicate_config() == {
        "base_url": "https://api.replicate.com/v1",
        "api_key": "r8_test",
        "model": "fofr/sticker-maker",
    }

    ConfigManager._instance = None
