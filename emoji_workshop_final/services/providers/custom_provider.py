"""自定义 OpenAI 兼容文生图提供商"""

import requests


class CustomProvider:
    """用户自定义 OpenAI 兼容图片生成接口"""

    name = "🛠 自定义"

    def generate(self, prompt: str, width: int = 512, height: int = 512, **kwargs) -> bytes:
        api_key = kwargs.get("api_key", "").strip()
        model = kwargs.get("model", "").strip()
        base_url = kwargs.get("base_url", "").strip().rstrip("/")
        if not base_url:
            raise RuntimeError("请先填写自定义 Base URL")
        if not model:
            raise RuntimeError("请先填写自定义模型名")
        if not api_key:
            raise RuntimeError("请先填写自定义 API Key")

        response = requests.post(
            f"{base_url}/images/generations",
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "prompt": prompt,
                "size": f"{width}x{height}",
                "response_format": "url",
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        if not data:
            raise RuntimeError("自定义接口返回内容为空")
        image_url = data[0].get("url")
        if not image_url:
            raise RuntimeError("自定义接口返回格式不支持")
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content
