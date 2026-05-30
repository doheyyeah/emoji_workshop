"""通用 LLM 服务 - OpenAI 兼容接口"""

import re

import requests


class LLMService:
    """通用 LLM 客户端，使用 OpenAI 兼容接口"""

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
