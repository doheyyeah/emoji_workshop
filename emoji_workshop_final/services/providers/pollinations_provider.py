"""Pollinations 免费文生图提供商"""

from urllib.parse import quote

import requests


class PollinationsProvider:
    """Pollinations.ai 免费文生图"""

    name = "Pollinations (免费)"

    def generate(self, prompt: str, width: int = 512, height: int = 512, **kwargs) -> bytes:
        url = (
            f"https://image.pollinations.ai/prompt/{quote(prompt)}"
            f"?width={width}&height={height}&seed={kwargs.get('seed', 42)}&nologo=true&nofeed=true"
        )
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.content
