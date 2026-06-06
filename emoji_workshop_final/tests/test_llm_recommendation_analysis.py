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
        lambda *_, **__: '```json\n{"tags":["开心","不存在"],"keywords":["爆笑","无语"],"image_ids":[3,"7","bad"]}\n```',
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


def test_select_candidate_images_filters_invalid_image_ids(monkeypatch):
    svc = LLMService("https://example.com", "k", "m")
    monkeypatch.setattr(
        svc,
        "chat",
        lambda *_, **__: (
            '{"image_ids":[2,"bad",99,2,1],"tags":["开心","不存在"],'
            '"keywords":["困","下班"],"reason":"粗筛"}'
        ),
    )
    result = svc.select_candidate_images(
        context="想下班",
        image_summaries=[
            {"id": 1, "name": "下班", "tags": ["开心"]},
            {"id": 2, "name": "困了", "tags": ["无语"]},
        ],
        available_tags=["开心", "无语"],
        candidate_count=5,
    )
    assert result["image_ids"] == [2, 1]
    assert result["tags"] == ["开心"]
    assert result["keywords"] == ["困", "下班"]


def test_select_candidate_images_sends_full_library_names(monkeypatch):
    svc = LLMService("https://example.com", "k", "m")
    captured = {}

    def fake_chat(prompt, *_, **__):
        captured["prompt"] = prompt
        return '{"image_ids":[85],"tags":[],"keywords":[],"reason":"按名称匹配"}'

    monkeypatch.setattr(svc, "chat", fake_chat)
    summaries = [
        {"id": idx, "name": f"照片{idx}", "tags": []}
        for idx in range(1, 86)
    ]
    result = svc.select_candidate_images(
        context="照片85",
        image_summaries=summaries,
        available_tags=[],
        candidate_count=5,
    )
    assert "id=85, name=照片85" in captured["prompt"]
    assert result["image_ids"] == [85]
