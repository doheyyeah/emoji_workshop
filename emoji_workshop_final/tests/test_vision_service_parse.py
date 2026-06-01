"""P0-3 测试：验证 VisionService 能正确解析 "3,7,1" 格式的模型返回"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.vision_service import VisionService


@pytest.fixture
def valid_ids():
    return list(range(1, 16))  # 1..15


def test_parse_simple_comma_format(valid_ids):
    """标准格式 "3,7,1" 正确解析"""
    result = VisionService._parse_ranking("3,7,1", valid_ids)
    assert result == [3, 7, 1]


def test_parse_comma_with_spaces(valid_ids):
    """带空格的格式 "3, 7, 1" 正确解析"""
    result = VisionService._parse_ranking("3, 7, 1", valid_ids)
    assert result == [3, 7, 1]


def test_parse_embedded_in_text(valid_ids):
    """编号混在文字中也能提取"""
    result = VisionService._parse_ranking("最匹配的是编号3和7，其次是1", valid_ids)
    assert result == [3, 7, 1]


def test_parse_deduplication(valid_ids):
    """重复编号去重保序"""
    result = VisionService._parse_ranking("3,7,3,1", valid_ids)
    assert result == [3, 7, 1]


def test_parse_filters_invalid_ids(valid_ids):
    """超出候选编号范围的值被过滤"""
    result = VisionService._parse_ranking("3,99,7,1", valid_ids)
    assert result == [3, 7, 1]


def test_parse_empty_returns_empty(valid_ids):
    """无效输入返回空列表"""
    result = VisionService._parse_ranking("无法理解您的问题", valid_ids)
    assert result == []


def test_parse_top_k_slicing(valid_ids):
    """rerank 方法对返回编号截取 top_k"""
    # 通过 _parse_ranking 测试截取（rerank 含 API 调用，此处只测核心解析）
    result = VisionService._parse_ranking("3,7,1,5,2", valid_ids)
    # 所有编号均有效
    assert result == [3, 7, 1, 5, 2]
    # 截取前 3 个
    assert result[:3] == [3, 7, 1]
