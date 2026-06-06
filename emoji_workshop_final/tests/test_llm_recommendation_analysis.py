import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.llm_service import LLMService


def test_analyze_recommendation_parses_json_fence(monkeypatch):
    svc = LLMService("https://example.com", "k", "m")
    monkeypatch.setattr(
        svc,
        "chat",
        lambda *_, **__: '```json\n{"tags":["开心","不存在"],"keywords":["爆笑","无语"],"image_ids":[3,"7"]}\n```',
    )
    result = svc.analyze_recommendation(
        context="哈哈哈",
        image_summaries=[{"id": 3, "name": "爆笑", "tags": ["开心"]}],
        available_tags=["开心", "无语"],
        top_k=2,
    )
    assert result["tags"] == ["开心"]
    assert result["keywords"] == ["爆笑", "无语"]
    assert result["image_ids"] == [3, 7]


def test_analyze_recommendation_fallback_to_recommend_tags(monkeypatch):
    svc = LLMService("https://example.com", "k", "m")
    monkeypatch.setattr(svc, "chat", lambda *_, **__: "not json")
    monkeypatch.setattr(svc, "recommend_tags", lambda *_, **__: ["无语"])
    result = svc.analyze_recommendation(
        context="...",
        image_summaries=[],
        available_tags=["无语"],
        top_k=2,
    )
    assert result["tags"] == ["无语"]
    assert result["keywords"] == []
