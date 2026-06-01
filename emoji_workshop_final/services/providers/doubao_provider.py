"""豆包 Seedream 5.0 Lite 文生图提供商（火山方舟接口）"""

import requests


class DoubaoProvider:
    """豆包 Seedream 5.0 Lite（火山方舟）

    接口文档：https://www.volcengine.com/docs/82379/1354228
    Endpoint:  https://ark.cn-beijing.volces.com/api/v3/images/generations
    Model:     doubao-seedream-5-0-260128
    """

    name = "豆包 Seedream 5.0 Lite"
    endpoint = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    default_model = "doubao-seedream-5-0-260128"

    def generate(self, prompt: str, width: int = 1024, height: int = 1024, **kwargs) -> bytes:
        api_key = kwargs.get("api_key", "")
        if not api_key:
            raise RuntimeError("缺少豆包 API Key，请在设置中填写")

        model = kwargs.get("model", self.default_model)
        payload = {
            "model": model,
            "prompt": prompt,
            "size": f"{width}x{height}",
            "response_format": "url",
            "watermark": False,
        }
        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        if not data:
            raise RuntimeError("豆包接口返回内容为空")
        image_url = data[0].get("url")
        if not image_url:
            raise RuntimeError("豆包接口返回格式不支持")
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content
