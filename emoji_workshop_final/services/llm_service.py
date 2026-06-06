"""通用 LLM 服务 - OpenAI 兼容接口"""

import json
import logging
import re

import requests


class LLMService:
    """通用 LLM 客户端，使用 OpenAI 兼容接口"""

    MAX_CANDIDATE_TAGS = 8
    MAX_CANDIDATE_KEYWORDS = 8
    CANDIDATE_SELECTION_TIMEOUT = 45

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def chat(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> str:
        """发送 chat 请求，返回模型回复文本"""
        url = f"{self.base_url}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = requests.post(
            url,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def recommend_tags(
        self, context: str, available_tags: list[str], top_k: int = 5
    ) -> list[str]:
        """让 LLM 从已有标签中选出最适合作为聊天回应表情的 tag"""
        if not available_tags:
            return []

        system = "你是一个表情包推荐助手，擅长理解中文聊天上下文并匹配最合适的表情标签。"
        prompt = f"""用户在聊天中说:
"{context}"

可用的表情标签(每个表情都被打了一个或多个标签):
{", ".join(available_tags)}

请从上面的标签中，挑选 {top_k} 个最适合作为回应表情的标签。

要求:
- 只返回标签名，用英文逗号分隔
- 不要解释，不要序号，不要其他任何文字
- 如果没有完全匹配的，挑选语义最接近的"""

        response = self.chat(prompt, system=system, temperature=0.3, timeout=30)
        parts = re.split(r"[,，;\n；]+", response)
        tags = [t.strip().lstrip("0123456789.、- ") for t in parts if t.strip()]
        return [t for t in tags if t in available_tags][:top_k]

    def analyze_recommendation(
        self,
        context: str,
        image_summaries: list[dict],
        available_tags: list[str],
        top_k: int = 5,
    ) -> dict:
        """结构化分析推荐意图（标签 + 关键词 + 可选图片 ID）"""
        summaries = image_summaries[:50]
        summary_lines = []
        for item in summaries:
            image_id = item.get("id")
            name = item.get("name", "")
            tags = item.get("tags", [])
            summary_lines.append(f"- id={image_id}, name={name}, tags={','.join(tags)}")

        system = "你是一个表情包推荐助手，擅长根据聊天语境理解语气、情绪和表达意图。"
        prompt = (
            f"聊天上下文:\n{context}\n\n"
            f"可用标签:\n{', '.join(available_tags)}\n\n"
            "候选图片（id/name/tags）:\n"
            + "\n".join(summary_lines)
            + "\n\n请输出 JSON（不要输出额外解释），格式：\n"
            "{\n"
            '  "tags": ["标签1", "标签2"],\n'
            '  "keywords": ["关键词1", "关键词2"],\n'
            '  "image_ids": [1, 2],\n'
            '  "reason": "可选，简短原因"\n'
            "}\n\n"
            f"要求：\n1) tags 只从可用标签中选择，最多 {top_k} 个\n"
            f"2) keywords 最多 {top_k} 个，优先情绪词、语气词、表达意图词\n"
            f"3) image_ids 最多 {top_k} 个，必须来自候选图片 id"
        )
        response = self.chat(prompt, system=system, temperature=0.2, timeout=30)
        parsed = self._parse_analysis_response(response, available_tags, top_k=top_k)
        if parsed["tags"] or parsed["keywords"] or parsed["image_ids"]:
            return parsed
        return {
            "tags": self.recommend_tags(context, available_tags, top_k=top_k),
            "keywords": [],
            "image_ids": [],
            "reason": "",
        }

    def select_candidate_images(
        self,
        context: str,
        image_summaries: list[dict],
        available_tags: list[str],
        candidate_count: int = 20,
    ) -> dict:
        """让 LLM 基于整个图片库的名称和标签只做候选范围筛选（不做最终排序）"""
        summaries = image_summaries
        summary_lines = []
        valid_ids: set[int] = set()
        for item in summaries:
            image_id = item.get("id")
            if image_id is None:
                continue
            try:
                normalized_id = int(image_id)
            except (TypeError, ValueError):
                continue
            valid_ids.add(normalized_id)
            name = item.get("name", "")
            tags = item.get("tags", [])
            summary_lines.append(f"- id={normalized_id}, name={name}, tags={','.join(tags)}")

        if not summary_lines:
            return {"image_ids": [], "tags": [], "keywords": [], "reason": ""}

        system = (
            "你是表情包候选筛选助手。"
            "你只能基于用户输入、表情包名称、已有标签筛选候选范围。"
            "请优先根据表情包名称做初筛，标签只作为辅助线索。"
            "后续本地排序会提高匹配提示语的标签权重，最终由视觉模型筛选。"
            "不要做最终排序判断，不要假装看到了图片内容。"
        )
        prompt = (
            f"用户输入/聊天上下文:\n{context}\n\n"
            f"可用标签:\n{', '.join(available_tags)}\n\n"
            "候选图片（id/name/tags）:\n"
            + "\n".join(summary_lines)
            + "\n\n请严格输出 JSON（不要额外解释），格式：\n"
            "{\n"
            '  "image_ids": [1, 2, 3],\n'
            '  "tags": ["标签1", "标签2"],\n'
            '  "keywords": ["关键词1", "关键词2"],\n'
            '  "reason": "简短说明"\n'
            "}\n\n"
            f"要求：\n"
            f"1) image_ids 最多 {candidate_count} 个，且必须来自上面的 id；\n"
            f"2) tags 只能从可用标签中选择，最多 {self.MAX_CANDIDATE_TAGS} 个；\n"
            f"3) keywords 最多 {self.MAX_CANDIDATE_KEYWORDS} 个；\n"
            f"4) 初筛范围是上面列出的整个图片库，不要只关注前几项；\n"
            f"5) 主要根据表情包名称判断是否相关，标签作为辅助；\n"
            f"6) 只做候选筛选，不做最终排序；\n"
            f"7) 用户输入的关键词/描述/上下文是最高优先级。"
        )
        response = self.chat(
            prompt,
            system=system,
            temperature=0.15,
            timeout=self.CANDIDATE_SELECTION_TIMEOUT,
        )
        parsed = self._parse_analysis_response(
            response,
            available_tags,
            top_k=max(1, candidate_count),
        )

        filtered_ids: list[int] = []
        seen_ids: set[int] = set()
        for image_id in parsed["image_ids"]:
            if image_id not in valid_ids or image_id in seen_ids:
                continue
            filtered_ids.append(image_id)
            seen_ids.add(image_id)

        parsed["image_ids"] = filtered_ids[:candidate_count]
        parsed["tags"] = parsed["tags"][: self.MAX_CANDIDATE_TAGS]
        parsed["keywords"] = parsed["keywords"][: self.MAX_CANDIDATE_KEYWORDS]
        return parsed

    @staticmethod
    def _parse_analysis_response(text: str, available_tags: list[str], top_k: int) -> dict:
        payload = LLMService._extract_json_payload(text)
        if not payload:
            return {"tags": [], "keywords": [], "image_ids": [], "reason": ""}
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {"tags": [], "keywords": [], "image_ids": [], "reason": ""}

        tags = data.get("tags", []) if isinstance(data, dict) else []
        keywords = data.get("keywords", []) if isinstance(data, dict) else []
        image_ids = data.get("image_ids", []) if isinstance(data, dict) else []
        reason = data.get("reason", "") if isinstance(data, dict) else ""

        if not isinstance(tags, list):
            tags = []
        if not isinstance(keywords, list):
            keywords = []
        if not isinstance(image_ids, list):
            image_ids = []

        tag_set = set(available_tags)
        norm_tags = [str(t).strip() for t in tags if str(t).strip() in tag_set][:top_k]
        norm_keywords = [str(k).strip() for k in keywords if str(k).strip()][:top_k]

        norm_image_ids: list[int] = []
        for val in image_ids:
            try:
                norm_image_ids.append(int(val))
            except (TypeError, ValueError):
                continue
        return {
            "tags": norm_tags,
            "keywords": norm_keywords,
            "image_ids": norm_image_ids[:top_k],
            "reason": str(reason).strip() if reason is not None else "",
        }

    @staticmethod
    def _extract_json_payload(text: str) -> str:
        content = (text or "").strip()
        if not content:
            return ""
        fence = re.search(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL)
        if fence:
            fenced = fence.group(1).strip()
            payload = LLMService._extract_first_json_object(fenced)
            if payload:
                return payload
        return LLMService._extract_first_json_object(content)

    @staticmethod
    def _extract_first_json_object(content: str) -> str:
        start = content.find("{")
        if start == -1:
            return ""
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(content)):
            ch = content[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return content[start : idx + 1]
        return ""
