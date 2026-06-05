from __future__ import annotations

import math
import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from PIL import Image
import io
import base64


class PersonalityService:
    """Generate a concise personality profile from usage history and tags.

    Produces:
    - short_summary: 1-line, 3 adjectives
    - summary_text: short HTML summary
    - dimensions: dict of 10 numeric scores 0-100
    - radar_svg_base64: PNG data URI of radar chart
    - examples: list of (id, name, file_path)
    """

    DIMENSIONS = [
        "情绪表达", "社交性", "幽默感", "正式度", "创意", "同理心",
        "冲动性", "积极性", "稳重性", "审美偏好"
    ]

    # Keyword -> dimension contributions (simple rules)
    KEYWORD_DIM_MAP = {
        # positive emotional tags
        "开心": {"情绪表达": 1, "积极性": 0.8},
        "快乐": {"情绪表达": 1, "积极性": 0.7},
        "笑": {"幽默感": 1, "情绪表达": 0.6},
        "搞笑": {"幽默感": 1.2},
        "沙雕": {"幽默感": 1.1, "冲动性": 0.6},
        "可爱": {"同理心": 0.9, "审美偏好": 0.6},
        "萌": {"同理心": 0.9},
        "治愈": {"同理心": 1.0},
        "怒": {"情绪表达": 1.0, "冲动性": 1.0},
        "生气": {"情绪表达": 1.0, "冲动性": 1.0},
        "惊讶": {"情绪表达": 0.8, "社交性": 0.6},
        "酷": {"正式度": 0.7, "审美偏好": 0.8},
        "帅": {"审美偏好": 0.8},
        "色": {"审美偏好": 0.6},
        "心": {"同理心": 0.8},
        "伤心": {"情绪表达": 1.0, "稳重性": 0.6},
        "严重": {"稳重性": 1.0},
        "创意": {"创意": 1.2},
        "艺术": {"审美偏好": 1.2, "创意": 0.8},
    }

    ADJECTIVE_BUCKETS = [
        (90, "极具表现力"),
        (75, "外向活跃"),
        (60, "幽默风趣"),
        (50, "温和有礼"),
        (35, "偏内向沉稳"),
        (0, "神秘莫测"),
    ]

    def __init__(self, db_service, config_manager):
        self.db = db_service
        self.config = config_manager

    def generate_profile(self, period: str = "week") -> dict:
        # get history
        since, period_label = self._calc_since_and_label(period)
        records = self.db.get_usage_history(since)
        total_uses = len(records)
        if total_uses == 0:
            return self._empty_profile(period_label)

        # accumulate tag scores with recency decay
        tag_scores: Dict[str, float] = defaultdict(float)
        now = datetime.now()
        for rec in records:
            # rec: (id, image_id, used_at)
            img_id = rec[1]
            used_at = self._parse_used_at(rec[2]) or now
            days = max(0.0, (now - used_at).days)
            # recency weight; recent more important
            weight = math.exp(-days / 30.0)
            # get tags
            tag_rows = self.db.get_image_tags(img_id)
            for tag_row in tag_rows:
                tag_name = tag_row[1]
                tag_scores[tag_name] += weight

        # normalize tag scores
        if not tag_scores:
            return self._empty_profile(period_label)

        max_score = max(tag_scores.values())
        for k in tag_scores:
            tag_scores[k] = tag_scores[k] / max_score

        # map to dimensions
        dims = {d: 0.0 for d in self.DIMENSIONS}
        for tag, s in tag_scores.items():
            lowered = tag.lower()
            matched = False
            for kw, contrib in self.KEYWORD_DIM_MAP.items():
                if kw in lowered:
                    matched = True
                    for dim, val in contrib.items():
                        dims[dim] = dims.get(dim, 0.0) + s * val
            if not matched:
                # unknown tags add mildly to creativity and aesthetic
                dims["创意"] = dims.get("创意", 0.0) + s * 0.3
                dims["审美偏好"] = dims.get("审美偏好", 0.0) + s * 0.2

        # visual heuristics: analyze top-used images for brightness/saturation
        top_images = self._get_top_images(records, top_k=6)
        visual_adj = self._analyze_visuals(top_images)
        # apply visual adjustments
        for dim, adj in visual_adj.items():
            if dim in dims:
                dims[dim] += adj

        # normalize dims to 0-100
        max_dim = max(dims.values()) or 1.0
        dims_percent = {k: min(100, int((v / max_dim) * 100)) for k, v in dims.items()}

        # choose top adjectives by key dimensions (select top three dimensions)
        sorted_dims = sorted(dims_percent.items(), key=lambda x: -x[1])
        top_dims = [d for d, _ in sorted_dims[:3]]
        adjectives = [self._map_dim_to_adjective(dims_percent[d]) for d in top_dims]

        short_summary = "、".join(adjectives)

        # build concise HTML summary with radar chart embedded
        radar_data_uri = self._make_radar_chart_datauri(dims_percent)

        # examples: top 4 images
        examples = []
        for img_id, _ in Counter([rec[1] for rec in records]).most_common(4):
            row = self.db.get_image_by_id(img_id)
            if row:
                examples.append((img_id, row[1], row[2]))

        summary_lines = []
        summary_lines.append(f"<h2>🎭 {period_label} 性格画像</h2>")
        summary_lines.append(f"<p style='font-size:13px;color:#888;'>简洁总结：<b>{short_summary}</b></p>")
        summary_lines.append(f"<img src=\"{radar_data_uri}\" style='max-width:540px;display:block;margin:8px auto;'/>")
        summary_lines.append("<p style='color:#666;font-size:12px;'>关键证据：</p><ul>")
        # list top contributing tags
        top_tags = sorted(tag_scores.items(), key=lambda x: -x[1])[:8]
        for t, sc in top_tags:
            summary_lines.append(f"<li>{t}（权重 {sc:.2f}）</li>")
        summary_lines.append("</ul>")
        summary_lines.append("<p style='color:#888;font-size:12px;'>注：画像由表情使用行为与标签自动推断，保持简短且可解释。</p>")

        summary_text = "\n".join(summary_lines)

        profile = {
            "period": period_label,
            "total_uses": total_uses,
            "short_summary": short_summary,
            "summary_text": summary_text,
            "dimensions": dims_percent,
            "examples": examples,
        }
        return profile

    # ---------------- helpers ----------------
    def _empty_profile(self, period_label: str) -> dict:
        return {
            "period": period_label,
            "total_uses": 0,
            "short_summary": "暂无数据",
            "summary_text": f"<p>{period_label}暂无使用记录。</p>",
            "dimensions": {d: 0 for d in self.DIMENSIONS},
            "examples": [],
        }

    def _calc_since_and_label(self, period: str) -> Tuple[str, str]:
        now = datetime.now()
        if period == "week":
            start = now - timedelta(days=now.weekday())
            label = f"{now.year}年第{now.isocalendar().week}周"
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            label = f"{now.year}年{now.month}月"
        else:
            start = datetime(2026, 1, 1)
            label = f"自开始至今"
        return start.isoformat(), label

    @staticmethod
    def _parse_used_at(s: str) -> datetime | None:
        try:
            return datetime.fromisoformat(s)
        except Exception:
            try:
                s2 = s.replace('T', ' ').split('.')[0]
                return datetime.strptime(s2, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

    def _get_top_images(self, records, top_k=6):
        counts = Counter([r[1] for r in records])
        top = [img_id for img_id, _ in counts.most_common(top_k)]
        imgs = []
        for img_id in top:
            row = self.db.get_image_by_id(img_id)
            if row:
                imgs.append({"id": row[0], "name": row[1], "file_path": row[2]})
        return imgs

    def _analyze_visuals(self, images: List[dict]) -> Dict[str, float]:
        # simple visual heuristics using PIL: saturation and brightness
        adj = {d: 0.0 for d in self.DIMENSIONS}
        if not images:
            return adj
        sat_vals = []
        val_vals = []
        for im in images:
            try:
                with Image.open(im["file_path"]) as img:
                    img = img.convert("RGB")
                    img.thumbnail((128, 128))
                    # compute average saturation and value
                    hsv = img.convert("HSV")
                    h, s, v = hsv.split()
                    sat = sum(s.getdata()) / (255.0 * img.size[0] * img.size[1])
                    val = sum(v.getdata()) / (255.0 * img.size[0] * img.size[1])
                    sat_vals.append(sat)
                    val_vals.append(val)
            except Exception:
                continue
        if not sat_vals:
            return adj
        avg_sat = sum(sat_vals) / len(sat_vals)
        avg_val = sum(val_vals) / len(val_vals)
        # heuristics
        # high saturation -> creative + aesthetic
        adj["创意"] += avg_sat * 1.2
        adj["审美偏好"] += avg_sat * 1.0
        # high brightness -> positive
        adj["积极性"] += max(0.0, (avg_val - 0.45)) * 1.4
        # low brightness -> more stable/serious
        adj["稳重性"] += max(0.0, (0.5 - avg_val)) * 0.8
        return adj

    def _map_dim_to_adjective(self, score: int) -> str:
        # choose adjective by score roughly
        for thresh, adj in self.ADJECTIVE_BUCKETS:
            if score >= thresh:
                return adj
        return "神秘莫测"

    def _make_radar_chart_datauri(self, dims: Dict[str, int]) -> str:
        try:
            import matplotlib
            matplotlib.use("Agg")
            from matplotlib.figure import Figure
            import numpy as np

            labels = list(dims.keys())
            values = [dims[l] for l in labels]
            angles = np.linspace(0, 2 * math.pi, len(labels), endpoint=False).tolist()
            values += values[:1]
            angles += angles[:1]

            fig = Figure(figsize=(5.2, 3.6), dpi=90)
            ax = fig.add_subplot(111, polar=True)
            ax.set_theta_offset(math.pi / 2)
            ax.set_theta_direction(-1)
            ax.plot(angles, values, color="#4a9eff", linewidth=2)
            ax.fill(angles, values, color="#4a9eff", alpha=0.25)
            ax.set_thetagrids([a * 180 / math.pi for a in angles[:-1]], labels)
            ax.set_rlim(0, 100)
            ax.grid(color="#333333")
            ax.set_facecolor("none")

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            return f"data:image/png;base64,{b64}"
        except Exception:
            return ""
