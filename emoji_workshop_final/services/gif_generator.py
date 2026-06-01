"""GIF 表情包生成器 —— 支持 8 种文字动画方式

动画模式（AnimationMode 枚举）：
1. BOTTOM_UP_STAY    从下到上（停留）
2. BOTTOM_UP_LOOP   从下到上（循环消失）
3. TOP_DOWN_STAY    从上到下（停留）
4. TOP_DOWN_LOOP    从上到下（循环消失）
5. LEFT_RIGHT_STAY  从左到右（停留）
6. LEFT_RIGHT_LOOP  从左到右（循环消失）
7. RIGHT_LEFT_STAY  从右到左（停留）
8. RIGHT_LEFT_LOOP  从右到左（循环消失）

"停留"模式：前半段插值滑入，后半段固定居中
"循环消失"模式：整段穿越，alpha 三角形渐变（进入淡入，离开淡出）
"""

import math
from enum import Enum
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


class AnimationMode(Enum):
    BOTTOM_UP_STAY   = "从下到上（停留）"
    BOTTOM_UP_LOOP   = "从下到上（循环消失）"
    TOP_DOWN_STAY    = "从上到下（停留）"
    TOP_DOWN_LOOP    = "从上到下（循环消失）"
    LEFT_RIGHT_STAY  = "从左到右（停留）"
    LEFT_RIGHT_LOOP  = "从左到右（循环消失）"
    RIGHT_LEFT_STAY  = "从右到左（停留）"
    RIGHT_LEFT_LOOP  = "从右到左（循环消失）"


# 展示名称 → 枚举（供 UI 下拉使用）
ANIMATION_MODE_NAMES: list[str] = [m.value for m in AnimationMode]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """字体加载链：msyh.ttc → msyh.ttf → simhei.ttf → PingFang.ttc → 默认"""
    candidates = [
        "msyh.ttc",
        "msyh.ttf",
        "simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _calc_position(
    mode: AnimationMode,
    t: float,
    W: int,
    H: int,
    tw: int,
    th: int,
) -> tuple[int, int, int]:
    """计算文字在 t∈[0,1] 时刻的 (x, y, alpha)

    "停留"模式：
        前半段 [0, 0.5)：线性插值从起点滑入到画面中央
        后半段 [0.5, 1]：固定在画面中央（alpha=255）

    "循环消失"模式：
        整段穿越画面，alpha 三角形渐变（进入淡入 0→255，离开淡出 255→0）
    """
    cx = (W - tw) // 2  # 水平居中 x
    cy = (H - th) // 2  # 垂直居中 y

    is_stay = mode.value.endswith("（停留）")

    if mode in (AnimationMode.BOTTOM_UP_STAY, AnimationMode.BOTTOM_UP_LOOP):
        # 从画面底部向上
        if is_stay:
            if t < 0.5:
                progress = t / 0.5
                y = int(H + th - progress * (H + th - cy))
            else:
                y = cy
            return cx, y, 255
        else:
            # 穿越：从 H+th 到 -th
            total_travel = H + 2 * th
            y = int(H + th - t * total_travel)
            alpha = _triangle_alpha(t)
            return cx, y, alpha

    elif mode in (AnimationMode.TOP_DOWN_STAY, AnimationMode.TOP_DOWN_LOOP):
        # 从画面顶部向下
        if is_stay:
            if t < 0.5:
                progress = t / 0.5
                y = int(-th + progress * (cy + th))
            else:
                y = cy
            return cx, y, 255
        else:
            total_travel = H + 2 * th
            y = int(-th + t * total_travel)
            alpha = _triangle_alpha(t)
            return cx, y, alpha

    elif mode in (AnimationMode.LEFT_RIGHT_STAY, AnimationMode.LEFT_RIGHT_LOOP):
        # 从左到右
        if is_stay:
            if t < 0.5:
                progress = t / 0.5
                x = int(-tw + progress * (cx + tw))
            else:
                x = cx
            return x, cy, 255
        else:
            total_travel = W + 2 * tw
            x = int(-tw + t * total_travel)
            alpha = _triangle_alpha(t)
            return x, cy, alpha

    else:  # RIGHT_LEFT
        # 从右到左
        if is_stay:
            if t < 0.5:
                progress = t / 0.5
                x = int(W + progress * (cx - W))
            else:
                x = cx
            return x, cy, 255
        else:
            total_travel = W + 2 * tw
            x = int(W + tw - t * total_travel)
            alpha = _triangle_alpha(t)
            return x, cy, alpha


def _triangle_alpha(t: float) -> int:
    """三角形 alpha：0→255 在前半段，255→0 在后半段"""
    if t < 0.5:
        return int(t / 0.5 * 255)
    else:
        return int((1 - t) / 0.5 * 255)


class GifGenerator:
    FRAMES = 16     # 默认帧数
    DURATION = 100  # 默认帧间隔（ms）

    @staticmethod
    def make_text_animated_gif(
        base_image_path: str,
        text: str,
        output_path: str,
        mode: AnimationMode | str = AnimationMode.BOTTOM_UP_STAY,
        font_size: int = 36,
        text_color: str = "#FFE600",
        frames: int = 16,
        duration: int = 100,
    ) -> str:
        """生成带文字动画的 GIF

        Args:
            base_image_path: 基础静图路径
            text: 叠加文字
            output_path: 输出 GIF 路径
            mode: 动画模式（AnimationMode 枚举或枚举值字符串）
            font_size: 字体大小（20-60）
            text_color: 文字颜色（十六进制）
            frames: 帧数（默认 16）
            duration: 帧间隔（ms，默认 100）

        Returns:
            输出文件路径
        """
        if isinstance(mode, str):
            # 支持传入枚举 value 字符串
            for m in AnimationMode:
                if m.value == mode:
                    mode = m
                    break
            else:
                mode = AnimationMode.BOTTOM_UP_STAY

        base = Image.open(base_image_path).convert("RGBA")
        W, H = base.size
        font = _load_font(font_size)

        # 预计算文字尺寸
        dummy_draw = ImageDraw.Draw(base)
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # 解析文字颜色
        try:
            r = int(text_color[1:3], 16)
            g = int(text_color[3:5], 16)
            b = int(text_color[5:7], 16)
        except Exception:
            r, g, b = 255, 230, 0

        gif_frames = []
        for i in range(frames):
            t = i / max(frames - 1, 1)
            x, y, alpha = _calc_position(mode, t, W, H, tw, th)

            frame = base.copy()
            draw = ImageDraw.Draw(frame)
            draw.text(
                (x, y),
                text,
                font=font,
                fill=(r, g, b, alpha),
                stroke_width=2,
                stroke_fill=(0, 0, 0, alpha),
            )
            gif_frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))

        gif_frames[0].save(
            output_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration,
            loop=0,
            optimize=True,
        )
        return output_path

    @staticmethod
    def make_multiframe_gif(
        image_paths: list[str],
        output_path: str,
        duration: int = 200,
    ) -> str:
        """将多张图片拼成 GIF（模式 B：多帧 AI 拼接）"""
        images = [
            Image.open(p).convert("RGBA").convert("P", palette=Image.Palette.ADAPTIVE)
            for p in image_paths
        ]
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
        )
        return output_path
