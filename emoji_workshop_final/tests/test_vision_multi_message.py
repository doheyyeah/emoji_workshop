"""P0-1 测试：视觉精排按多 message（一图一消息）发送"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.vision_service import VisionService


class _FakeResp:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "3,1,2"}}]}


def test_rerank_builds_multi_messages(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["messages"] = json["messages"]
        return _FakeResp()

    monkeypatch.setattr("services.vision_service.requests.post", fake_post)

    svc = VisionService(
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key="test-key",
        model="glm-4v-flash",
    )
    monkeypatch.setattr(svc, "_image_to_data_url", lambda _: "data:image/jpeg;base64,abc")

    candidates = [{"id": i, "file_path": f"/tmp/{i}.png"} for i in range(1, 8)]
    result = svc.rerank("我想睡觉", candidates, top_k=3)

    messages = captured["messages"]
    assert len(messages) == 6  # 5 张候选图 + 1 条问题消息
    for msg in messages[:-1]:
        image_parts = [part for part in msg["content"] if part["type"] == "image_url"]
        assert len(image_parts) == 1
    assert [item["id"] for item in result] == [3, 1, 2]
