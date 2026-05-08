"""
Page 4: Download Report
下载报告 — PDF 预览 + 下载 + CSV 导出
"""

import io
import json
from datetime import datetime

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Download Report", page_icon="📥", layout="wide")

st.title("📥 Download Report / 下载报告")

# ── 前置检查 ────────────────────────────────────────────────
if not st.session_state.get("analysis_results"):
    st.warning("⚠️ Please run analysis first → **📊 Deep Analysis**")
    st.stop()

results = st.session_state.analysis_results
niche = st.session_state.get("niche", "youtube_niche")
monitor = st.session_state.get("analysis_monitor", {})
strategy_brief = results.get("strategy_brief", {})
output_language = "en" if str(strategy_brief.get("output_language", st.session_state.get("output_language", "zh"))).lower().startswith("en") else "zh"
t = lambda zh, en: en if output_language == "en" else zh

# ── Report Preview ──────────────────────────────────────────
st.markdown(f"### 📄 {t('报告预览', 'Report Preview')}")

plan = results.get("milestone_plan", {})
mon = results.get("monetization", {})
comparison_df = results.get("comparison_df", pd.DataFrame())
dur = results.get("duration_analysis", {})
pub = results.get("publish_patterns", {})
trust = results.get("reliability_summary", {})
consistency = results.get("duration_consistency", {})
transcript_insights = results.get("transcript_insights", {})

# Summary cards
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(t("分析频道数", "Channels Analyzed"), len(results.get("channels_data", {})))
col2.metric(t("扫描视频数", "Videos Scanned"), len(results.get("combined_df", [])))
col3.metric(t("采集评论数", "Comments Collected"), len(results.get("all_comments", [])))
col4.metric(t("分析字幕数", "Transcripts Analyzed"), len(results.get("transcripts", {})))

total = mon.get("total_estimated", {})
col5.metric(t("预估月收入", "Est. Monthly Revenue"), f"${total.get('mid', 0):,.0f}")

st.markdown("---")

# Key insights
st.markdown(f"### 🔍 {t('核心洞察', 'Key Insights')}")

insights_col1, insights_col2 = st.columns(2)

with insights_col1:
    st.markdown(f"**📊 {t('赛道指标', 'Niche Metrics')}**")
    metrics = plan.get("key_metrics", {})
    for k, v in metrics.items():
        st.markdown(f"- **{k}**: {v}")

    st.markdown(f"**⏱️ {t('观察到的更强时长区间', 'Observed Stronger Duration Range')}**: {dur.get('best_range', 'N/A')}")
    st.markdown(f"**📅 {t('样本中更常见的发布时间星期', 'Common Publish Day In Sample')}**: {pub.get('best_day', 'N/A')}")
    st.markdown(f"**🕐 {t('样本中更常见的发布时间点', 'Common Publish Hour In Sample')}**: {pub.get('best_hour', 'N/A')}:00 UTC")

    if transcript_insights.get("has_data"):
        top_hook = transcript_insights.get("hook_patterns", [])
        top_structure = transcript_insights.get("structure_patterns", [])
        if top_hook:
            st.markdown(f"**🧠 {t('主导 Hook', 'Dominant Hook')}**: {top_hook[0].get('label', 'N/A')}")
        if top_structure:
            st.markdown(f"**🧩 {t('主导结构', 'Dominant Structure')}**: {top_structure[0].get('label', 'N/A')}")

with insights_col2:
    st.markdown(f"**⏰ {t('增长时间线', 'Growth Timeline')}**")
    st.markdown(f"_{plan.get('estimated_timeline', 'N/A')}_")

    if trust:
        st.markdown(f"**🛡️ {t('数据可信度', 'Data Trust')}**")
        st.markdown(
            f"- {t('可靠频道', 'Reliable channels')}: {trust.get('reliable_channels', 0)}/{trust.get('total_channels', 0)}"
        )
        st.markdown(f"- {t('平均可靠性评分', 'Avg reliability score')}: {trust.get('average_score', 0)}/100")

    st.markdown(f"**💰 {t('收入区间', 'Revenue Range')}**")
    st.markdown(f"- {t('低', 'Low')}: ${total.get('low', 0):,.0f}/mo")
    st.markdown(f"- {t('中', 'Mid')}: ${total.get('mid', 0):,.0f}/mo")
    st.markdown(f"- {t('高', 'High')}: ${total.get('high', 0):,.0f}/mo")

    if transcript_insights.get("has_data"):
        coverage = transcript_insights.get("coverage", {})
        st.markdown(f"**📝 {t('字幕覆盖情况', 'Transcript Coverage')}**")
        st.markdown(f"- {t('视频数', 'Videos')}: {coverage.get('analyzed_videos', 0)}")
        st.markdown(f"- {t('频道数', 'Channels')}: {coverage.get('analyzed_channels', 0)}")
        st.markdown(f"- {t('解析词数', 'Words parsed')}: {coverage.get('total_words', 0):,}")

if consistency.get("has_conflict"):
    issues = consistency.get("issues", [])
    if issues:
        st.warning(f"{t('策略一致性预警', 'Strategy consistency warning')}: {issues[0]}")

# Channel comparison table
if not comparison_df.empty:
    st.markdown(f"### 📊 {t('频道对比', 'Channel Comparison')}")
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

# TOP 5 engagement titles
st.markdown(f"### 🏆 {t('高互动标题 TOP 5', 'Top Engagement Titles')}")
top_eng = results.get("top_engagement", pd.DataFrame())
if not top_eng.empty:
    for i, (_, v) in enumerate(top_eng.head(5).iterrows(), 1):
        eng = v.get("engagement_rate", 0)
        views = v.get("view_count", 0)
        st.markdown(
            f"{i}. **{v['title']}** — {t('播放量', 'Views')}: {views:,} | {t('互动率', 'Engagement')}: {eng:.2%}"
        )

# ── Download Buttons ────────────────────────────────────────
st.markdown("---")
st.markdown(f"### 📥 {t('下载导出', 'Downloads')}")

download_col1, download_col2, download_col3, download_col4 = st.columns(4)

# PDF Report
with download_col1:
    report_bytes = st.session_state.get("report_bytes")
    if report_bytes:
        safe_niche = "".join(c if c.isalnum() or c in " _-" else "_" for c in niche)
        filename = f"YouTube_Research_{safe_niche}_{datetime.now().strftime('%Y%m%d')}.pdf"

        st.download_button(
            label=f"📄 {t('下载 PDF 报告', 'Download PDF Report')}",
            data=report_bytes,
            file_name=filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
        st.caption(f"{t('文件', 'File')}: {filename}")
    else:
        st.warning(t("PDF 报告尚未生成，请重新运行分析。", "PDF report not generated. Re-run analysis."))

# Videos CSV
with download_col2:
    combined_df = results.get("combined_df", pd.DataFrame())
    if not combined_df.empty:
        csv_buffer = io.StringIO()
        export_cols = [c for c in combined_df.columns if c != "thumbnail"]
        combined_df[export_cols].to_csv(csv_buffer, index=False, encoding="utf-8-sig")

        st.download_button(
            label=f"📊 {t('下载视频 CSV', 'Download Videos CSV')}",
            data=csv_buffer.getvalue(),
            file_name=f"videos_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption(f"{len(combined_df)} {t('条视频', 'videos')}")

# Comments CSV
with download_col3:
    comments = results.get("all_comments", [])
    if comments:
        comments_df = pd.DataFrame(comments)
        csv_buffer = io.StringIO()
        comments_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")

        st.download_button(
            label=f"💬 {t('下载评论 CSV', 'Download Comments CSV')}",
            data=csv_buffer.getvalue(),
            file_name=f"comments_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption(f"{len(comments)} {t('条评论', 'comments')}")
    else:
        st.info(t("没有采集到评论", "No comments collected"))

# Transcript JSON
with download_col4:
    transcripts = results.get("transcripts", {})
    transcript_info = results.get("transcript_video_info", {})
    if transcripts:
        transcript_export = {
            vid_id: {
                "title": transcript_info.get(vid_id, {}).get("title", ""),
                "channel": transcript_info.get(vid_id, {}).get("channel_title", ""),
                "views": transcript_info.get(vid_id, {}).get("view_count", 0),
                "text": text,
            }
            for vid_id, text in transcripts.items()
        }
        st.download_button(
            label=f"📝 {t('下载字幕 JSON', 'Download Transcripts JSON')}",
            data=json.dumps(transcript_export, ensure_ascii=False, indent=2),
            file_name=f"transcripts_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption(f"{len(transcripts)} {t('份字幕', 'transcripts')}")
    else:
        st.info(t("没有采集到字幕", "No transcripts collected"))

# ── Report Structure Preview ────────────────────────────────
st.markdown("---")
st.markdown(f"### 📑 {t('PDF 结构预览', 'PDF Report Structure')}")
if output_language == "en":
    st.markdown("""
The PDF report contains 8 chapters:

| Chapter | Content |
|---------|---------|
| 1. Niche Overview | Research scope, key metrics |
| 2. Channel Analysis | Competitor comparison table + radar chart |
| 3. Viral Content | TOP videos, engagement leaders, duration analysis |
| 4. Transcript Intelligence & Strategy | Hook patterns, structure patterns, reusable script templates |
| 5. Rising Channels | Channels with stronger recent movement in the sample |
| 6. Audience Pain Points | Comment keyword analysis |
| 7. Growth Plan & Revenue | Early growth notes + scenario-based revenue range |
| 8. Action Checklist | Prioritized execution checklist |
""")
else:
    st.markdown("""
PDF 报告共 8 章：

| 章节 | 内容 |
|------|------|
| 1. 赛道概览 | 调研范围、核心指标 |
| 2. 对标频道分析 | 频道对比表、雷达图 |
| 3. 爆款内容解码 | 高表现视频、互动领先项、时长分析 |
| 4. 字幕洞察与内容策略 | Hook 模式、结构模式、可复用脚本模板 |
| 5. 上升频道观察 | 样本中近期表现更强的频道 |
| 6. 观众痛点洞察 | 评论关键词分析 |
| 7. 增长规划与收入 | 阶段增长建议、收入区间 |
| 8. 执行清单 | 优先执行事项 |
""")

st.markdown("---")
st.caption(
    "💡 "
    + t(
        "提示：当你需要做比较而不是寻找唯一答案时，换一组频道或关键词重新运行一次。",
        "Tip: Re-run with a different channel set or keyword set when you want a comparison, not a guaranteed answer.",
    )
)

if monitor:
    st.markdown(f"### 🧪 {t('流程监视器', 'Workflow Monitor')}")
    monitor_col1, monitor_col2, monitor_col3 = st.columns(3)
    monitor_col1.metric(t("总耗时", "Total Runtime"), f"{monitor.get('duration_sec', 0):.2f}s")
    monitor_col2.metric(t("记录阶段数", "Tracked Stages"), len(monitor.get("stages", [])))
    ok_stages = sum(1 for stage in monitor.get("stages", []) if stage.get("status") == "ok")
    monitor_col3.metric(t("成功阶段数", "Successful Stages"), ok_stages)

    for stage in monitor.get("stages", []):
        label = stage.get("name", "stage")
        duration = stage.get("duration_sec", 0)
        status = stage.get("status", "unknown")
        st.markdown(f"- **{label}**: {status} ({duration:.2f}s)")

if monitor:
    st.download_button(
        label=f"🧪 {t('下载流程监视器', 'Download Workflow Monitor')}",
        data=json.dumps(monitor, ensure_ascii=False, indent=2),
        file_name=f"workflow_monitor_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json",
        use_container_width=True,
    )
