"""P0-4 测试：LA 模式图片可正常生成 JPEG 缩略图"""

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.thumbnail_service import ThumbnailService


def test_thumbnail_generation_supports_la_mode(tmp_path):
    src = tmp_path / "la.png"
    Image.new("LA", (16, 16), (120, 128)).save(src)

    service = ThumbnailService(cache_dir=str(tmp_path / "thumbs"))
    out = service.get_thumbnail(str(src))

    assert out is not None
    assert Path(out).exists()
