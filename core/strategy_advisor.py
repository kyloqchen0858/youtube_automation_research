"""
Strategy Advisor — 阶段目标与盈利建议生成模块
基于竞品数据分析，生成 0→1000 订阅路线图、盈利模式建议、内容策略
"""

import logging
from datetime import datetime
import math
from typing import Optional

import pandas as pd
import numpy as np

from core.cold_start_executor import generate_executable_cold_start_plan
from core.insight_validator import summarize_reliability, validate_duration_recommendation
from core.reverse_engineering import build_reverse_engineering_playbook
from core.strategy_models import (
    ContentDirection,
    PrimaryGoal,
    StrategyBrief,
    StrategyCheckpoint,
    StrategyPlan,
)

logger = logging.getLogger(__name__)


def _resolve_output_language(value: StrategyBrief | str | None) -> str:
    if isinstance(value, StrategyBrief):
        value = value.output_language
    return "en" if str(value or "").lower().startswith("en") else "zh"


def _t(language: StrategyBrief | str | None, zh: str, en: str) -> str:
    return en if _resolve_output_language(language) == "en" else zh


def generate_milestone_plan(
    channels_data: dict,
    niche_description: str = "",
    target_subscribers: int = 1000,
    strategy_brief: Optional[StrategyBrief] = None,
    radar_results: Optional[dict] = None,
    reverse_engineering_playbook: Optional[dict] = None,
    transcript_insights: Optional[dict] = None,
) -> dict:
    return generate_strategy_plan(
        channels_data=channels_data,
        niche_description=niche_description,
        target_subscribers=target_subscribers,
        strategy_brief=strategy_brief,
        radar_results=radar_results,
        reverse_engineering_playbook=reverse_engineering_playbook,
        transcript_insights=transcript_insights,
    )


def generate_strategy_plan(
    channels_data: dict,
    niche_description: str = "",
    target_subscribers: int = 1000,
    strategy_brief: Optional[StrategyBrief] = None,
    radar_results: Optional[dict] = None,
    reverse_engineering_playbook: Optional[dict] = None,
    transcript_insights: Optional[dict] = None,
) -> dict:
    """
    生成阶段性增长路线图

    Returns:
        {
            'milestones': [...],          # 阶段目标列表
            'estimated_timeline': str,    # 预估达标时间
            'key_metrics': {...},         # 关键指标参考值
            'niche_insights': str,        # 赛道特征总结
        }
    """
    radar_results = radar_results or {}
    strategy_brief = strategy_brief or StrategyBrief(niche=niche_description)
    reverse_engineering_playbook = reverse_engineering_playbook or build_reverse_engineering_playbook(
        brief=strategy_brief,
        radar_results=radar_results,
        transcript_insights=transcript_insights or {},
    )

    # 从竞品数据中提取参考值
    all_videos = []
    channel_stats = []
    for ch_id, data in channels_data.items():
        videos_df = data.get("videos", pd.DataFrame())
        info = data.get("info", {})
        if not videos_df.empty:
            all_videos.append(videos_df)
        if info:
            channel_stats.append(info)

    # 赛道平均指标
    avg_views_per_video = 0
    avg_engagement = 0
    avg_duration = 0
    if all_videos:
        combined = pd.concat(all_videos, ignore_index=True)
        avg_views_per_video = int(combined["view_count"].mean())
        if "engagement_rate" in combined.columns:
            avg_engagement = combined["engagement_rate"].mean()
        if "duration_minutes" in combined.columns:
            avg_duration = combined["duration_minutes"].mean()

    # 估算达标时间（基于赛道平均增速）
    top_channels = radar_results.get("top_channels", []) or []
    top_videos = radar_results.get("top_videos", []) or []
    reliable_channels = [
        data for data in channels_data.values()
        if data.get("growth", {}).get("reliable")
    ]
    translate = lambda zh, en: _t(strategy_brief, zh, en)

    # 粗略估算：根据 primary_goal 做保守换算
    subs_per_video_ratio = _subs_per_video_ratio(strategy_brief)
    if avg_views_per_video > 0:
        estimated_subs_per_video = int(avg_views_per_video * subs_per_video_ratio)
    else:
        estimated_subs_per_video = 10

    videos_needed = max(1, target_subscribers // max(estimated_subs_per_video, 1))
    cadence_long, cadence_support = _weekly_output_profile(strategy_brief)
    videos_per_month = max(cadence_long * 4, 1)
    estimated_months = max(2, math.ceil(videos_needed / videos_per_month))

    milestones = _build_checkpoints(
        brief=strategy_brief,
        playbook=reverse_engineering_playbook,
        avg_duration=avg_duration,
        avg_views_per_video=avg_views_per_video,
        target_subscribers=target_subscribers,
    )
    checkpoint_rules = _build_checkpoint_rules(strategy_brief)
    weekly_operating_rules = _build_weekly_rules(strategy_brief, reverse_engineering_playbook, cadence_long, cadence_support)
    confidence_notes = _build_confidence_notes(top_channels, reliable_channels, transcript_insights, reverse_engineering_playbook, strategy_brief)
    recommended_formats = reverse_engineering_playbook.get("dominant_formats", []) or strategy_brief.format_preferences or ["unknown"]
    lead_channel = top_channels[0] if top_channels else {}
    lead_video = top_videos[0] if top_videos else {}

    plan = StrategyPlan(
        north_star_goal=_north_star_goal(strategy_brief, target_subscribers),
        estimated_timeline=translate(
            f"预估 {estimated_months}-{estimated_months + 2} 个月达到 {target_subscribers} 订阅",
            f"Estimated {estimated_months}-{estimated_months + 2} months to reach {target_subscribers} subscribers",
        ),
        key_metrics={
            translate("赛道平均播放量", "Average Views per Video"): f"{avg_views_per_video:,}",
            translate("赛道平均互动率", "Average Engagement Rate"): f"{avg_engagement:.2%}",
            translate("赛道平均视频时长", "Average Video Length"): translate(f"{avg_duration:.0f} 分钟", f"{avg_duration:.0f} min"),
            translate("预估每视频新增订阅", "Estimated Subs per Video"): f"~{estimated_subs_per_video}",
            translate("达标所需视频数(估)", "Estimated Videos Needed"): f"~{videos_needed}",
            translate("雷达短名单", "Radar Shortlist"): f"{len(top_channels)} channels",
            translate("主导内容格式", "Dominant Format"): recommended_formats[0] if recommended_formats else "unknown",
        },
        milestones=[item.to_dict() for item in milestones],
        checkpoint_rules=checkpoint_rules,
        weekly_operating_rules=weekly_operating_rules,
        confidence_notes=confidence_notes,
        recommended_formats=recommended_formats,
        strategy_source_summary={
            "shortlisted_channels": len(top_channels),
            "reliable_channels": len(reliable_channels),
            "lead_channel": lead_channel.get("channel_title", ""),
            "lead_video": lead_video.get("title", ""),
            "channel_archetype": reverse_engineering_playbook.get("channel_archetype", ""),
        },
        niche_insights=_niche_insights(niche_description, reverse_engineering_playbook, strategy_brief),
    )
    return plan.to_dict()


def estimate_monetization(
    target_subscribers: int = 1000,
    avg_views_per_video: int = 1000,
    niche_cpm: float = 5.0,
    videos_per_month: int = 8,
    output_language: str = "zh",
) -> dict:
    """
    盈利模式分析

    Args:
        target_subscribers: 目标订阅数
        avg_views_per_video: 平均每视频播放量
        niche_cpm: 赛道 CPM（每千次播放广告收入，美元）
        videos_per_month: 每月视频数

    Returns:
        各盈利渠道的预估收入
    """
    monthly_views = avg_views_per_video * videos_per_month

    # 1. AdSense 广告收入
    # CPM 范围：教育/商业类通常 $3-$10
    adsense_low = monthly_views / 1000 * (niche_cpm * 0.6)
    adsense_mid = monthly_views / 1000 * niche_cpm
    adsense_high = monthly_views / 1000 * (niche_cpm * 1.5)

    # 2. 知识付费
    # 假设转化漏斗：观众 → 0.5% 点击链接 → 20% 注册免费资源 → 5% 购买
    monthly_visitors = monthly_views * 0.005
    free_signups = monthly_visitors * 0.20
    paid_conversions = free_signups * 0.05
    translate = lambda zh, en: _t(output_language, zh, en)

    course_prices = [
        {"name": translate("迷你课程", "Mini Course"), "price": 29, "conversions": paid_conversions},
        {"name": translate("完整课程", "Full Course"), "price": 99, "conversions": paid_conversions * 0.3},
        {"name": translate("高端咨询", "1-on-1 Coaching"), "price": 299, "conversions": max(1, paid_conversions * 0.05)},
    ]

    # 3. 频道会员
    # 假设 1-2% 的订阅者成为付费会员
    membership_rate = 0.015
    members = int(target_subscribers * membership_rate)
    membership_revenue = members * 4.99 * 0.7  # YouTube 抽成 30%

    # 4. Super Chat / Thanks
    # 高度不确定，给个保守估计
    super_chat = monthly_views / 10000 * 2  # 每万播放约 $2

    # 5. 联盟营销
    # 假设 0.1% 的观众通过联盟链接购买
    affiliate_conversions = monthly_views * 0.001
    affiliate_revenue = affiliate_conversions * 5  # 平均每单佣金 $5

    return {
        "monthly_views": monthly_views,
        "adsense": {
            "low": round(adsense_low, 2),
            "mid": round(adsense_mid, 2),
            "high": round(adsense_high, 2),
            "note": translate(f"基于赛道 CPM ${niche_cpm:.1f} 估算", f"Estimated using niche CPM ${niche_cpm:.1f}"),
        },
        "knowledge_products": [
            {
                "name": p["name"],
                "price": p["price"],
                "monthly_sales": round(p["conversions"], 1),
                "monthly_revenue": round(p["price"] * p["conversions"], 2),
            }
            for p in course_prices
        ],
        "membership": {
            "members": members,
            "monthly_revenue": round(membership_revenue, 2),
            "note": translate(
                f"假设 {membership_rate:.1%} 订阅者转为月费会员 ($4.99/月)",
                f"Assumes {membership_rate:.1%} of subscribers convert to paid members ($4.99/mo)",
            ),
        },
        "super_chat": {
            "monthly_revenue": round(super_chat, 2),
        },
        "affiliate": {
            "monthly_revenue": round(affiliate_revenue, 2),
            "note": translate("联盟营销（推荐书籍/工具/课程）", "Affiliate revenue (books / tools / courses)"),
        },
        "total_estimated": {
            "low": round(adsense_low + sum(p["price"] * p["conversions"] * 0.5 for p in course_prices) + membership_revenue, 2),
            "mid": round(adsense_mid + sum(p["price"] * p["conversions"] for p in course_prices) + membership_revenue + affiliate_revenue, 2),
            "high": round(adsense_high + sum(p["price"] * p["conversions"] * 1.5 for p in course_prices) + membership_revenue + affiliate_revenue + super_chat, 2),
        },
    }


def suggest_content_strategy(
    top_videos_df: pd.DataFrame,
    title_keywords: dict[str, float],
    duration_analysis: dict,
    publish_patterns: dict,
    niche_description: str = "",
    channels_data: Optional[dict] = None,
    user_keywords: Optional[list[str]] = None,
    strategy_brief: Optional[StrategyBrief] = None,
    radar_results: Optional[dict] = None,
    reverse_engineering_playbook: Optional[dict] = None,
) -> dict:
    """
    基于数据生成内容策略建议

    Returns:
        {
            'title_formulas': [...],        # 标题公式模板
            'content_themes': [...],        # 推荐内容主题
            'optimal_duration': str,        # 最佳时长建议
            'publish_schedule': str,        # 发布节奏建议
            'thumbnail_tips': [...],        # 缩略图建议
            'seo_keywords': [...],          # SEO 关键词建议
        }
    """
    strategy_brief = strategy_brief or StrategyBrief(niche=niche_description)
    radar_results = radar_results or {}
    translate = lambda zh, en: _t(strategy_brief, zh, en)
    reverse_engineering_playbook = reverse_engineering_playbook or build_reverse_engineering_playbook(
        brief=strategy_brief,
        radar_results=radar_results,
        transcript_insights={},
        top_videos_df=top_videos_df,
    )

    # 标题公式提取
    title_formulas = list(dict.fromkeys(
        reverse_engineering_playbook.get("winning_title_formulas", []) + _extract_title_patterns(top_videos_df, strategy_brief)
    ))

    # 内容主题建议
    top_keywords = list(title_keywords.keys())[:15] if title_keywords else []
    content_themes = _playbook_content_themes(reverse_engineering_playbook, strategy_brief) + _generate_content_themes(top_keywords, niche_description, strategy_brief)

    # 最佳时长
    best_range = duration_analysis.get("best_range", "10-15m")
    optimal_duration = translate(
        f"建议视频时长：{best_range}（该时长区间平均播放量最高）",
        f"Recommended video length: {best_range} (this range delivered the strongest average views)",
    )

    # 发布节奏
    best_day = publish_patterns.get("best_day", "N/A")
    best_hour = publish_patterns.get("best_hour", 12)
    cadence_long, cadence_support = _weekly_output_profile(strategy_brief)
    publish_schedule = translate(
        (
            f"建议发布时间：{best_day} {best_hour}:00 UTC "
            f"（该时段对标频道视频平均播放量最高）\n"
            f"建议节奏：每周 {cadence_long} 个长视频 + {cadence_support} 个支持型内容"
        ),
        (
            f"Recommended publish time: {best_day} {best_hour}:00 UTC "
            f"(this slot produced the strongest average views in the benchmark set)\n"
            f"Suggested cadence: {cadence_long} long-form videos + {cadence_support} support pieces per week"
        ),
    )

    # 缩略图建议
    thumbnail_tips = _thumbnail_tips(strategy_brief)

    # SEO 关键词
    seo_keywords = top_keywords[:20]

    guided_keywords = [kw.strip() for kw in (user_keywords or []) if kw and kw.strip()]
    if guided_keywords:
        seo_keywords = list(dict.fromkeys(guided_keywords + seo_keywords))[:20]
        guided_themes = []
        for kw in guided_keywords[:5]:
            guided_themes.append({
                "theme": translate(f"关键词优先：{kw}", f"Keyword priority: {kw}"),
                "reason": translate("来自用户主动输入的内容方向，优先进入测试队列", "User-provided direction should enter the testing queue first"),
                "example_titles": [
                    f"How to Apply {kw} in Real Life",
                    f"{kw}: 3 Practical Lessons for Modern Creators",
                ],
            })
        content_themes = guided_themes + content_themes

    reliability_summary = summarize_reliability(channels_data) if channels_data else None
    consistency_check = validate_duration_recommendation(duration_analysis, channels_data) if channels_data else None
    painpoint_hypothesis = _infer_painpoint_hypothesis(guided_keywords, niche_description, strategy_brief)
    cold_start_plan = generate_executable_cold_start_plan(
        channels_data=channels_data or {},
        niche=niche_description,
        user_keywords=guided_keywords,
        count=12,
        output_language=strategy_brief.output_language,
    )

    return {
        "title_formulas": title_formulas,
        "content_themes": content_themes,
        "optimal_duration": optimal_duration,
        "publish_schedule": publish_schedule,
        "thumbnail_tips": thumbnail_tips,
        "seo_keywords": seo_keywords,
        "reliability_summary": reliability_summary,
        "consistency_check": consistency_check,
        "painpoint_hypothesis": painpoint_hypothesis,
        "cold_start_plan": cold_start_plan,
        "reverse_engineering_playbook": reverse_engineering_playbook,
        "weekly_operating_rules": _build_weekly_rules(strategy_brief, reverse_engineering_playbook, cadence_long, cadence_support),
        "confidence_notes": _build_confidence_notes(
            radar_results.get("top_channels", []) or [],
            [data for data in (channels_data or {}).values() if data.get("growth", {}).get("reliable")],
            None,
            reverse_engineering_playbook,
            strategy_brief,
        ),
    }


def _subs_per_video_ratio(strategy_brief: StrategyBrief) -> float:
    if strategy_brief.primary_goal == PrimaryGoal.SUBSCRIBER_CONVERSION.value:
        return 0.04
    if strategy_brief.primary_goal == PrimaryGoal.HIGH_RETENTION_LONGFORM.value:
        return 0.025
    return 0.03


def _weekly_output_profile(strategy_brief: StrategyBrief) -> tuple[int, int]:
    team_model = strategy_brief.production_constraints.get("team_model", "solo")
    if strategy_brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        return (2, 2) if team_model == "collab" else (1, 2)
    if strategy_brief.content_direction == ContentDirection.MIXED.value:
        return (2, 3)
    return (3, 3) if team_model == "collab" else (2, 3)


def _north_star_goal(strategy_brief: StrategyBrief, target_subscribers: int) -> str:
    translate = lambda zh, en: _t(strategy_brief, zh, en)
    if strategy_brief.primary_goal == PrimaryGoal.SUBSCRIBER_CONVERSION.value:
        return translate(
            f"在 {target_subscribers} 订阅目标之前，优先建立稳定的订阅转化和明确的频道承诺",
            f"Before reaching {target_subscribers} subscribers, prioritize a stable subscriber-conversion loop and a clear channel promise",
        )
    if strategy_brief.primary_goal == PrimaryGoal.HIGH_RETENTION_LONGFORM.value:
        return translate(
            f"在冲击 {target_subscribers} 订阅的同时，把长视频 retention 打磨成可复制的强项",
            f"While pushing toward {target_subscribers} subscribers, turn long-form retention into a repeatable strength",
        )
    return translate(
        f"在达到 {target_subscribers} 订阅前，先找到能持续产生突破播放的题材与包装组合",
        f"Before reaching {target_subscribers} subscribers, find topic and packaging combinations that can repeatedly produce breakout views",
    )


def _build_checkpoints(
    brief: StrategyBrief,
    playbook: dict,
    avg_duration: float,
    avg_views_per_video: int,
    target_subscribers: int,
) -> list[StrategyCheckpoint]:
    translate = lambda zh, en: _t(brief, zh, en)
    lead_format = (playbook.get("dominant_formats") or ["unknown"])[0]
    lead_topics = ", ".join(playbook.get("winning_topic_clusters", [])[:3]) or translate("短名单主题", "shortlisted topics")
    safe_duration = max(5, int(avg_duration * 0.8)) if avg_duration else 8

    checkpoint_1_actions = [
        translate(
            f"围绕 {lead_topics} 连续发布 4-6 个同一内容簇的视频，而不是平均分散题材",
            f"Publish 4-6 videos around the same {lead_topics} cluster instead of spreading effort evenly across topics",
        ),
        translate(
            f"优先使用 {lead_format} 作为首发形式，保留另一个轻量变体用于 A/B 测试",
            f"Lead with {lead_format} as the primary format and keep one lighter variant for A/B tests",
        ),
        translate(
            f"将视频时长控制在 {safe_duration}-{max(safe_duration + 3, 10)} 分钟，先验证 retention 再加长",
            f"Keep videos in the {safe_duration}-{max(safe_duration + 3, 10)} minute range and validate retention before making them longer",
        ),
        translate("每支视频开头 15 秒直接交付结果承诺，不先铺垫背景", "Use the first 15 seconds to deliver the result promise directly instead of opening with background context"),
    ]

    checkpoint_2_actions = [
        translate("观察前 6-8 支视频的点击和播放表现，把表现最强的主题簇和包装公式放大一倍", "Review click and view performance across the first 6-8 videos, then double down on the strongest topic clusters and packaging formulas"),
        translate("把雷达短名单里表现最稳定的标题公式写成可复用模板，而不是每次重新想标题", "Turn the most stable headline formulas from the radar shortlist into reusable templates instead of rewriting titles from scratch"),
        translate("开始建立系列感：每个视频在结尾明确指向下一个问题或下一个实验", "Build serial momentum: each video should point clearly to the next question or next experiment"),
        translate("把评论区高频问题整理为下一轮脚本输入，而不是只看播放量", "Convert repeated comment questions into the next scripting inputs instead of watching views alone"),
    ]

    checkpoint_3_actions = [
        translate("对表现最好的系列做封面、标题、开场结构微调，优先提升 CTR 与 30 秒留存", "Fine-tune thumbnails, titles, and opening structure on the best-performing series, prioritizing CTR and 30-second retention"),
        translate("把系列内容打包成 playlist 或可下载资源，开始测试订阅和邮件转化", "Package the strongest series into playlists or downloadable assets and start testing subscriber and email conversion"),
        translate("只在已有高表现格式上增加频率，不要同时扩展新格式和新主题", "Increase frequency only on formats that already perform; do not expand new formats and new topics at the same time"),
        translate("为后续变现准备素材库：案例、流程图、脚本模板、常见问题", "Prepare an asset library for monetization: cases, diagrams, script templates, and FAQs"),
    ]

    phase_1 = StrategyCheckpoint(
        phase=translate("阶段 1：模式发现期", "Phase 1: Pattern Discovery"),
        target=translate("先找到 1-2 个可重复的包装和选题组合", "Find 1-2 repeatable packaging and topic combinations first"),
        duration=translate("第 1-4 周", "Week 1-4"),
        actions=checkpoint_1_actions,
        kpi=translate(
            f"目标：每个视频达到赛道均播的 30%-50%（当前基准 {avg_views_per_video:,} views）",
            f"Target: each video reaches 30%-50% of niche-average views (current baseline {avg_views_per_video:,} views)",
        ),
        decision_rule=translate("如果连续 3 支视频都未达到基础播放预期，先换标题/开场，不要先换全部主题", "If 3 videos in a row miss the baseline, change the title and opening first instead of changing the whole topic set"),
        fallback_action=translate("减少题材面，回到雷达短名单里最强主题簇并只保留一个主格式", "Narrow the topic surface, return to the strongest radar-shortlist cluster, and keep only one main format"),
    )
    phase_2 = StrategyCheckpoint(
        phase=translate("阶段 2：放大验证期", "Phase 2: Double Down"),
        target=translate("从零散命中切换到稳定可复制的内容系统", "Shift from isolated wins to a stable repeatable content system"),
        duration=translate("第 5-8 周", "Week 5-8"),
        actions=checkpoint_2_actions,
        kpi=translate("目标：至少出现 2 支明显高于频道均值的内容，并形成系列化继续观看", "Target: produce at least 2 videos that clearly outperform the channel average and create follow-on viewing through a series"),
        decision_rule=translate("如果某一标题/格式组合连续两次达标，就停止平均测试，改为重点放大", "If one title/format combination clears the bar twice in a row, stop equal testing and scale it"),
        fallback_action=translate("保留主题不变，重新测试开头钩子与标题承诺，而不是立刻推翻整个方向", "Keep the topic, retest the opening hook and title promise, and do not scrap the whole direction immediately"),
    )
    phase_3 = StrategyCheckpoint(
        phase=translate("阶段 3：转化系统期", "Phase 3: Conversion System"),
        target=translate(f"冲击 {target_subscribers} 订阅并建立后续变现前置条件", f"Push toward {target_subscribers} subscribers while building the prerequisites for monetization"),
        duration=translate("第 9-12 周及以后", "Week 9-12+"),
        actions=checkpoint_3_actions,
        kpi=translate("目标：出现可连续复用的系列、稳定的发布节奏，以及明确的订阅/资源转化路径", "Target: establish reusable series, a stable publishing cadence, and a clear conversion path for subscribers or resources"),
        decision_rule=translate("只有在 CTR 与 retention 都稳定后，才增加发布频率或扩展新系列", "Increase publishing frequency or expand into new series only after CTR and retention are both stable"),
        fallback_action=translate("如果播放在增长但转化弱，优先优化频道承诺、CTA 与系列衔接，而不是单纯加量", "If views rise but conversion stays weak, improve the channel promise, CTA, and series linkage before increasing volume"),
    )

    return [phase_1, phase_2, phase_3]


def _build_checkpoint_rules(strategy_brief: StrategyBrief) -> list[dict[str, str]]:
    translate = lambda zh, en: _t(strategy_brief, zh, en)
    rules = [
        {
            "checkpoint": translate("前 3 支视频", "First 3 videos"),
            "decision_rule": translate("低于基础预期时先改标题和前 15 秒，不先换赛道", "If performance misses the baseline, change the title and first 15 seconds before changing the niche"),
            "fallback_action": translate("保留主题簇，仅切换包装和承诺句", "Keep the topic cluster and change only the packaging and promise line"),
        },
        {
            "checkpoint": translate("前 6-8 支视频", "First 6-8 videos"),
            "decision_rule": translate("当某组主题+格式连续 2 次有效时，停止平均测试并集中放大", "When one topic-plus-format combo works twice in a row, stop equal testing and concentrate on it"),
            "fallback_action": translate("删除最弱的 50% 主题，留下最强内容树继续加深", "Cut the weakest 50% of topics and deepen only the strongest content tree"),
        },
        {
            "checkpoint": translate("系列验证阶段", "Series validation stage"),
            "decision_rule": translate("只有在点击和留存都稳定后，才增加频率或增加新形式", "Increase frequency or add new formats only when click-through and retention are both stable"),
            "fallback_action": translate("保留强系列，把支持型内容降到最低成本形式", "Keep the strong series and reduce support content to the lowest-cost format"),
        },
    ]

    if strategy_brief.primary_goal == PrimaryGoal.HIGH_RETENTION_LONGFORM.value:
        rules[0]["decision_rule"] = translate("优先观察开场留存和结构清晰度，低留存时不要先追求更多题材", "Prioritize opening retention and structural clarity; when retention is low, do not chase more topics first")
        rules[1]["fallback_action"] = translate("压缩长度、加强结构标记，再测试同题材而不是立刻换题", "Shorten the video and strengthen structural signposting before changing the topic")
    return rules


def _build_weekly_rules(
    strategy_brief: StrategyBrief,
    playbook: dict,
    cadence_long: int,
    cadence_support: int,
) -> list[str]:
    translate = lambda zh, en: _t(strategy_brief, zh, en)
    lead_format = (playbook.get("dominant_formats") or ["unknown"])[0]
    rules = [
        translate(
            f"每周固定产出 {cadence_long} 个长视频和 {cadence_support} 个支持型内容，避免靠临时灵感决定发什么",
            f"Ship {cadence_long} long-form videos and {cadence_support} support pieces every week instead of deciding output from temporary inspiration",
        ),
        translate(
            f"优先用 {lead_format} 做主格式，其他形式只作为测试变量而不是主线",
            f"Use {lead_format} as the primary format; other forms should be test variables, not the main line",
        ),
        translate("每周至少复盘一次：看标题承诺、开场钩子、主题簇，而不是只看总播放量", "Run at least one weekly review focused on the title promise, opening hook, and topic cluster instead of total views alone"),
    ]
    if strategy_brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        rules.append(translate("每支视频都要有可见的里程碑、约束或决策，不要把 build in public 做成泛成长鸡汤", "Each video should include a visible milestone, constraint, or decision. Do not let build in public drift into vague motivational content"))
    else:
        rules.append(translate("教程类视频必须先展示结果或收益，再进入步骤解释，否则冷启动阶段很难拿到点击", "Tutorial videos should show the result or payoff first and only then explain the steps, otherwise cold-start click-through will stay weak"))
    return rules


def _build_confidence_notes(
    top_channels: list[dict],
    reliable_channels: list[dict],
    transcript_insights: Optional[dict],
    playbook: dict,
    strategy_brief: Optional[StrategyBrief] = None,
) -> list[str]:
    translate = lambda zh, en: _t(strategy_brief, zh, en)
    notes = list(playbook.get("confidence_notes", []))
    if top_channels:
        notes.append(translate(f"当前策略主要参考 {len(top_channels)} 个雷达短名单频道", f"This strategy is primarily grounded in {len(top_channels)} radar-shortlisted channels"))
    if reliable_channels:
        notes.append(translate(f"其中 {len(reliable_channels)} 个频道具备可靠增长窗口数据", f"{len(reliable_channels)} of those channels include reliable growth-window data"))
    if transcript_insights and transcript_insights.get("has_data"):
        notes.append(translate("策略同时参考了 transcript hook/structure 模式，因此结构建议置信度更高", "Transcript hook and structure patterns also informed the strategy, so structure recommendations have higher confidence"))
    return list(dict.fromkeys(notes))[:4]


def _niche_insights(niche_description: str, playbook: dict, strategy_brief: Optional[StrategyBrief] = None) -> str:
    archetype = playbook.get("channel_archetype", "")
    if archetype and niche_description:
        return _t(strategy_brief, f"{niche_description} | 当前最强竞品原型：{archetype}", f"{niche_description} | Current lead competitor archetype: {archetype}")
    return niche_description or archetype


def _playbook_content_themes(playbook: dict, strategy_brief: Optional[StrategyBrief] = None) -> list[dict]:
    themes = []
    for cluster in playbook.get("winning_topic_clusters", [])[:4]:
        themes.append({
            "theme": _t(strategy_brief, f"围绕「{cluster}」做连续内容簇", f"Build a continuous content cluster around \"{cluster}\""),
            "reason": _t(strategy_brief, "来自雷达短名单爆发视频的重复主题信号", "Repeated topic signal from breakout videos in the radar shortlist"),
            "example_titles": [
                f"How to Apply {cluster} in a Real Creator Workflow",
                f"{cluster}: The Next Experiment to Run on Your Channel",
            ],
        })
    return themes


def _thumbnail_tips(strategy_brief: StrategyBrief) -> list[str]:
    translate = lambda zh, en: _t(strategy_brief, zh, en)
    if strategy_brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        return [
            translate("用时间盒、里程碑或结果数字做主视觉，而不是泛化情绪图", "Use time-boxes, milestones, or result numbers as the primary visual instead of generic emotional imagery"),
            translate("封面上只保留一个核心承诺，例如 Week 3、30 Days、First $100", "Keep only one core promise on the thumbnail, such as Week 3, 30 Days, or First $100"),
            translate("优先展示产品界面、图表或结果物，少用与内容无关的装饰元素", "Prioritize product UI, charts, or concrete outputs and avoid decorative elements unrelated to the content"),
            translate("保持每个系列的版式一致，让观众一眼识别进度线", "Keep the layout consistent across each series so viewers recognize the progress line instantly"),
        ]
    return [
        translate("优先展示最终产出画面或工作流结果，而不是空泛的人脸情绪图", "Show the final output or workflow result first instead of generic face-reaction imagery"),
        translate("文字不超过 4-6 个词，突出结果、时间节省或自动化收益", "Keep text to 4-6 words and emphasize results, time saved, or automation payoff"),
        translate("UI 截图要放大关键区域，避免整屏缩略导致手机端不可读", "Zoom into the key area in UI screenshots so mobile viewers can still read them"),
        translate("把缩略图当作承诺页：一眼说明视频解决什么问题", "Treat the thumbnail as a promise page: make the solved problem obvious at a glance"),
    ]


def _infer_painpoint_hypothesis(user_keywords: list[str], niche_description: str, strategy_brief: Optional[StrategyBrief] = None) -> dict:
    joined = " ".join(user_keywords).lower()
    translate = lambda zh, en: _t(strategy_brief, zh, en)

    if "拖延" in "".join(user_keywords) or "procrast" in joined:
        return {
            "primary": translate("执行瘫痪：知道该做什么，但迟迟无法开始与持续", "Execution paralysis: people know what to do, but cannot start or sustain it"),
            "secondary": [
                translate("拖延后的自责循环，降低自我效能感", "Self-blame loops after procrastination reduce self-efficacy"),
                translate("任务拆解不足，启动门槛过高", "Tasks are not decomposed well enough, so the starting threshold stays too high"),
                translate("分心环境导致注意力断裂", "Distracting environments keep breaking attention"),
            ],
            "content_goal": translate("提供可当天执行的最小行动步骤，而不是抽象励志", "Provide the smallest actionable steps that can be used today instead of abstract motivation"),
        }

    return {
        "primary": translate("目标与执行系统不匹配，导致行动效率低", "Goals and execution systems are misaligned, which drags down execution efficiency"),
        "secondary": [
            translate("缺乏稳定复盘机制", "There is no stable review loop"),
            translate("策略不具体，难以落地", "The strategy is too vague to execute"),
        ],
        "content_goal": translate(
            f"围绕 {niche_description or '用户核心诉求'} 输出可执行策略",
            f"Produce executable guidance around {niche_description or 'the user\'s core demand'}",
        ),
    }


def _extract_title_patterns(top_videos_df: pd.DataFrame, strategy_brief: Optional[StrategyBrief] = None) -> list[str]:
    """从高播放量视频标题中提取标题公式"""
    formulas = []
    translate = lambda zh, en: _t(strategy_brief, zh, en)

    if top_videos_df.empty:
        return [
            translate('"How [persona] Uses [tool/system] to Get [result]" — 例：How Creators Use AI Agents to Ship Faster', '"How [persona] Uses [tool/system] to Get [result]" — Example: How Creators Use AI Agents to Ship Faster'),
            translate('"[Number] [workflow/tool] Rules for [use case]" — 例：7 Cursor Workflow Rules for Solo Operators', '"[Number] [workflow/tool] Rules for [use case]" — Example: 7 Cursor Workflow Rules for Solo Operators'),
            translate('"Why [common approach] Fails — [better system] Explains" — 例：Why Prompt Chaos Fails — A Better AI Workflow', '"Why [common approach] Fails — [better system] Explains" — Example: Why Prompt Chaos Fails — A Better AI Workflow'),
            translate('"[Tool/Framework] Guide to [pain point]" — 例：A Practical Guide to AI Research Workflows', '"[Tool/Framework] Guide to [pain point]" — Example: A Practical Guide to AI Research Workflows'),
            '"I Tried [workflow] for 30 Days — Here\'s What Happened"',
        ]

    titles = top_videos_df["title"].tolist()

    # 检测常见模式
    number_pattern = sum(1 for t in titles if any(c.isdigit() for c in t))
    question_pattern = sum(1 for t in titles if "?" in t or "how" in t.lower() or "why" in t.lower())
    list_pattern = sum(1 for t in titles if any(w in t.lower() for w in ["top", "best", "rules", "steps", "ways", "tips"]))

    if number_pattern > len(titles) * 0.3:
        formulas.append(translate('"[数字] + [关键词] + [结果承诺]" — 数字型标题在本赛道表现突出', '"[Number] + [keyword] + [result promise]" — number-led titles are outperforming in this niche'))
    if question_pattern > len(titles) * 0.3:
        formulas.append(translate('"How/Why + [反直觉观点]?" — 疑问型标题吸引好奇心点击', '"How/Why + [counterintuitive angle]?" — question-led titles are pulling curiosity clicks'))
    if list_pattern > len(titles) * 0.2:
        formulas.append(translate('"Top/Best [N] [策略] for [场景]" — 清单型标题自带明确价值预期', '"Top/Best [N] [strategy] for [context]" — list-style titles carry a clear value promise'))

    # 通用高效公式
    formulas.extend([
        '"[Tool/System] + [specific bottleneck]" — 例：How I Use Claude to Turn Research into Scripts',
        translate('"I Applied [workflow/system] — The Results Were..." — 个人实验体叙事', '"I Applied [workflow/system] — The Results Were..." — personal experiment narrative'),
        translate('"[痛点关键词] — [可复制解法]" — 先戳痛点再给方案', '"[pain-point keyword] — [repeatable fix]" — surface the pain point before the solution'),
    ])

    return formulas[:6]


def _generate_content_themes(top_keywords: list[str], niche: str, strategy_brief: Optional[StrategyBrief] = None) -> list[dict]:
    """基于高频关键词生成内容主题建议"""
    themes = []
    translate = lambda zh, en: _t(strategy_brief, zh, en)

    # 基于关键词组合生成选题
    if top_keywords:
        for i in range(0, min(len(top_keywords), 10), 2):
            kw1 = top_keywords[i]
            kw2 = top_keywords[i + 1] if i + 1 < len(top_keywords) else ""
            themes.append({
                "theme": translate(f"围绕「{kw1}」+「{kw2}」的内容", f"Content around \"{kw1}\" + \"{kw2}\""),
                "reason": translate("赛道高频关键词组合，搜索需求已验证", "High-frequency keyword pairing in the niche with validated search demand"),
                "example_titles": [
                    translate(f"'{kw1}' 的 5 条{kw2 if kw2 else '核心'}法则", f"5 {kw2 if kw2 else 'core'} rules for '{kw1}'"),
                    f"Why '{kw1}' Is the Secret to {kw2 if kw2 else 'Success'}",
                ],
            })

    # 通用选题建议（教程 / workflow / build in public）
    universal_themes = [
        {
            "theme": translate("工作流拆解系列", "Workflow teardown series"),
            "reason": translate("把复杂任务拆成可复制步骤，最容易建立新观众的信任感", "Breaking complex tasks into repeatable steps builds trust with new viewers fastest"),
            "example_titles": [
                "The AI Research Workflow I Use Before Writing Any Script",
                "How I Turn One Prompt into a Full Content System",
            ],
        },
        {
            "theme": translate("「一个工具解决一个瓶颈」系列", "One tool solves one bottleneck series"),
            "reason": translate("每期聚焦一个明确问题和一套具体工具，转化为收藏与搜索流量都更直接", "Each episode focuses on one clear problem and one concrete tool stack, which translates more directly into saves and search traffic"),
            "example_titles": [
                "The Best AI Stack for Turning Notes into YouTube Scripts",
                "One Automation That Saves Me 5 Hours Every Week",
            ],
        },
        {
            "theme": translate("反常识/颠覆认知系列", "Contrarian insight series"),
            "reason": translate("用结果导向的对比挑战观众旧做法，容易形成高点击的认知反差", "Challenge the audience's old method with a results-led contrast to create strong click-driving tension"),
            "example_titles": [
                "Why Most AI Tutorials Waste Your Time",
                "Stop Collecting Tools. Build One Workflow Instead.",
            ],
        },
    ]
    themes.extend(universal_themes)

    return themes[:8]
