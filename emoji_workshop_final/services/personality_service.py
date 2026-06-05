from __future__ import annotations

import base64
import io
import math
import warnings
from collections import Counter


class PersonalityService:
    """基于本地使用数据生成可解释画像（雷达图 + 证据 + 兜底文案）。"""

    DIMENSIONS = [
        "情绪表达",
        "社交性",
        "幽默感",
        "创意",
        "同理心",
        "积极性",
        "稳重性",
        "审美偏好",
    ]

    KEYWORD_DIM_MAP: dict[str, dict[str, float]] = {
        "开心": {"情绪表达": 1.0, "积极性": 0.9},
        "快乐": {"情绪表达": 1.0, "积极性": 0.9},
        "笑": {"幽默感": 1.0, "情绪表达": 0.5},
        "搞笑": {"幽默感": 1.3},
        "沙雕": {"幽默感": 1.2, "社交性": 0.5},
        "社恐": {"社交性": -0.8, "稳重性": 0.4},
        "社牛": {"社交性": 1.2},
        "萌": {"同理心": 0.8, "审美偏好": 0.5},
        "可爱": {"同理心": 0.8, "审美偏好": 0.6},
        "治愈": {"同理心": 1.0},
        "创意": {"创意": 1.2},
        "艺术": {"创意": 0.7, "审美偏好": 1.0},
        "怒": {"情绪表达": 0.8, "稳重性": -0.6},
        "生气": {"情绪表达": 0.8, "稳重性": -0.6},
        "稳重": {"稳重性": 1.0},
    }

    TRAIT_BY_DIMENSION = {
        "情绪表达": "情绪表达派",
        "社交性": "社交达人",
        "幽默感": "幽默担当",
        "创意": "点子很多",
        "同理心": "共情细腻",
        "积极性": "乐观积极",
        "稳重性": "沉稳靠谱",
        "审美偏好": "审美在线",
    }

    def analyze(
        self,
        tag_counter: Counter,
        top_images: list[tuple[int, str, int]],
        peak_period: str,
        season: str,
    ) -> dict:
        dimensions = self._build_dimensions(tag_counter, peak_period)
        evidence_tags = self._build_evidence_tags(tag_counter)
        radar_chart_data_uri = self._build_radar_chart_data_uri(dimensions)
        fallback_traits = self._build_fallback_traits(dimensions)
        fallback_description = self._build_fallback_description(
            peak_period=peak_period,
            season=season,
            fallback_traits=fallback_traits,
            evidence_tags=evidence_tags,
            top_images=top_images,
        )
        return {
            "dimensions": dimensions,
            "evidence_tags": evidence_tags,
            "radar_chart_data_uri": radar_chart_data_uri,
            "fallback_traits": fallback_traits,
            "fallback_description": fallback_description,
        }

    def _build_dimensions(self, tag_counter: Counter, peak_period: str) -> dict[str, int]:
        total = sum(tag_counter.values()) or 1
        base = {dim: 35.0 for dim in self.DIMENSIONS}

        for tag, count in tag_counter.items():
            tag_text = str(tag).lower()
            weight = count / total
            matched = False
            for keyword, delta in self.KEYWORD_DIM_MAP.items():
                if keyword in tag_text:
                    matched = True
                    for dim, value in delta.items():
                        base[dim] = base.get(dim, 35.0) + value * weight * 40
            if not matched:
                base["创意"] += weight * 6
                base["审美偏好"] += weight * 4

        if peak_period == "深夜":
            base["创意"] += 6
            base["稳重性"] -= 3
        elif peak_period == "早晨":
            base["积极性"] += 6
            base["稳重性"] += 4
        elif peak_period in {"上午", "下午"}:
            base["稳重性"] += 3

        return {
            dim: max(10, min(95, int(round(score))))
            for dim, score in base.items()
        }

    @staticmethod
    def _build_evidence_tags(tag_counter: Counter) -> list[tuple[str, float]]:
        total = sum(tag_counter.values()) or 1
        return [
            (str(tag), round(count / total, 3))
            for tag, count in tag_counter.most_common(8)
        ]

    def _build_fallback_traits(self, dimensions: dict[str, int]) -> list[str]:
        sorted_dims = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)
        traits: list[str] = []
        for dim, score in sorted_dims[:4]:
            if score >= 50:
                traits.append(self.TRAIT_BY_DIMENSION.get(dim, dim))
        return traits or ["神秘莫测"]

    @staticmethod
    def _build_fallback_description(
        peak_period: str,
        season: str,
        fallback_traits: list[str],
        evidence_tags: list[tuple[str, float]],
        top_images: list[tuple[int, str, int]],
    ) -> str:
        traits_text = "、".join(fallback_traits[:3]) or "神秘莫测"
        tags_text = "、".join(tag for tag, _ in evidence_tags[:3]) or "暂无明显标签"
        top_image = top_images[0][1] if top_images else "常用表情"
        return (
            f"你的数据画像偏向「{traits_text}」。"
            f"你常在{peak_period}活跃，{season}阶段里更常用 {tags_text} 这类标签，"
            f"其中「{top_image}」出现频率较高。整体看起来既有个人节奏，也很会用表情传达情绪。"
        )

    def _build_radar_chart_data_uri(self, dimensions: dict[str, int]) -> str:
        try:
            import matplotlib

            matplotlib.use("Agg")
            matplotlib.rcParams["font.sans-serif"] = [
                "Microsoft YaHei",
                "SimHei",
                "PingFang SC",
                "Arial Unicode MS",
                "DejaVu Sans",
            ]
            matplotlib.rcParams["axes.unicode_minus"] = False

            from matplotlib.figure import Figure
            import numpy as np
        except Exception:
            return ""

        try:
            labels = list(dimensions.keys())
            values = [dimensions[label] for label in labels]
            angles = np.linspace(0, 2 * math.pi, len(labels), endpoint=False).tolist()
            values += values[:1]
            angles += angles[:1]

            fig = Figure(figsize=(4.8, 3.2), dpi=110)
            ax = fig.add_subplot(111, polar=True)
            ax.set_theta_offset(math.pi / 2)
            ax.set_theta_direction(-1)
            ax.plot(angles, values, color="#4a9eff", linewidth=2)
            ax.fill(angles, values, color="#4a9eff", alpha=0.28)
            ax.set_thetagrids([a * 180 / math.pi for a in angles[:-1]], labels)
            ax.set_ylim(0, 100)
            ax.grid(color="#b7bec9", alpha=0.35)

            buf = io.BytesIO()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
            buf.seek(0)
            return f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"
        except Exception:
            return ""
