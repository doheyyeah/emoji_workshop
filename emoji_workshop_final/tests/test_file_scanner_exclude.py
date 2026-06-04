"""P0-3 测试：扫描时排除 venv/site-packages 等目录"""

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.file_scanner import FileScanner


def _make_png(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (255, 0, 0)).save(path)


def test_scan_directory_excludes_virtualenv_dirs(tmp_path):
    keep = tmp_path / "assets" / "ok.png"
    skip1 = tmp_path / "venv" / "Lib" / "site-packages" / "bad.png"
    skip2 = tmp_path / ".venv" / "bad2.png"
    _make_png(keep)
    _make_png(skip1)
    _make_png(skip2)

    files = FileScanner.scan_directory(str(tmp_path))
    assert str(keep) in files
    assert str(skip1) not in files
    assert str(skip2) not in files
