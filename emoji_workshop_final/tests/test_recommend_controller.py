import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controllers.recommend_controller import RecommendController


class _FakeDB:
    def __init__(self, images):
        self._images = images

    def get_all_images_with_tags(self):
        return list(self._images)


class _FakeConfig:
    def __init__(self, llm_cfg=None, vision_cfg=None):
        self._llm_cfg = llm_cfg or {"enabled": False, "base_url": "", "api_key": "", "model": ""}
        self._vision_cfg = vision_cfg or {"enabled": False, "base_url": "", "api_key": "", "model": ""}

    def get_llm_config(self):
        return self._llm_cfg

    def get_vision_config(self):
        return self._vision_cfg


def _images():
    return [
        {"id": 1, "name": "谢谢老板", "file_path": "/tmp/1.png", "file_type": "png", "tags": ["感谢"]},
        {"id": 2, "name": "无语", "file_path": "/tmp/2.png", "file_type": "png", "tags": ["吐槽"]},
        {"id": 3, "name": "爆笑", "file_path": "/tmp/3.png", "file_type": "png", "tags": ["开心"]},
    ]


def test_name_match_changes_result_by_context():
    db = _FakeDB(_images())
    controller = RecommendController(db, config_manager=_FakeConfig())
    first = controller.recommend("谢谢老板", top_k=1)[0]
    second = controller.recommend("我很无语", top_k=1)[0]
    assert first.id != second.id
    assert first.name == "谢谢老板"


def test_recommend_works_with_vision_only(monkeypatch):
    class _FakeVision:
        def __init__(self, **kwargs):
            pass

        def rerank(self, context, candidate_images, top_k=3, max_images=None):
            assert max_images == len(candidate_images)
            return list(reversed(candidate_images[:top_k]))

    monkeypatch.setattr("controllers.recommend_controller.VisionService", _FakeVision)
    cfg = _FakeConfig(
        llm_cfg={"enabled": False, "base_url": "", "api_key": "", "model": ""},
        vision_cfg={"enabled": True, "base_url": "x", "api_key": "k", "model": "m"},
    )
    controller = RecommendController(_FakeDB(_images()), config_manager=cfg)
    results = controller.recommend("我很无语", top_k=2)
    assert len(results) == 2
    assert controller.last_debug_info["vision_status"] == "成功"


def test_vision_failure_falls_back_to_text(monkeypatch):
    class _BrokenVision:
        def __init__(self, **kwargs):
            pass

        def rerank(self, context, candidate_images, top_k=3, max_images=None):
            raise RuntimeError("boom")

    monkeypatch.setattr("controllers.recommend_controller.VisionService", _BrokenVision)
    cfg = _FakeConfig(
        llm_cfg={"enabled": False, "base_url": "", "api_key": "", "model": ""},
        vision_cfg={"enabled": True, "base_url": "x", "api_key": "k", "model": "m"},
    )
    controller = RecommendController(_FakeDB(_images()), config_manager=cfg)
    results = controller.recommend("爆笑", top_k=2)
    assert len(results) == 2
    assert controller.last_debug_info["vision_status"] == "失败"
    assert "降级" in controller.last_debug_info["fallback"]


def test_build_candidate_scope_prioritizes_llm_ids():
    ranked = [
        {"id": 1, "name": "a", "file_path": "/tmp/1.png", "file_type": "png"},
        {"id": 2, "name": "b", "file_path": "/tmp/2.png", "file_type": "png"},
        {"id": 3, "name": "c", "file_path": "/tmp/3.png", "file_type": "png"},
    ]
    selected, seeded = RecommendController._build_candidate_scope(
        ranked_all=ranked,
        preferred_ids=[3, 99, 3],
        candidate_count=3,
    )
    assert seeded == 1
    assert [item["id"] for item in selected] == [3, 1, 2]
