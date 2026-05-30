import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controllers.recommend_controller import RecommendController
from services.database_service import DatabaseService
from services.llm_service import LLMService


def _add_image(db: DatabaseService, index: int) -> int:
    return db.add_image(
        file_path=f"/tmp/img_{index}.png",
        name=f"img_{index}.png",
        file_type="png",
        file_size=1,
        width=10,
        height=10,
        thumbnail_path="",
    )


def test_batch_tagging_assigns_tag_to_all_selected_images(tmp_path):
    db = DatabaseService(str(tmp_path / "test.db"))
    image_ids = [_add_image(db, i) for i in range(3)]
    selected_tag_name = "开心"
    # 模拟 TagPanel 中的批量循环逻辑
    for image_id in image_ids:
        db.add_tag_to_image(image_id, selected_tag_name)

    for image_id in image_ids:
        tag_names = [row[1] for row in db.get_image_tags(image_id)]
        assert "开心" in tag_names


def test_llm_recommend_filters_unknown_tags():
    class FakeDB:
        def get_all_tags(self):
            return [(1, "开心", "#fff"), (2, "哈哈", "#fff"), (3, "生气", "#fff")]

        def get_images_by_tags_union(self, tag_names):
            assert tag_names == ["开心", "哈哈"]
            return [
                {
                    "id": 1,
                    "name": "a.png",
                    "file_path": "/tmp/a.png",
                    "file_type": "png",
                    "file_size": 1,
                    "width": 10,
                    "height": 10,
                    "thumbnail_path": "",
                }
            ]

    class FakeConfig:
        def get_llm_config(self):
            return {
                "enabled": True,
                "api_key": "k",
                "base_url": "https://example.com/v1",
                "model": "m",
            }

    class FakeLLM:
        def __init__(self, **kwargs):
            pass

        def recommend_tags(self, context, all_tags, top_k=3):
            return ["开心", "哈哈"][:top_k]

    controller = RecommendController(FakeDB(), config_manager=FakeConfig(), llm_service_cls=FakeLLM)
    models = controller.recommend("今天真开心", top_k=3)
    assert [m.id for m in models] == [1]
    assert controller.last_recommended_tags == ["开心", "哈哈"]


def test_llm_service_filters_unknown_tags(monkeypatch):
    llm = LLMService("https://example.com/v1", "k", "m")
    monkeypatch.setattr(llm, "chat", lambda *args, **kwargs: "开心, 不存在标签, 哈哈")
    tags = llm.recommend_tags("context", ["开心", "哈哈", "生气"], top_k=3)
    assert tags == ["开心", "哈哈"]


def test_llm_recommend_requires_enabled_config():
    class FakeDB:
        def get_all_tags(self):
            return [(1, "开心", "#fff")]

    class FakeConfig:
        def get_llm_config(self):
            return {"enabled": False, "api_key": ""}

    controller = RecommendController(FakeDB(), config_manager=FakeConfig())
    with pytest.raises(RuntimeError, match="未启用 LLM 智能推荐"):
        controller.recommend("hi")
