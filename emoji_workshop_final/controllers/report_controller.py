"""性格画像报告控制器

职责：
- 读取 usage_history 表中的使用记录
- 分析使用时段、高频表情、高频标签
- 基于规则推断用户性格倾向
- 生成结构化报告字典

说明：
    usage_history 表会在本控制器第一次访问时由 DatabaseService 自动创建。
    若表中暂无数据，所有字段均返回友好默认值，不会崩溃。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from services.database_service import DatabaseService


# 时段定义
_PERIOD_NAMES = {
    range(5, 9):   "早晨",
    range(9, 12):  "上午",
    range(12, 14): "中午",
    range(14, 18): "下午",
    range(18, 22): "傍晚",
    range(22, 24): "深夜",
    range(0, 5):   "深夜",
}

# 性格规则：(关键词集合, 特征标签)
_PERSONALITY_RULES: list[tuple[set[str], str]] = [
    ({"开心", "快乐", "笑", "哈哈", "高兴", "喜悦", "棒", "厉害"}, "阳光开朗"),
    ({"难过", "哭", "沮丧", "伤心", "失落", "委屈", "痛苦"}, "感性细腻"),
    ({"搞笑", "沙雕", "无语", "哭笑", "好笑", "滑稽", "蠢萌"}, "幽默风趣"),
    ({"猫", "狗", "可爱", "萌", "治愈", "温柔", "暖", "爱心"}, "温柔治愈"),
    ({"怒", "生气", "暴怒", "愤怒", "烦", "崩溃"}, "情绪丰富"),
]


def _hour_to_period(hour: int) -> str:
    """将小时数转换为时段名称"""
    for r, name in _PERIOD_NAMES.items():
        if hour in r:
            return name
    return "深夜"


class ReportController:
    """性格画像报告控制器"""

    def __init__(self, db_service: DatabaseService) -> None:
        self.db = db_service
        # 确保 usage_history 表存在
        self.db.ensure_usage_history_table()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def generate_report(self, period: str = "week") -> dict:
        """生成性格画像报告

        Args:
            period: 统计粒度，"week" / "month" / "all"

        Returns:
            包含报告各字段的字典：
            {
                "period": str,
                "total_uses": int,
                "active_hours": [(hour, count), ...],
                "peak_period": str,
                "top_images": [(image_id, name, count), ...],
                "top_tags": [(tag_name, count), ...],
                "personality_traits": [str, ...],
                "summary_text": str,
            }
        """
        since = self._calc_since(period)
        records = self.db.get_usage_history(since)

        period_label = {"week": "本周", "month": "本月", "all": "全部时间"}.get(period, "全部时间")
        total_uses = len(records)

        if total_uses == 0:
            return self._empty_report(period_label)

        # 分析时段
        hour_counter: Counter = Counter()
        image_counter: Counter = Counter()
        for rec in records:
            # rec: (id, image_id, used_at)
            image_id = rec[1]
            used_at_str = rec[2]
            image_counter[image_id] += 1
            try:
                dt = datetime.fromisoformat(str(used_at_str))
                hour_counter[dt.hour] += 1
            except Exception:
                pass

        active_hours = sorted(hour_counter.items(), key=lambda x: -x[1])
        peak_hour = active_hours[0][0] if active_hours else 12
        peak_period = _hour_to_period(peak_hour)

        # Top 5 图片
        top_image_ids = [img_id for img_id, _ in image_counter.most_common(5)]
        top_images: list[tuple[int, str, int]] = []
        for img_id in top_image_ids:
            row = self.db.get_image_by_id(img_id)
            name = row[1] if row else f"图片#{img_id}"
            top_images.append((img_id, name, image_counter[img_id]))

        # Top 10 标签（通过常用图片的标签统计）
        tag_counter: Counter = Counter()
        for img_id in image_counter:
            tag_rows = self.db.get_image_tags(img_id)
            for tag_row in tag_rows:
                tag_name = tag_row[1]
                tag_counter[tag_name] += image_counter[img_id]
        top_tags = tag_counter.most_common(10)

        # 性格判断
        personality_traits = self._infer_personality(
            tag_counter, peak_period, total_uses
        )

        # 组装报告文字
        summary_text = self._build_summary(
            period_label, total_uses, peak_period,
            top_images, top_tags, personality_traits
        )

        return {
            "period": period_label,
            "total_uses": total_uses,
            "active_hours": active_hours,
            "peak_period": peak_period,
            "top_images": top_images,
            "top_tags": top_tags,
            "personality_traits": personality_traits,
            "summary_text": summary_text,
        }

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_since(period: str) -> str | None:
        """计算时间范围的起始时间字符串（ISO 格式）"""
        now = datetime.now()
        if period == "week":
            since = now - timedelta(weeks=1)
        elif period == "month":
            since = now - timedelta(days=30)
        else:
            return None
        return since.isoformat()

    @staticmethod
    def _empty_report(period_label: str) -> dict:
        return {
            "period": period_label,
            "total_uses": 0,
            "active_hours": [],
            "peak_period": "—",
            "top_images": [],
            "top_tags": [],
            "personality_traits": [],
            "summary_text": f"<p>{period_label}暂无使用记录。<br>开始使用表情包，这里会生成你的专属性格画像！✨</p>",
        }

    @staticmethod
    def _infer_personality(
        tag_counter: Counter,
        peak_period: str,
        total_uses: int,
    ) -> list[str]:
        """基于标签分布和使用时段推断性格特征"""
        traits: list[str] = []
        total_tag_uses = sum(tag_counter.values()) or 1

        for keywords, trait in _PERSONALITY_RULES:
            matched = sum(
                count for tag, count in tag_counter.items()
                if any(kw in tag for kw in keywords)
            )
            if matched / total_tag_uses > 0.15:  # 占比 > 15% 即触发
                traits.append(trait)

        # 时段特征
        if peak_period == "深夜":
            traits.append("夜猫子型")
        elif peak_period == "早晨":
            traits.append("早起鸟型")

        if not traits:
            traits.append("神秘莫测")

        return traits

    @staticmethod
    def _build_summary(
        period_label: str,
        total_uses: int,
        peak_period: str,
        top_images: list[tuple[int, str, int]],
        top_tags: list[tuple[str, int]],
        personality_traits: list[str],
    ) -> str:
        """生成 HTML 格式的报告正文"""
        lines: list[str] = []

        lines.append(f"<h2>🎭 {period_label}性格画像报告</h2>")
        lines.append(f"<p>📊 {period_label}共使用表情 <b>{total_uses}</b> 次，")
        lines.append(f"你在 <b>{peak_period}</b> 最为活跃。</p>")

        if personality_traits:
            traits_str = "、".join(f"<b>{t}</b>" for t in personality_traits)
            lines.append(f"<p>🌟 性格特征：{traits_str}</p>")

        if top_images:
            lines.append("<h3>🏆 最爱的表情 Top 5</h3><ol>")
            for _, name, count in top_images:
                lines.append(f"<li>{name}（使用 {count} 次）</li>")
            lines.append("</ol>")

        if top_tags:
            lines.append("<h3>🏷️ 高频标签 Top 10</h3><p>")
            tag_parts = [f"{tag}（{count}次）" for tag, count in top_tags]
            lines.append("、".join(tag_parts))
            lines.append("</p>")

        lines.append("<hr><p style='color:#888;font-size:12px;'>报告由表情工坊自动生成 ✨</p>")

        return "\n".join(lines)
