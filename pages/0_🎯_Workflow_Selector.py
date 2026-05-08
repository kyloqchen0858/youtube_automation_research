"""
Page 0: Workflow Selector
工作流选择器 — v6 引导入口
"""

import streamlit as st

from core.strategy_models import (
    ContentDirection,
    PrimaryGoal,
    StrategyBrief,
    get_strategy_brief,
    sync_strategy_brief,
)

st.set_page_config(page_title="Workflow Selector", page_icon="🎯", layout="wide")

st.title("🎯 Workflow Selector / 工作流选择")
st.markdown("### 选择你的分析目标、交付模式与输出语言")
st.warning(
    "Current status: workflow settings, content direction, and primary goal now feed competitor ranking, "
    "candidate sampling, and downstream strategy source selection. Output language now drives app-side strategy text, report preview, and PDF export. "
    "Internal CLI AI-written analyses are still Chinese-first."
)

mode_options = {
    "Analysis Quality First / 策略可靠性优先": "analysis_quality",
    "Horizontal Benchmark / 横向对标": "horizontal_benchmark",
    "Vertical Channel Optimization / 频道纵向优化": "vertical_optimize",
    "Single Viral Deep-Dive / 单爆款深挖": "single_viral",
}

stage_options = {
    "Cold Start (0-100 subs) / 冷启动": "cold_start",
    "Growth (100-1000 subs) / 增长期": "growth",
    "Monetization (1000+ subs) / 变现期": "monetization",
    "Plateau Recovery / 平台期修复": "plateau",
}

language_options = {
    "中文": "zh",
    "English": "en",
}

delivery_options = {
    "One-time Report Access / 按次报告": "single_report",
    "Lifetime License / 买断长期授权": "lifetime_license",
}

content_direction_options = {
    "AI Tool Tutorials / AI 工具实战分享": ContentDirection.AI_TOOL_TUTORIAL.value,
    "Build in Public / 独立开发公开构建": ContentDirection.BUILD_IN_PUBLIC.value,
    "Mixed Strategy / 双线混合": ContentDirection.MIXED.value,
}

primary_goal_options = {
    "Breakout Growth / 爆发增长": PrimaryGoal.BREAKOUT_GROWTH.value,
    "Subscriber Conversion / 订阅转化": PrimaryGoal.SUBSCRIBER_CONVERSION.value,
    "High-Retention Longform / 长视频高完播": PrimaryGoal.HIGH_RETENTION_LONGFORM.value,
}

production_profile_options = {
    "Solo / 个人单打": "solo",
    "Collaborative / 小团队协作": "collab",
    "High Edit Load / 高剪辑负载": "high_edit",
}

current_brief = get_strategy_brief(st.session_state, niche_override=st.session_state.get("niche", ""))

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    selected_mode_label = st.radio(
        "1) Workflow Mode / 工作流模式",
        list(mode_options.keys()),
        index=list(mode_options.values()).index(st.session_state.get("workflow_mode", "analysis_quality"))
        if st.session_state.get("workflow_mode", "analysis_quality") in mode_options.values()
        else 0,
    )

    selected_stage_label = st.selectbox(
        "2) Channel Stage / 频道阶段",
        list(stage_options.keys()),
        index=list(stage_options.values()).index(current_brief.creator_stage)
        if current_brief.creator_stage in stage_options.values()
        else 0,
    )

    selected_direction_label = st.selectbox(
        "3) Content Direction / 内容方向",
        list(content_direction_options.keys()),
        index=list(content_direction_options.values()).index(current_brief.content_direction)
        if current_brief.content_direction in content_direction_options.values()
        else 0,
    )

with col2:
    selected_language_label = st.radio(
        "4) Output Language / 输出语言",
        list(language_options.keys()),
        index=list(language_options.values()).index(current_brief.output_language)
        if current_brief.output_language in language_options.values()
        else 0,
        horizontal=True,
    )

    selected_delivery_label = st.radio(
        "5) Delivery Mode / 交付模式",
        list(delivery_options.keys()),
        index=list(delivery_options.values()).index(current_brief.delivery_mode)
        if current_brief.delivery_mode in delivery_options.values()
        else 0,
    )

    selected_goal_label = st.selectbox(
        "6) Primary Goal / 主要目标",
        list(primary_goal_options.keys()),
        index=list(primary_goal_options.values()).index(current_brief.primary_goal)
        if current_brief.primary_goal in primary_goal_options.values()
        else 0,
    )

strategy_keywords_text = st.text_area(
    "7) Strategy Keywords / 策略关键词（可选）",
    value="\n".join(current_brief.strategy_keywords),
    placeholder="例如:\nai workflow tutorials\nai agents\ncreator systems\nscreen-recorded explainers",
    height=140,
    help="这些关键词会在后续策略生成中作为优先意图。",
)

format_preferences_text = st.text_area(
    "8) Format Preferences / 呈现形式偏好（可选）",
    value="\n".join(current_brief.format_preferences),
    placeholder="例如:\nscreen recording\nvoiceover\nslides\nanimation",
    height=110,
    help="这些偏好会进入第一阶段的竞品雷达打分。",
)

selected_production_label = st.selectbox(
    "9) Production Reality / 当前执行条件",
    list(production_profile_options.keys()),
    index=list(production_profile_options.values()).index(
        current_brief.production_constraints.get("team_model", "solo")
    )
    if current_brief.production_constraints.get("team_model", "solo") in production_profile_options.values()
    else 0,
)

st.markdown("---")
if st.button("💾 Save Workflow Setup / 保存工作流设置", type="primary", use_container_width=True):
    brief = StrategyBrief(
        brief_id=current_brief.brief_id,
        created_at=current_brief.created_at,
        content_direction=content_direction_options[selected_direction_label],
        creator_stage=stage_options[selected_stage_label],
        primary_goal=primary_goal_options[selected_goal_label],
        workflow_mode=mode_options[selected_mode_label],
        output_language=language_options[selected_language_label],
        delivery_mode=delivery_options[selected_delivery_label],
        niche=st.session_state.get("niche", ""),
        strategy_keywords=[kw.strip() for kw in strategy_keywords_text.split("\n") if kw.strip()],
        discovery_keywords=st.session_state.get("keywords", []),
        format_preferences=[item.strip() for item in format_preferences_text.split("\n") if item.strip()],
        production_constraints={"team_model": production_profile_options[selected_production_label]},
        channel_context=dict(current_brief.channel_context),
        success_definition={"primary_goal": primary_goal_options[selected_goal_label]},
    )
    sync_strategy_brief(st.session_state, brief)

    st.success("✅ Workflow setup saved. The active strategy brief will now drive phase-one competitor radar scoring.")

st.markdown("### Current Setup / 当前设置")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Mode", st.session_state.get("workflow_mode", "analysis_quality"))
m2.metric("Stage", st.session_state.get("creator_stage", "cold_start"))
m3.metric("Direction", st.session_state.get("content_direction", ContentDirection.AI_TOOL_TUTORIAL.value))
m4.metric("Goal", st.session_state.get("primary_goal", PrimaryGoal.BREAKOUT_GROWTH.value))

if st.session_state.get("niche"):
    st.caption(f"Linked niche: {st.session_state.get('niche')}")

if st.session_state.get("strategy_keywords"):
    st.markdown("**Strategy Keywords:** " + " | ".join(st.session_state.get("strategy_keywords", [])))

if st.session_state.get("format_preferences"):
    st.markdown("**Format Preferences:** " + " | ".join(st.session_state.get("format_preferences", [])))
