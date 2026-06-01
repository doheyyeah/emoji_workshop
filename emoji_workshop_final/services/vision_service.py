"""视觉精排服务

使用 OpenAI 兼容的视觉模型（如智谱 GLM-4V-Flash）对候选图片进行视觉精排。

预设提供商:
- 智谱 GLM-4V-Flash (免费): base_url=https://open.bigmodel.cn/api/paas/v4, model=glm-4v-flash
- Kimi 视觉: base_url=https://api.moonshot.cn/v1, model=moonshot-v1-8k-vision-preview
"""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import requests
from PIL import Image


class VisionService:
    """OpenAI 兼容视觉模型客户端，支持图片精排"""

    # 预设提供商
    PRESETS = {
        "智谱 GLM-4V-Flash (免费)": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4v-flash",
        },
        "Kimi Vision": {
            "base_url": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k-vision-preview",
        },
    }

    MAX_IMAGES = 15  # 单次请求最多发送图片数，控制请求大小

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def rerank(
        self,
        context: str,
        candidate_images: list[dict],
        top_k: int = 3,
    ) -> list[dict]:
        """视觉精排：从候选图中选出最匹配的 top_k 张

        Args:
            context: 用户聊天上下文
            candidate_images: 候选图片列表，每项含 {"id": int, "file_path": str, ...}
            top_k: 返回最匹配的图片数量

        Returns:
            排序后的图片字典列表（长度 <= top_k）

        Raises:
            RuntimeError: API Key 为空或调用失败
        """
        if not self.api_key:
            raise RuntimeError("视觉精排未配置 API Key")

        # 截取最多 MAX_IMAGES 张候选
        candidates = candidate_images[: self.MAX_IMAGES]
        if not candidates:
            return []

        # 构造编号 → 图片映射
        indexed = {i + 1: img for i, img in enumerate(candidates)}

        # 构造多模态消息
        messages = self._build_messages(context, indexed)

        # 调用 API
        response_text = self._chat(messages)

        # 解析返回的编号列表（格式如 "3,7,1"）
        ranked_ids = self._parse_ranking(response_text, list(indexed.keys()))
        ranked_ids = ranked_ids[:top_k]

        # 按编号顺序返回对应图片
        return [indexed[i] for i in ranked_ids if i in indexed]

    def test_connection(self) -> bool:
        """发送极小测试图验证连接，返回是否成功"""
        img = Image.new("RGB", (8, 8), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这是一张测试图，请回复'OK'"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
        try:
            self._chat(messages, timeout=15)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------

    def _build_messages(self, context: str, indexed: dict[int, dict]) -> list[dict]:
        """构造多模态消息列表"""
        content = [
            {
                "type": "text",
                "text": (
                    f"用户在聊天中说：\"{context}\"\n\n"
                    f"以下是 {len(indexed)} 张候选表情包图片（按编号展示），"
                    "请选出最适合作为回复的图片编号。\n"
                    "只返回编号，格式如 \"3,1,7\"，不要解释，不要其他内容。"
                ),
            }
        ]

        for idx, img_info in indexed.items():
            data_url = self._image_to_data_url(img_info["file_path"])
            if data_url:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    }
                )
                # 在图片后附加编号说明
                content.append({"type": "text", "text": f"（上图编号：{idx}）"})

        return [{"role": "user", "content": content}]

    def _image_to_data_url(self, file_path: str) -> str | None:
        """将图片压缩到 256px 并转为 JPEG base64 data URL"""
        try:
            with Image.open(file_path) as img:
                img = img.convert("RGB")
                img.thumbnail((256, 256), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=75)
                b64 = base64.b64encode(buf.getvalue()).decode()
                return f"data:image/jpeg;base64,{b64}"
        except Exception as exc:
            print(f"[VisionService] 图片转换失败 {file_path}: {exc}")
            return None

    def _chat(self, messages: list[dict], timeout: int = 60) -> str:
        """调用视觉模型 chat 接口，返回文本内容"""
        url = f"{self.base_url}/chat/completions"
        resp = requests.post(
            url,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": 64,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _parse_ranking(text: str, valid_ids: list[int]) -> list[int]:
        """从模型回复中解析编号列表，过滤无效编号，去重保序

        支持格式：
        - "3,7,1"
        - "3, 7, 1"
        - "编号3、7、1"
        - 混有文字的情况，只提取数字
        """
        numbers = re.findall(r"\d+", text)
        seen: set[int] = set()
        result: list[int] = []
        for n in numbers:
            val = int(n)
            if val in valid_ids and val not in seen:
                seen.add(val)
                result.append(val)
        return result
