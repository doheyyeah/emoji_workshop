"""性格画像报告控制器

职责：
- 读取 usage_history 表中的使用记录
- 分析使用时段、高频表情、高频标签
- 优先使用 LLM 结合统计、时段和季节生成有趣画像
- LLM 不可用时降级为本地规则画像
- 生成结构化报告字典

说明：
    usage_history 表会在本控制器第一次访问时由 DatabaseService 自动创建。
    若表中暂无数据，所有字段均返回友好默认值，不会崩溃。
"""

from __future__ import annotations

import html
import re
from collections import Counter
from datetime import datetime, timedelta

from services.database_service import DatabaseService
from services.llm_service import LLMService
from services.personality_service import PersonalityService
from utils.config_manager import ConfigManager


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

# 性格规则：(关键词集合, 特征标签)，作为 LLM 不可用时的兜底
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


def _month_to_season(month: int) -> str:
    """将月份转换为季节名称"""
    if month in (3, 4, 5):
        return "春季"
    if month in (6, 7, 8):
        return "夏季"
    if month in (9, 10, 11):
        return "秋季"
    return "冬季"


class ReportController:
    """性格画像报告控制器"""

    def __init__(self, db_service: DatabaseService, config_manager: ConfigManager | None = None) -> None:
        self.db = db_service
        self.config = config_manager or ConfigManager()
        self.personality_service = PersonalityService()
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
            包含报告各字段的字典。
        """
        since, period_label = self._calc_since_and_label(period)
        records = self.db.get_usage_history(since)
        total_uses = len(records)

        if total_uses == 0:
            return self._empty_report(period_label)

        now = datetime.now()
        season = _month_to_season(now.month)

        # 分析时段、图片使用
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

        # 本地画像层（雷达图 + 证据标签 + 兜底人格描述）
        local_profile = self.personality_service.analyze(
            tag_counter=tag_counter,
            top_images=top_images,
            peak_period=peak_period,
            season=season,
        )
        fallback_traits = local_profile["fallback_traits"]
        fallback_description = local_profile["fallback_description"]

        # 优先尝试 LLM 画像；失败则使用兜底画像
        ai_traits, ai_description, ai_enabled = self._generate_llm_personality(
            period_label=period_label,
            total_uses=total_uses,
            peak_period=peak_period,
            season=season,
            active_hours=active_hours,
            top_images=top_images,
            top_tags=top_tags,
            fallback_traits=fallback_traits,
            fallback_description=fallback_description,
        )

        # 组装报告文字
        summary_text = self._build_summary(
            period_label=period_label,
            total_uses=total_uses,
            peak_period=peak_period,
            season=season,
            active_hours=active_hours,
            top_images=top_images,
            top_tags=top_tags,
            personality_traits=ai_traits,
            personality_description=ai_description,
            ai_enabled=ai_enabled,
            local_profile=local_profile,
        )

        return {
            "period": period_label,
            "total_uses": total_uses,
            "active_hours": active_hours,
            "peak_period": peak_period,
            "season": season,
            "top_images": top_images,
            "top_tags": top_tags,
            "personality_traits": ai_traits,
            "personality_description": ai_description,
            "ai_enabled": ai_enabled,
            "dimensions": local_profile["dimensions"],
            "evidence_tags": local_profile["evidence_tags"],
            "radar_chart_data_uri": local_profile["radar_chart_data_uri"],
            "fallback_traits": local_profile["fallback_traits"],
            "fallback_description": local_profile["fallback_description"],
            "summary_text": summary_text,
        }

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_since_and_label(period: str) -> tuple[str | None, str]:
        """计算时间范围与显示标签"""
        now = datetime.now()
        if period == "week":
            week_start = now - timedelta(days=now.weekday())
            week_end = week_start + timedelta(days=6)
            week_no = now.isocalendar().week
            label = f"{now.year}年第{week_no}周({week_start:%m-%d} ~ {week_end:%m-%d})"
            since = week_start
        elif period == "month":
            label = f"{now.year}年{now.month}月"
            since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            since = datetime(2026, 1, 1)
            label = f"{since:%Y-%m-%d} 至今"
        return since.isoformat() if since else None, label

    @staticmethod
    def _empty_report(period_label: str) -> dict:
        return {
            "period": period_label,
            "total_uses": 0,
            "active_hours": [],
            "peak_period": "—",
            "season": _month_to_season(datetime.now().month),
            "top_images": [],
            "top_tags": [],
            "personality_traits": [],
            "personality_description": "",
            "ai_enabled": False,
            "dimensions": {},
            "evidence_tags": [],
            "radar_chart_data_uri": "",
            "fallback_traits": [],
            "fallback_description": "",
            "summary_text": f"<p>{period_label}暂无使用记录。<br>开始使用表情包，这里会生成你的专属性格画像！✨</p>",
        }

    @staticmethod
    def _infer_personality(
        tag_counter: Counter,
        peak_period: str,
        total_uses: int,
    ) -> list[str]:
        """基于标签分布和使用时段推断性格特征（LLM 不可用时兜底）"""
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

        return traits[:5]

    @staticmethod
    def _build_fallback_description(
        peak_period: str,
        season: str,
        top_tags: list[tuple[str, int]],
        traits: list[str],
    ) -> str:
        tag_text = "、".join(tag for tag, _ in top_tags[:3]) or "一些很有个人风格的表情"
        trait_text = "、".join(traits) or "神秘莫测"
        return (
            f"你最近的表情包气质偏向「{trait_text}」。"
            f"高频出没时段是{peak_period}，常用标签集中在{tag_text}。"
            f"在{season}的氛围里，你像一台随时准备发射情绪弹幕的小型雷达，"
            "看似只是发图，其实每一张都在精准表达当下的心情。"
        )

    def _generate_llm_personality(
        self,
        period_label: str,
        total_uses: int,
        peak_period: str,
        season: str,
        active_hours: list[tuple[int, int]],
        top_images: list[tuple[int, str, int]],
        top_tags: list[tuple[str, int]],
        fallback_traits: list[str],
        fallback_description: str,
    ) -> tuple[list[str], str, bool]:
        """调用与智能推荐相同的 LLM 配置生成画像；失败自动降级。"""
        cfg = self.config.get_llm_config()
        if not (cfg.get("enabled") and cfg.get("base_url") and cfg.get("api_key") and cfg.get("model")):
            return fallback_traits, fallback_description, False

        llm = LLMService(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            model=cfg["model"],
        )

        top_tags_text = "、".join(f"{tag}({count}次)" for tag, count in top_tags) or "暂无标签"
        top_images_text = "、".join(f"{name}({count}次)" for _, name, count in top_images) or "暂无图片"
        active_hours_text = "、".join(f"{hour}:00({count}次)" for hour, count in active_hours[:5]) or "暂无时段"

        system = (
            "你是一个幽默、温和、不过度诊断的表情包性格画像助手。"
            "你只能根据给定的表情包使用统计做轻松娱乐向总结，不能做严肃心理诊断，"
            "不能输出负面攻击、隐私推断或令人不适的评价。"
        )
        prompt = f"""请根据下面的表情包使用统计，生成一份轻松有趣的性格画像。\n\n统计周期：{period_label}\n总使用次数：{total_uses}\n最活跃时段：{peak_period}\n当前季节：{season}\n高频小时：{active_hours_text}\n高频标签：{top_tags_text}\n最常用表情：{top_images_text}\n\n请严格按以下格式输出，不要添加其他内容：\n特征：标签1、标签2、标签3\n描述：一段 80 到 150 字的中文描述，风格活泼有梗，但要友好、简明、不要冒犯用户。\n\n要求：\n- 特征只给 3 到 5 个短标签，每个标签 2 到 6 个字。\n- 描述中要自然结合高频标签、时段特征、季节特征。\n- 不要说“根据数据可知”这种太机械的话。\n- 不要输出 Markdown。\n"""

        try:
            response = llm.chat(prompt, system=system, temperature=0.85, timeout=30)
            traits, description = self._parse_llm_personality(response)
            if traits and description:
                return traits[:5], description, True
        except Exception:
            pass

        return fallback_traits, fallback_description, False

    @staticmethod
    def _parse_llm_personality(response: str) -> tuple[list[str], str]:
        """解析 LLM 返回的“特征/描述”格式。"""
        text = (response or "").strip()
        if not text:
            return [], ""

        traits_match = re.search(r"特征[:：]\s*(.+)", text)
        desc_match = re.search(r"描述[:：]\s*(.+)", text, flags=re.S)
        if not traits_match or not desc_match:
            return [], ""

        raw_traits = traits_match.group(1).strip().splitlines()[0]
        traits = [t.strip(" ，,、;；。") for t in re.split(r"[、,，;；]", raw_traits) if t.strip()]
        traits = [html.escape(t[:12]) for t in traits if t]

        description = desc_match.group(1).strip()
        description = re.sub(r"\s+", " ", description)
        description = html.escape(description[:260])
        return traits, description

    @staticmethod
    def _build_summary(
        period_label: str,
        total_uses: int,
        peak_period: str,
        season: str,
        active_hours: list[tuple[int, int]],
        top_images: list[tuple[int, str, int]],
        top_tags: list[tuple[str, int]],
        personality_traits: list[str],
        personality_description: str,
        ai_enabled: bool,
        local_profile: dict,
    ) -> str:
        """生成 HTML 格式的报告正文"""
        lines: list[str] = []

        lines.append(f"<h2>🎭 {html.escape(period_label)}性格画像报告</h2>")
        lines.append("<p style='font-size:12px;color:#888;'>📊 统计规则:每次双击图片(自动复制到剪贴板)记为 1 次使用</p>")
        lines.append(
            f"<p>📊 {html.escape(period_label)}共使用表情 <b>{total_uses}</b> 次，"
            f"你在 <b>{html.escape(peak_period)}</b> 最为活跃，当前属于 <b>{html.escape(season)}</b> 画像。</p>"
        )

        if personality_traits:
            traits_str = "、".join(f"<b>{html.escape(t)}</b>" for t in personality_traits)
            source = "AI 生成" if ai_enabled else "本地规则"
            lines.append(f"<h3>🌟 性格特征 <span style='font-size:11px;color:#888;'>({source})</span></h3>")
            lines.append(f"<p>{traits_str}</p>")

        if personality_description:
            lines.append("<h3>🧠 画像描述</h3>")
            lines.append(f"<p>{personality_description}</p>")

        # 本地数据画像层：与 LLM 共存
        dimensions = local_profile.get("dimensions", {}) or {}
        radar_chart = local_profile.get("radar_chart_data_uri", "") or ""
        evidence_tags = local_profile.get("evidence_tags", []) or []
        lines.append("<h3>🕸️ 数据画像维度</h3>")
        if radar_chart:
            lines.append(
                "<p style='margin:8px 0 12px 0;'>"
                "<img alt='画像雷达图' src='"
                + html.escape(radar_chart, quote=True)
                + "' style='max-width:520px;width:100%;'/>"
                "</p>"
            )
        elif dimensions:
            sorted_dimensions = sorted(
                dimensions.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            dim_parts = [f"{html.escape(dim)}：{score}" for dim, score in sorted_dimensions]
            lines.append("<p>、".join(dim_parts) + "</p>")
        else:
            lines.append("<p>暂无可用数据画像维度。</p>")

        lines.append("<h3>🔎 关键证据</h3>")
        if evidence_tags:
            evidence_parts = [
                f"{html.escape(str(tag))}（{int(round(weight * 100))}%）"
                for tag, weight in evidence_tags
            ]
            lines.append("<p>高频标签： " + "、".join(evidence_parts) + "</p>")
        else:
            lines.append("<p>高频标签：暂无</p>")

        if active_hours:
            hour_parts = [f"{hour}:00（{count}次）" for hour, count in active_hours[:5]]
            lines.append("<p>活跃时段： " + "、".join(hour_parts) + "</p>")
        else:
            lines.append("<p>活跃时段：暂无</p>")

        if top_images:
            lines.append("<h3>🏆 最爱的表情 Top 5</h3><ol>")
            for _, name, count in top_images:
                lines.append(f"<li>{html.escape(str(name))}（使用 {count} 次）</li>")
            lines.append("</ol>")

        if top_tags:
            lines.append("<h3>🏷️ 高频标签 Top 10</h3><p>")
            tag_parts = [f"{html.escape(str(tag))}（{count}次）" for tag, count in top_tags]
            lines.append("、".join(tag_parts))
            lines.append("</p>")

        lines.append("<hr><p style='color:#888;font-size:12px;'>报告由表情工坊自动生成 ✨</p>")

        return "\n".join(lines)
