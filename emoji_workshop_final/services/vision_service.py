"""视觉精排服务

使用 OpenAI 兼容的视觉模型（如智谱 GLM-4V-Flash）对候选图片进行视觉精排。
通过 Base URL、API Key、Model 自行配置视觉模型。
"""

from __future__ import annotations

import base64
import io
import logging
import re
from pathlib import Path

import requests
from PIL import Image


class VisionService:
    """OpenAI 兼容视觉模型客户端，支持图片精排"""

    MAX_IMAGES = 5  # 单次请求最多发送图片数，避免请求过大与兼容性问题

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
        timeout: int = 60,
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

        # 构造多 message（每条 message 仅含 1 张图）
        messages, indexed = self._build_messages(context, candidates, top_k)
        if not indexed:
            return []

        # 调用 API
        response_text = self._chat(messages, timeout=timeout)

        # 解析返回的编号列表（格式如 "3,7,1"）
        ranked_ids = self._parse_ranking(response_text, list(indexed.keys()))
        ranked_ids = ranked_ids[:top_k]

        # 按编号顺序返回对应图片
        return [indexed[i] for i in ranked_ids if i in indexed]

    def test_connection(self) -> tuple[bool, str]:
        """发送极小测试图验证连接，返回 (是否成功, 错误信息)"""
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
            return True, ""
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------

    def _build_messages(
        self, context: str, candidates: list[dict], top_k: int
    ) -> tuple[list[dict], dict[int, dict]]:
        """构造多模态消息列表（每条 message 仅一张图）"""
        messages: list[dict] = []
        indexed: dict[int, dict] = {}

        for img_info in candidates:
            file_path = img_info.get("file_path") or img_info.get("path")
            if not file_path:
                continue
            data_url = self._image_to_data_url(file_path)
            if not data_url:
                continue
            idx = len(indexed) + 1
            indexed[idx] = img_info
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"图片 {idx}:"},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            )

        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"用户在聊天中说:\"{context}\"\n\n"
                            f"上面给你 {len(messages)} 张候选表情包(编号 1 到 {len(messages)}),"
                            f"请挑出最适合作为回应的 {top_k} 个,按合适程度降序。\n\n"
                            "严格只返回编号,用英文逗号分隔,不要任何其他文字。\n例如:3,1,2"
                        ),
                    }
                ],
            }
        )
        return messages, indexed

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
            logging.debug("[VisionService] 图片转换失败 %s: %s", file_path, exc)
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
