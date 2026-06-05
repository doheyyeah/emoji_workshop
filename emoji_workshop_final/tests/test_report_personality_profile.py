import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controllers.report_controller import ReportController
from services.database_service import DatabaseService
from utils.config_manager import ConfigManager


def _build_controller(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ConfigManager._instance = None
    cfg = ConfigManager(config_name="test_report_config.json")
    cfg.set_llm_config(base_url="", api_key="", model="", enabled=False)
    db = DatabaseService(db_path=str(tmp_path / "report_test.db"))
    controller = ReportController(db, config_manager=cfg)
    return db, controller


def test_generate_report_contains_local_personality_layers(tmp_path, monkeypatch):
    db, controller = _build_controller(tmp_path, monkeypatch)
    image_id = db.add_image(
        file_path=str(tmp_path / "sample.png"),
        name="sample",
        file_type="png",
        file_size=1,
        width=1,
        height=1,
    )
    db.add_tag_to_image(image_id, "开心")
    db.record_usage(image_id)

    report = controller.generate_report("week")

    assert report["total_uses"] == 1
    assert report["dimensions"]
    assert report["evidence_tags"]
    assert report["fallback_traits"]
    assert "数据画像维度" in report["summary_text"]
    assert "关键证据" in report["summary_text"]
    assert report["radar_chart_data_uri"] == "" or report["radar_chart_data_uri"].startswith(
        "data:image/png;base64,"
    )


def test_generate_report_gracefully_falls_back_when_radar_unavailable(tmp_path, monkeypatch):
    db, controller = _build_controller(tmp_path, monkeypatch)
    image_id = db.add_image(
        file_path=str(tmp_path / "sample2.png"),
        name="sample2",
        file_type="png",
        file_size=1,
        width=1,
        height=1,
    )
    db.add_tag_to_image(image_id, "社牛")
    db.record_usage(image_id)

    monkeypatch.setattr(
        controller.personality_service,
        "_build_radar_chart_data_uri",
        lambda _: "",
    )

    report = controller.generate_report("week")
    assert report["radar_chart_data_uri"] == ""
    assert "数据画像维度" in report["summary_text"]
    assert "社交性" in report["summary_text"]
