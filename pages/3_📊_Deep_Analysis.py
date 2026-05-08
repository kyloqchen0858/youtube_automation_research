"""
Page 3: Deep Analysis
深度分析 — 8步实时进度 + 交互仪表盘
"""

import os
import tempfile
import logging

import streamlit as st
import pandas as pd

from core.fetcher import YouTubeFetcher
from core.competitor_radar import build_competitor_radar
from core.decline_analyzer import analyze_decline_drivers
from core.analyzer import (
    compute_metrics,
    find_top_videos,
    analyze_duration_sweet_spot,
    analyze_publish_patterns,
    analyze_channel_evolution,
    extract_title_keywords,
    extract_comment_keywords,
    compare_channels,
)
from core.growth_detector import detect_growth, detect_viral_outliers
from core.insight_validator import summarize_reliability, validate_duration_recommendation
from core.visualizer import (
    plot_top_videos_bar,
    plot_duration_scatter,
    plot_publish_heatmap,
    plot_channel_comparison_radar,
    plot_growth_trend,
    plot_title_wordcloud,
    plot_comment_wordcloud,
    save_plotly_as_image,
    save_matplotlib_as_image,
)
from core.strategy_advisor import (
    generate_milestone_plan,
    estimate_monetization,
    suggest_content_strategy,
)
from core.report_generator import generate_report
from core.reverse_engineering import build_reverse_engineering_playbook
from core.strategy_models import get_strategy_brief, sync_strategy_brief
from core.transcript_analyzer import analyze_transcript_patterns
from core.workflow_monitor import WorkflowMonitor

logger = logging.getLogger(__name__)


def render_transcript_patterns(title: str, patterns: list[dict]):
    st.markdown(f"#### {title}")
    if not patterns:
        st.info("No usable transcript signal found in this block.")
        return

    for pattern in patterns:
        share = int(pattern.get("share", 0) * 100)
        label = pattern.get("label", "Pattern")
        count = pattern.get("count", 0)
        with st.expander(f"{label} — {share}% of sample ({count} videos)"):
            st.markdown(pattern.get("description", ""))
            examples = pattern.get("examples", [])
            if examples:
                st.markdown("**Examples**")
                for example in examples:
                    st.markdown(f"- {example}")


WORKFLOW_MODE_HINTS = {
    "analysis_quality": "Analysis Quality mode prioritizes reliable windows and more conservative strategy sources.",
    "horizontal_benchmark": "Horizontal Benchmark mode keeps the sample broad and emphasizes cross-channel comparison.",
    "vertical_optimize": "Vertical Optimize mode treats the first selected channel as the focus channel for deeper diagnosis and strategy.",
    "single_viral": "Single Viral mode prioritizes breakout-style examples and outlier replication risk.",
}


def _resolve_focus_channel_id(selected_channels: list[dict], channels_data: dict, strategy_brief) -> str | None:
    preferred = strategy_brief.channel_context.get("focus_channel_id")
    if preferred and preferred in channels_data:
        return preferred

    for channel in selected_channels:
        channel_id = channel.get("channel_id")
        if not channels_data or channel_id in channels_data:
            return channel_id

    return next(iter(channels_data), None)


def _workflow_video_pool(channels_data: dict, strategy_brief, selected_channels: list[dict]) -> pd.DataFrame:
    if not channels_data:
        return pd.DataFrame()

    mode = strategy_brief.workflow_mode
    focus_channel_id = _resolve_focus_channel_id(selected_channels, channels_data, strategy_brief)

    if mode == "vertical_optimize" and focus_channel_id in channels_data:
        focus_videos = channels_data[focus_channel_id].get("videos", pd.DataFrame())
        return focus_videos.copy() if not focus_videos.empty else pd.DataFrame()

    if mode == "analysis_quality":
        frames = [
            data["videos"]
            for data in channels_data.values()
            if data.get("growth", {}).get("reliable") and not data.get("videos", pd.DataFrame()).empty
        ]
        if frames:
            return pd.concat(frames, ignore_index=True)

    frames = [data["videos"] for data in channels_data.values() if not data.get("videos", pd.DataFrame()).empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _select_mode_candidates(
    channels_data: dict,
    strategy_brief,
    selected_channels: list[dict],
    top_n: int,
    min_views: int = 0,
) -> pd.DataFrame:
    pool = _workflow_video_pool(channels_data, strategy_brief, selected_channels)
    if pool.empty:
        return pool

    if min_views > 0:
        filtered = pool[pool["view_count"] >= min_views].copy()
        if filtered.empty:
            filtered = pool.copy()
    else:
        filtered = pool.copy()

    mode = strategy_brief.workflow_mode
    if mode == "horizontal_benchmark" and "channel_id" in filtered.columns:
        per_channel = max(1, min(3, top_n))
        diversified = (
            filtered.sort_values("view_count", ascending=False)
            .groupby("channel_id", group_keys=False)
            .head(per_channel)
        )
        return diversified.nlargest(top_n, "view_count")

    if mode == "single_viral":
        sort_cols = ["view_count"]
        ascending = [False]
        if "comment_count" in filtered.columns:
            sort_cols.append("comment_count")
            ascending.append(False)
        return filtered.sort_values(sort_cols, ascending=ascending).head(top_n)

    return filtered.nlargest(top_n, "view_count")


def _choose_strategy_source(
    channels_data: dict,
    radar_results: dict,
    strategy_brief,
    viral_outliers: dict,
    selected_channels: list[dict],
) -> tuple[dict, str]:
    focus_channel_id = _resolve_focus_channel_id(selected_channels, channels_data, strategy_brief)
    radar_shortlist = {
        ch_id: channels_data[ch_id]
        for ch_id in radar_results.get("shortlist_channel_ids", [])
        if ch_id in channels_data
    }
    reliable_channels = {
        ch_id: data
        for ch_id, data in channels_data.items()
        if data.get("growth", {}).get("reliable")
    }
    reliable_radar_shortlist = {
        ch_id: data
        for ch_id, data in radar_shortlist.items()
        if data.get("growth", {}).get("reliable")
    }

    mode = strategy_brief.workflow_mode
    if mode == "vertical_optimize" and focus_channel_id in channels_data:
        title = channels_data[focus_channel_id].get("info", {}).get("title", focus_channel_id)
        return {focus_channel_id: channels_data[focus_channel_id]}, f"Vertical optimize mode: focusing strategy on {title}"

    if mode == "single_viral":
        outlier_channels = {
            ch_id: channels_data[ch_id]
            for ch_id, insight in viral_outliers.items()
            if insight.get("has_outliers") and ch_id in channels_data
        }
        reliable_outliers = {
            ch_id: data
            for ch_id, data in outlier_channels.items()
            if data.get("growth", {}).get("reliable")
        }
        if reliable_outliers:
            return reliable_outliers, f"Single viral mode: prioritizing {len(reliable_outliers)} reliable outlier channels"
        if outlier_channels:
            return outlier_channels, f"Single viral mode: prioritizing {len(outlier_channels)} outlier channels"

    if mode == "horizontal_benchmark":
        if radar_shortlist:
            return radar_shortlist, f"Horizontal benchmark mode: comparing across {len(radar_shortlist)} radar-shortlisted channels"
        return channels_data, f"Horizontal benchmark mode: using all {len(channels_data)} selected channels"

    if reliable_radar_shortlist:
        return reliable_radar_shortlist, f"Analysis quality mode: {len(reliable_radar_shortlist)} radar-shortlisted reliable channels"
    if radar_shortlist:
        return radar_shortlist, f"Analysis quality mode: {len(radar_shortlist)} radar-shortlisted channels"
    if reliable_channels:
        return reliable_channels, f"Analysis quality mode: {len(reliable_channels)}/{len(channels_data)} reliable channels"
    return channels_data, "Analysis quality mode: fallback to all channels"

st.set_page_config(page_title="Deep Analysis", page_icon="📊", layout="wide")

st.title("📊 Deep Analysis / 深度分析")

# ── 前置检查 ────────────────────────────────────────────────
if not st.session_state.get("api_key_valid"):
    st.warning("⚠️ Please set up your API key → **🔑 API Setup**")
    st.stop()

if not st.session_state.get("selected_channels"):
    st.warning("⚠️ Please select channels first → **🔍 Channel Discovery**")
    st.stop()

fetcher = YouTubeFetcher(st.session_state.api_key)
selected = st.session_state.selected_channels
strategy_brief = get_strategy_brief(st.session_state, niche_override=st.session_state.get("niche", "YouTube Niche"))
sync_strategy_brief(st.session_state, strategy_brief)
niche = strategy_brief.niche or st.session_state.get("niche", "YouTube Niche")

brief_col1, brief_col2, brief_col3 = st.columns(3)
brief_col1.metric("Content Direction", strategy_brief.content_direction)
brief_col2.metric("Primary Goal", strategy_brief.primary_goal)
brief_col3.metric("Workflow Mode", strategy_brief.workflow_mode)

if strategy_brief.strategy_keywords:
    st.caption("Active brief keywords: " + " | ".join(strategy_brief.strategy_keywords))

mode_hint = WORKFLOW_MODE_HINTS.get(strategy_brief.workflow_mode)
if mode_hint:
    st.info(mode_hint)
if strategy_brief.workflow_mode == "vertical_optimize" and selected:
    st.caption(f"Focus channel for downstream strategy: {selected[0].get('title', selected[0].get('channel_id', 'N/A'))}")

# ── Configuration ───────────────────────────────────────────
st.markdown("### ⚙️ Analysis Configuration")
col1, col2, col3 = st.columns(3)
with col1:
    max_videos = st.number_input("Max videos per channel", 10, 200, 50, step=10)
with col2:
    fetch_comments = st.checkbox("Fetch comments (for pain points)", value=True)
with col3:
    fetch_transcripts = st.checkbox("Fetch transcripts (zero quota)", value=False)

top_n_comments = 5  # 只抓 TOP 5 视频的评论以节省配额
top_n_transcripts = 10

# ── Run Analysis ────────────────────────────────────────────
if st.button("🚀 Start Deep Analysis", type="primary", use_container_width=True):

    # Create temp directory for chart images
    chart_dir = tempfile.mkdtemp(prefix="yt_charts_")
    chart_paths = {}
    monitor = WorkflowMonitor(
        phase="Streamlit Deep Analysis",
        keyword=niche,
        metadata={
            "selected_channels": len(selected),
            "content_direction": strategy_brief.content_direction,
            "primary_goal": strategy_brief.primary_goal,
            "max_videos": int(max_videos),
            "fetch_comments": fetch_comments,
            "fetch_transcripts": fetch_transcripts,
        },
    )

    channels_data = {}
    all_videos = []
    all_comments = []
    transcripts = {}
    video_info_map = {}
    channel_evolution = {}
    viral_outliers = {}
    radar_results = {
        "brief": strategy_brief.to_dict(),
        "top_channels": [],
        "top_videos": [],
        "channel_scorecards": [],
        "shortlist_channel_ids": [],
        "summary": {},
    }
    reverse_engineering_playbook = {
        "channel_archetype": "",
        "winning_topic_clusters": [],
        "winning_title_formulas": [],
        "winning_hook_formulas": [],
        "dominant_formats": [],
        "viewer_praise_patterns": [],
        "viewer_gap_patterns": [],
        "copy_constraints": [],
        "recommended_adaptations": [],
        "confidence_notes": [],
    }
    decline_diagnostics = []
    transcript_insights = {
        "has_data": False,
        "message": "Transcript analysis was skipped.",
        "coverage": {
            "candidate_videos": 0,
            "analyzed_videos": 0,
            "analyzed_channels": 0,
            "total_words": 0,
            "avg_words_per_video": 0,
        },
        "hook_patterns": [],
        "structure_patterns": [],
        "promise_patterns": [],
        "cta_patterns": [],
        "evidence_patterns": [],
        "signal_terms": [],
        "video_breakdowns": [],
        "channel_signatures": [],
        "evolution_signals": [],
        "strategy_recommendations": [],
        "script_templates": [],
        "method_note": "Transcript analysis was not run.",
    }

    with st.status("🔄 Running analysis pipeline...", expanded=True) as status:

        total_steps = 10
        current = 0

        # ── Step 1: Fetch channel videos ──────────────────
        current += 1
        with monitor.stage("fetch_channel_videos"):
            status.update(label=f"Step {current}/{total_steps}: Fetching channel videos...")
            st.write(f"📺 Fetching videos for {len(selected)} channels...")

            for ch in selected:
                ch_id = ch["channel_id"]
                ch_title = ch.get("title", ch_id)
                st.write(f"  → {ch_title}...")

                try:
                    videos_df = fetcher.get_channel_videos(ch_id, max_videos=max_videos)
                    info = ch.copy()
                    # Remove internal keys
                    info.pop("_videos_df", None)

                    growth = detect_growth(videos_df)

                    channels_data[ch_id] = {
                        "info": info,
                        "videos": videos_df,
                        "growth": growth,
                    }

                    if not videos_df.empty:
                        all_videos.append(videos_df)

                    st.write(f"    ✅ {len(videos_df)} videos")
                except Exception as e:
                    st.warning(f"    ⚠️ Failed: {e}")

        # ── Step 2: Fetch comments ────────────────────────
        current += 1
        with monitor.stage("fetch_comments"):
            status.update(label=f"Step {current}/{total_steps}: Fetching comments...")

            if fetch_comments and all_videos:
                top_for_comments = _select_mode_candidates(
                    channels_data,
                    strategy_brief,
                    selected,
                    top_n_comments,
                )

                for _, vid in top_for_comments.iterrows():
                    st.write(f"  💬 {vid['title'][:40]}...")
                    try:
                        comments = fetcher.get_video_comments(vid["video_id"], max_comments=50)
                        all_comments.extend(comments)
                    except Exception as e:
                        st.write(f"    ⚠️ Comments disabled or error: {e}")
                st.write(f"  ✅ Total comments: {len(all_comments)}")
            else:
                st.write("  ⏭️ Skipped")

        # ── Step 3: Fetch transcripts ─────────────────────
        current += 1
        with monitor.stage("fetch_transcripts"):
            status.update(label=f"Step {current}/{total_steps}: Fetching transcripts...")

            if fetch_transcripts and all_videos:
                transcript_candidates = _select_mode_candidates(
                    channels_data,
                    strategy_brief,
                    selected,
                    top_n_transcripts,
                    min_views=20000,
                )

                for _, vid in transcript_candidates.iterrows():
                    video_info_map[vid["video_id"]] = {
                        "title": vid["title"],
                        "channel_title": vid.get("channel_title", ""),
                        "view_count": int(vid.get("view_count", 0)),
                        "published_at": vid.get("published_at"),
                    }
                    st.write(f"  📝 {vid['title'][:40]}...")
                    text = YouTubeFetcher.get_video_transcript(vid["video_id"])
                    if text and len(text) > 120:
                        transcripts[vid["video_id"]] = text
                        st.write("    ✅ Got transcript")
                    else:
                        st.write("    ⏭️ No transcript available")

                st.write(f"  ✅ Total transcripts: {len(transcripts)}/{len(transcript_candidates)}")
            else:
                st.write("  ⏭️ Skipped")

        # ── Step 4: Analyze transcripts ───────────────────
        current += 1
        with monitor.stage("analyze_transcripts"):
            status.update(label=f"Step {current}/{total_steps}: Analyzing transcript patterns...")

            if transcripts:
                transcript_insights = analyze_transcript_patterns(transcripts, video_info_map)
                coverage = transcript_insights.get("coverage", {})
                st.write(
                    "  ✅ Transcript patterns extracted: "
                    f"{coverage.get('analyzed_videos', 0)} videos / "
                    f"{coverage.get('analyzed_channels', 0)} channels"
                )
            else:
                st.write("  ⏭️ Skipped")

        # ── Step 5: Compute metrics ───────────────────────
        current += 1
        with monitor.stage("compute_metrics"):
            status.update(label=f"Step {current}/{total_steps}: Computing metrics...")

            if all_videos:
                combined_df = pd.concat(all_videos, ignore_index=True)
                combined_df = compute_metrics(combined_df)

                # Also compute per-channel
                for ch_id, data in channels_data.items():
                    if not data["videos"].empty:
                        data["videos"] = compute_metrics(data["videos"])
                        channel_evolution[ch_id] = analyze_channel_evolution(data["videos"])
                        viral_outliers[ch_id] = detect_viral_outliers(data["videos"])

                top_videos = find_top_videos(combined_df, "view_count", 10)
                top_engagement = find_top_videos(combined_df, "engagement_rate", 10)
                duration_analysis = analyze_duration_sweet_spot(combined_df)
                publish_patterns = analyze_publish_patterns(combined_df)
                title_kw = extract_title_keywords(combined_df)
                comment_kw = extract_comment_keywords(all_comments)
                comparison_df = compare_channels(channels_data)
                reliability_summary = summarize_reliability(channels_data)
                duration_consistency = validate_duration_recommendation(duration_analysis, channels_data)
                decline_diagnostics = analyze_decline_drivers(
                    channels_data,
                    strategy_brief=strategy_brief,
                    viral_outliers=viral_outliers,
                    evolution_insights=channel_evolution,
                )

                st.write("  ✅ Metrics computed")
            else:
                st.error("No video data available. Cannot proceed.")
                st.stop()

        # ── Step 6: Rank competitors ──────────────────────
        current += 1
        with monitor.stage("competitor_radar"):
            status.update(label=f"Step {current}/{total_steps}: Ranking competitors against active brief...")

            radar_results = build_competitor_radar(channels_data, strategy_brief)
            shortlist_ids = radar_results.get("shortlist_channel_ids", [])
            if shortlist_ids:
                st.write(f"  ✅ Competitor radar shortlisted {len(shortlist_ids)} channels")
            else:
                st.write("  ⚠️ Competitor radar found no shortlist, fallback strategy will use all channels")

        # ── Step 7: Generate charts ───────────────────────
        current += 1
        with monitor.stage("generate_charts"):
            status.update(label=f"Step {current}/{total_steps}: Generating charts...")

            # Chart 1: TOP 10 bar
            fig_top10 = plot_top_videos_bar(combined_df, "view_count", 10)
            path = os.path.join(chart_dir, "top10_bar.png")
            try:
                save_plotly_as_image(fig_top10, path)
                chart_paths["top10_bar"] = path
            except Exception:
                pass
            st.write("  ✅ TOP 10 chart")

            # Chart 2: Duration scatter
            fig_scatter = plot_duration_scatter(combined_df)
            path = os.path.join(chart_dir, "duration_scatter.png")
            try:
                save_plotly_as_image(fig_scatter, path)
                chart_paths["duration_scatter"] = path
            except Exception:
                pass
            st.write("  ✅ Duration scatter chart")

            # Chart 3: Publish heatmap
            heatmap_data = publish_patterns.get("heatmap_data")
            fig_heatmap = plot_publish_heatmap(heatmap_data)
            path = os.path.join(chart_dir, "publish_heatmap.png")
            try:
                save_plotly_as_image(fig_heatmap, path)
                chart_paths["publish_heatmap"] = path
            except Exception:
                pass
            st.write("  ✅ Publish heatmap")

            # Chart 4: Radar
            fig_radar = plot_channel_comparison_radar(comparison_df)
            path = os.path.join(chart_dir, "radar.png")
            try:
                save_plotly_as_image(fig_radar, path)
                chart_paths["radar"] = path
            except Exception:
                pass
            st.write("  ✅ Radar chart")

            # Chart 5: Title wordcloud
            fig_wc_title = plot_title_wordcloud(title_kw)
            path = os.path.join(chart_dir, "title_wordcloud.png")
            save_matplotlib_as_image(fig_wc_title, path)
            chart_paths["title_wordcloud"] = path
            st.write("  ✅ Title word cloud")

            # Chart 6: Comment wordcloud
            if comment_kw:
                fig_wc_comment = plot_comment_wordcloud(comment_kw)
                path = os.path.join(chart_dir, "comment_wordcloud.png")
                save_matplotlib_as_image(fig_wc_comment, path)
                chart_paths["comment_wordcloud"] = path
                st.write("  ✅ Comment word cloud")

            # Chart 7: Growth trend (for top channel)
            if channels_data:
                first_ch_id = list(channels_data.keys())[0]
                first_data = channels_data[first_ch_id]
                fig_growth = plot_growth_trend(
                    first_data["videos"],
                    first_data["info"].get("title", ""),
                )
                path = os.path.join(chart_dir, "growth_trend.png")
                try:
                    save_plotly_as_image(fig_growth, path)
                    chart_paths["growth_trend"] = path
                except Exception:
                    pass
                st.write("  ✅ Growth trend chart")

        # ── Step 8: Generate strategy ─────────────────────
        current += 1
        with monitor.stage("generate_strategy"):
            status.update(label=f"Step {current}/{total_steps}: Generating strategy...")

            strategy_source, strategy_source_note = _choose_strategy_source(
                channels_data,
                radar_results,
                strategy_brief,
                viral_outliers,
                selected,
            )
            st.write(f"  ✅ Strategy source: {strategy_source_note}")

            reverse_engineering_playbook = build_reverse_engineering_playbook(
                brief=strategy_brief,
                radar_results=radar_results,
                transcript_insights=transcript_insights,
                top_videos_df=top_engagement,
            )

            milestone_plan = generate_milestone_plan(
                strategy_source,
                niche,
                strategy_brief=strategy_brief,
                radar_results=radar_results,
                reverse_engineering_playbook=reverse_engineering_playbook,
                transcript_insights=transcript_insights,
            )
            avg_views = int(combined_df["view_count"].mean()) if not combined_df.empty else 1000

            # Estimate niche CPM (education/business niche ~ $5-8)
            monetization = estimate_monetization(
                target_subscribers=1000,
                avg_views_per_video=avg_views,
                niche_cpm=6.0,
                videos_per_month=8,
            )
            content_strategy = suggest_content_strategy(
                top_engagement,
                title_kw,
                duration_analysis,
                publish_patterns,
                niche,
                channels_data=strategy_source,
                user_keywords=st.session_state.get("strategy_keywords", []),
                strategy_brief=strategy_brief,
                radar_results=radar_results,
                reverse_engineering_playbook=reverse_engineering_playbook,
            )
            st.write("  ✅ Strategy generated")

        # ── Step 9: Build rising channels DF ──────────────
        current += 1
        with monitor.stage("compile_rising_channels"):
            status.update(label=f"Step {current}/{total_steps}: Compiling rising channels...")

            rising_data = []
            for ch_id, data in channels_data.items():
                growth = data.get("growth", {})
                info = data.get("info", {})
                if growth.get("reliable") and growth.get("growth_ratio", 0) >= 1.5:
                    rising_data.append({**info, **growth})
            rising_channels_df = pd.DataFrame(rising_data) if rising_data else pd.DataFrame()
            st.write("  ✅ Rising channels compiled")

        # ── Step 10: Generate PDF ─────────────────────────
        current += 1
        with monitor.stage("generate_pdf"):
            status.update(label=f"Step {current}/{total_steps}: Generating PDF report...")

            try:
                report_bytes = generate_report(
                    niche=niche,
                    channels_data=channels_data,
                    comparison_df=comparison_df,
                    top_videos_df=top_engagement,
                    duration_analysis=duration_analysis,
                    publish_patterns=publish_patterns,
                    title_keywords=title_kw,
                    comment_keywords=comment_kw,
                    milestone_plan=milestone_plan,
                    monetization=monetization,
                    content_strategy=content_strategy,
                    chart_paths=chart_paths,
                    rising_channels_df=rising_channels_df,
                    reliability_summary=reliability_summary,
                    consistency_check=duration_consistency,
                    viral_outliers=viral_outliers,
                    evolution_insights=channel_evolution,
                    transcript_insights=transcript_insights,
                )
                st.session_state.report_bytes = report_bytes
                st.write("  ✅ PDF report generated")
            except Exception as e:
                st.warning(f"  ⚠️ PDF generation failed: {e}")
                st.session_state.report_bytes = None

        # ── Save results to session ───────────────────────
        st.session_state.analysis_results = {
            "channels_data": channels_data,
            "combined_df": combined_df,
            "comparison_df": comparison_df,
            "top_videos": top_videos,
            "top_engagement": top_engagement,
            "duration_analysis": duration_analysis,
            "publish_patterns": publish_patterns,
            "title_keywords": title_kw,
            "comment_keywords": comment_kw,
            "transcripts": transcripts,
            "transcript_video_info": video_info_map,
            "transcript_insights": transcript_insights,
            "reverse_engineering_playbook": reverse_engineering_playbook,
            "strategy_brief": strategy_brief.to_dict(),
            "radar_results": radar_results,
            "milestone_plan": milestone_plan,
            "monetization": monetization,
            "content_strategy": content_strategy,
            "reliability_summary": reliability_summary,
            "duration_consistency": duration_consistency,
            "viral_outliers": viral_outliers,
            "channel_evolution": channel_evolution,
            "decline_diagnostics": decline_diagnostics,
            "rising_channels_df": rising_channels_df,
            "chart_paths": chart_paths,
            "all_comments": all_comments,
        }
        monitor.set_summary(
            channels_analyzed=len(channels_data),
            videos_scanned=len(combined_df),
            comments_collected=len(all_comments),
            transcripts_collected=len(transcripts),
            charts_generated=len(chart_paths),
        )
        st.session_state.analysis_monitor = monitor.to_dict()

        status.update(label="✅ Analysis Complete!", state="complete")

    st.balloons()
    st.success("🎉 Analysis complete! Scroll down to see results, or go to **📥 Download Report** for the PDF.")

# ── Results Dashboard ───────────────────────────────────────
results = st.session_state.get("analysis_results")
if results:
    st.markdown("---")
    st.markdown("## 📊 Analysis Dashboard")

    trust = results.get("reliability_summary", {})
    if trust:
        st.info(
            f"Data trust: {trust.get('reliable_channels', 0)}/{trust.get('total_channels', 0)} reliable channels "
            f"(avg reliability score {trust.get('average_score', 0)}/100)"
        )

    consistency = results.get("duration_consistency", {})
    if consistency.get("has_conflict"):
        issues = consistency.get("issues", [])
        if issues:
            st.warning(f"Strategy consistency warning: {issues[0]}")

    tab_radar, tab_compare, tab_viral, tab_transcript, tab_content, tab_growth, tab_plan = st.tabs([
        "🧭 Competitor Radar",
        "📊 Channel Comparison",
        "🔥 Viral Content",
        "🧠 Transcript Intelligence",
        "🗺️ Content Map",
        "📈 Growth Analysis",
        "🎯 Growth Plan & Revenue",
    ])

    # ── Tab 1: Competitor Radar ──────────────────────────
    with tab_radar:
        st.markdown("### Competitor Radar / 竞品雷达")
        radar_data = results.get("radar_results", {})
        radar_summary = radar_data.get("summary", {})
        if radar_summary.get("why_it_matters"):
            st.info(radar_summary.get("why_it_matters"))

        top_channels = radar_data.get("top_channels", [])
        if top_channels:
            st.markdown("#### Ranked Channels")
            radar_df = pd.DataFrame(top_channels)
            show_cols = [
                "channel_title",
                "subscriber_count",
                "avg_recent_views",
                "avg_views_to_subs_ratio",
                "growth_ratio",
                "reliability_score",
                "keyword_relevance",
                "format_fit",
                "radar_score",
            ]
            existing_cols = [col for col in show_cols if col in radar_df.columns]
            st.dataframe(radar_df[existing_cols], use_container_width=True, hide_index=True)

            for channel in top_channels[:3]:
                with st.expander(f"{channel.get('channel_title', 'Channel')} — radar score {channel.get('radar_score', 0)}"):
                    for reason in channel.get("score_reasons", []):
                        st.markdown(f"- {reason}")
        else:
            st.info("Competitor radar did not return ranked channels for the current sample.")

        top_videos = radar_data.get("top_videos", [])
        if top_videos:
            st.markdown("#### Breakout Reference Videos")
            top_videos_df = pd.DataFrame(top_videos)
            show_video_cols = [
                "title",
                "channel_id",
                "view_count",
                "baseline_lift",
                "views_to_subs_ratio",
                "keyword_relevance",
                "format_guess",
                "breakout_score",
            ]
            existing_video_cols = [col for col in show_video_cols if col in top_videos_df.columns]
            st.dataframe(top_videos_df[existing_video_cols], use_container_width=True, hide_index=True)

    # ── Tab 2: Channel Comparison ─────────────────────────
    with tab_compare:
        st.markdown("### Channel Comparison / 频道对比")
        if not results["comparison_df"].empty:
            st.dataframe(results["comparison_df"], use_container_width=True, hide_index=True)

        fig_radar = plot_channel_comparison_radar(results["comparison_df"])
        st.plotly_chart(fig_radar, use_container_width=True)

    # ── Tab 3: Viral Content ──────────────────────────────
    with tab_viral:
        st.markdown("### 🏆 TOP Videos by Views")
        fig_bar = plot_top_videos_bar(results["combined_df"], "view_count", 10)
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("### 🤝 TOP Videos by Engagement Rate")
        if not results["top_engagement"].empty:
            for _, v in results["top_engagement"].head(5).iterrows():
                with st.expander(f'{v["title"][:60]} — {v.get("engagement_rate", 0):.2%}'):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Views", f'{v["view_count"]:,}')
                    c2.metric("Likes", f'{v["like_count"]:,}')
                    c3.metric("Comments", f'{v["comment_count"]:,}')
                    c4.metric("Duration", f'{v.get("duration_minutes", 0):.0f} min')

        st.markdown("### 🧪 Single-Viral Outlier Check")
        any_outlier = False
        for ch_id, insight in results.get("viral_outliers", {}).items():
            if not insight.get("has_outliers"):
                continue
            any_outlier = True
            ch_name = results["channels_data"].get(ch_id, {}).get("info", {}).get("title", ch_id)
            with st.expander(f"{ch_name} — {insight.get('outlier_count', 0)} outlier video(s)"):
                for outlier in insight.get("outliers", []):
                    st.markdown(
                        f"- {outlier.get('title', 'N/A')} | "
                        f"Views: {outlier.get('view_count', 0):,} | z-score: {outlier.get('zscore', 0)}"
                    )
                st.caption(
                    "Baseline growth without outliers: "
                    f"{insight.get('baseline_growth_ratio', 'N/A')}x "
                    f"({insight.get('baseline_status', 'N/A')})"
                )
        if not any_outlier:
            st.info("No strong viral outlier detected in current sample.")

    # ── Tab 4: Transcript Intelligence ───────────────────
    with tab_transcript:
        st.markdown("### 🧠 Transcript-First Content Intelligence")
        transcript_data = results.get("transcript_insights", {})

        if not transcript_data.get("has_data"):
            st.info(transcript_data.get("message", "No transcript analysis available."))
        else:
            coverage = transcript_data.get("coverage", {})
            c1, c2, c3 = st.columns(3)
            c1.metric("Transcripts Analyzed", coverage.get("analyzed_videos", 0))
            c2.metric("Channels Covered", coverage.get("analyzed_channels", 0))
            c3.metric("Words Parsed", f"{coverage.get('total_words', 0):,}")

            st.caption(transcript_data.get("method_note", ""))

            signal_terms = transcript_data.get("signal_terms", [])
            if signal_terms:
                st.markdown("**Recurring signal terms**")
                st.markdown(" | ".join(f"`{term}`" for term in signal_terms))

            render_transcript_patterns("Opening Hooks", transcript_data.get("hook_patterns", []))
            render_transcript_patterns("Structure Patterns", transcript_data.get("structure_patterns", []))
            render_transcript_patterns("Title Promise Patterns", transcript_data.get("promise_patterns", []))
            render_transcript_patterns("CTA Patterns", transcript_data.get("cta_patterns", []))

            channel_signatures = transcript_data.get("channel_signatures", [])
            if channel_signatures:
                st.markdown("#### Channel Content Signatures")
                for channel in channel_signatures[:5]:
                    with st.expander(f"{channel['channel']} — {channel['videos']} transcript sample(s)"):
                        st.markdown(channel.get("summary", ""))
                        st.markdown(
                            f"- Hook: {channel.get('dominant_hook', 'N/A')}\n"
                            f"- Structure: {channel.get('dominant_structure', 'N/A')}\n"
                            f"- Promise: {channel.get('dominant_promise', 'N/A')}\n"
                            f"- CTA: {channel.get('dominant_cta', 'N/A')}"
                        )

            evolution_signals = transcript_data.get("evolution_signals", [])
            if evolution_signals:
                st.markdown("#### Channel Evolution Signals")
                for evolution in evolution_signals:
                    st.markdown(f"- **{evolution['channel']}**: {evolution['summary']}")

            strategy_recommendations = transcript_data.get("strategy_recommendations", [])
            if strategy_recommendations:
                st.markdown("#### Transcript-Grounded Strategy Moves")
                for recommendation in strategy_recommendations:
                    with st.expander(f"{recommendation['title']} ({recommendation['confidence']})"):
                        st.markdown(recommendation.get("recommendation", ""))
                        st.caption(recommendation.get("evidence", ""))

            script_templates = transcript_data.get("script_templates", [])
            if script_templates:
                st.markdown("#### Reusable Script Templates")
                for template in script_templates:
                    with st.expander(template.get("name", "Template")):
                        st.markdown(template.get("why_it_works", ""))
                        st.caption(template.get("evidence", ""))
                        for step in template.get("steps", []):
                            st.markdown(f"- {step}")
                        example_titles = template.get("example_titles", [])
                        if example_titles:
                            st.markdown("**Example titles**")
                            for example_title in example_titles:
                                st.markdown(f"- {example_title}")

            video_breakdowns = transcript_data.get("video_breakdowns", [])
            if video_breakdowns:
                st.markdown("#### Transcript Breakdown by Video")
                transcript_df = pd.DataFrame(video_breakdowns)
                if not transcript_df.empty:
                    show_cols = [
                        "title",
                        "channel_title",
                        "view_count",
                        "hook_type",
                        "structure_type",
                        "promise_type",
                        "cta_type",
                        "word_count",
                    ]
                    existing_cols = [col for col in show_cols if col in transcript_df.columns]
                    st.dataframe(transcript_df[existing_cols], use_container_width=True, hide_index=True)

    # ── Tab 5: Content Map ────────────────────────────────
    with tab_content:
        col_wc, col_scatter = st.columns(2)

        with col_wc:
            st.markdown("### 📝 Title Keywords")
            fig_wc = plot_title_wordcloud(results["title_keywords"])
            st.pyplot(fig_wc)

        with col_scatter:
            st.markdown("### ⏱️ Duration vs Views")
            fig_scatter = plot_duration_scatter(results["combined_df"])
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.markdown("### 📅 Publish Time Heatmap")
        heatmap_data = results["publish_patterns"].get("heatmap_data")
        fig_heatmap = plot_publish_heatmap(heatmap_data)
        st.plotly_chart(fig_heatmap, use_container_width=True)

        if results["comment_keywords"]:
            st.markdown("### 💬 Comment Keywords")
            fig_cmt = plot_comment_wordcloud(results["comment_keywords"])
            st.pyplot(fig_cmt)

        # Duration sweet spot
        st.markdown("### 🎯 Duration Sweet Spot")
        dur = results["duration_analysis"]
        st.info(f"Best duration range: **{dur.get('best_range', 'N/A')}** "
                f"(avg {dur.get('best_range_avg_views', 0):,} views)")
        if dur.get("ranges"):
            dur_df = pd.DataFrame(dur["ranges"])
            st.dataframe(dur_df, use_container_width=True, hide_index=True)

    # ── Tab 6: Growth Analysis ────────────────────────────
    with tab_growth:
        st.markdown("### 📈 Channel Growth Trends")
        diagnostics_by_channel = {
            item["channel_id"]: item for item in results.get("decline_diagnostics", [])
        }

        for ch_id, data in results["channels_data"].items():
            ch_title = data["info"].get("title", ch_id)
            growth = data.get("growth", {})

            with st.expander(
                f'{growth.get("status_emoji", "")} {ch_title} — {growth.get("growth_ratio", 1):.1f}x growth'
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Growth Ratio", f'{growth.get("growth_ratio", 1):.1f}x')
                c2.metric("Recent Avg Views", f'{growth.get("avg_recent_views", 0):,}')
                c3.metric("Older Avg Views", f'{growth.get("avg_older_views", 0):,}')
                c4.metric("Engagement Trend", growth.get("engagement_trend", "N/A"))

                st.caption(
                    "Reliability: "
                    f"{growth.get('reliability_level', 'N/A')} "
                    f"({growth.get('reliability_score', 0)}/100) - "
                    f"{growth.get('reliability_reason', 'N/A')}"
                )

                evo = results.get("channel_evolution", {}).get(ch_id, {})
                if evo and evo.get("trend") != "insufficient":
                    st.markdown(
                        f"**Evolution Trend:** {evo.get('trend_label', 'N/A')} "
                        f"({evo.get('improvement_rate', 0):+.0%})"
                    )
                    st.markdown(f"- {evo.get('inflection', '')}")

                diagnosis = diagnostics_by_channel.get(ch_id)
                if diagnosis:
                    st.markdown(f"**Decline Diagnosis:** {diagnosis.get('classification_label', 'N/A')}")
                    st.markdown(f"- {diagnosis.get('summary', '')}")
                    for reason in diagnosis.get("objective_factors", []):
                        st.markdown(f"- 客观因素：{reason}")
                    for reason in diagnosis.get("strategy_factors", []):
                        st.markdown(f"- 策略因素：{reason}")

                fig_trend = plot_growth_trend(data["videos"], ch_title)
                st.plotly_chart(fig_trend, use_container_width=True)

        if not results["rising_channels_df"].empty:
            st.markdown("### 🚀 Rising Channels Summary")
            st.dataframe(
                results["rising_channels_df"][["title", "subscriber_count", "growth_ratio", "status"]].rename(
                    columns={"title": "Channel", "subscriber_count": "Subscribers", "growth_ratio": "Growth", "status": "Status"}
                ),
                use_container_width=True,
                hide_index=True,
            )

    # ── Tab 7: Growth Plan & Revenue ──────────────────────
    with tab_plan:
        plan = results["milestone_plan"]
        mon = results["monetization"]
        strategy = results["content_strategy"]
        transcript_data = results.get("transcript_insights", {})
        playbook = results.get("reverse_engineering_playbook", {})

        if strategy.get("consistency_check", {}).get("has_conflict"):
            issue_text = strategy.get("consistency_check", {}).get("issues", [])
            if issue_text:
                st.warning(issue_text[0])

        rel = strategy.get("reliability_summary")
        if rel:
            st.markdown(
                f"**Strategy Source Quality:** {rel.get('reliable_channels', 0)}/{rel.get('total_channels', 0)} reliable channels"
            )

        st.markdown("### 🎯 Growth Roadmap: 0 → 1,000 Subscribers")
        st.info(f"⏰ {plan.get('estimated_timeline', '')}")

        if plan.get("north_star_goal"):
            st.markdown("#### North Star Goal")
            st.markdown(f"- {plan.get('north_star_goal')}")

        if playbook.get("channel_archetype"):
            st.markdown("#### Reverse-Engineering Playbook")
            st.markdown(f"- **Channel archetype**: {playbook.get('channel_archetype')}")
            for item in playbook.get("recommended_adaptations", []):
                st.markdown(f"- {item}")
            if playbook.get("copy_constraints"):
                st.caption("Copy constraints: " + " | ".join(playbook.get("copy_constraints", [])[:3]))

        if plan.get("confidence_notes"):
            st.markdown("#### Confidence Notes")
            for note in plan.get("confidence_notes", []):
                st.markdown(f"- {note}")

        # Key metrics
        st.markdown("#### 📊 Niche Benchmark Metrics")
        metrics = plan.get("key_metrics", {})
        cols = st.columns(len(metrics))
        for col, (k, v) in zip(cols, metrics.items()):
            col.metric(k, v)

        # Milestones
        for ms in plan.get("milestones", []):
            with st.expander(f"**{ms['phase']}** — {ms['target']}", expanded=False):
                st.markdown(f"**Duration:** {ms['duration']}")
                for action in ms.get("actions", []):
                    st.markdown(f"- {action}")
                st.markdown(f"**KPI:** {ms.get('kpi', '')}")
                if ms.get("decision_rule"):
                    st.caption(f"Decision rule: {ms.get('decision_rule')}")
                if ms.get("fallback_action"):
                    st.caption(f"Fallback: {ms.get('fallback_action')}")

        if plan.get("weekly_operating_rules"):
            st.markdown("#### Weekly Operating Rules")
            for rule in plan.get("weekly_operating_rules", []):
                st.markdown(f"- {rule}")

        if plan.get("checkpoint_rules"):
            st.markdown("#### Checkpoint Rules")
            checkpoint_df = pd.DataFrame(plan.get("checkpoint_rules", []))
            st.dataframe(checkpoint_df, use_container_width=True, hide_index=True)

        # Revenue
        st.markdown("---")
        st.markdown("### 💰 Revenue Projection / 收入预估")

        r1, r2, r3 = st.columns(3)
        total = mon.get("total_estimated", {})
        r1.metric("Monthly Low", f"${total.get('low', 0):,.0f}")
        r2.metric("Monthly Mid", f"${total.get('mid', 0):,.0f}")
        r3.metric("Monthly High", f"${total.get('high', 0):,.0f}")

        st.markdown("#### Breakdown")
        adsense = mon.get("adsense", {})
        st.markdown(f"- **AdSense**: ${adsense.get('low',0):.0f} - ${adsense.get('high',0):.0f}/mo "
                    f"({adsense.get('note', '')})")

        for p in mon.get("knowledge_products", []):
            st.markdown(f"- **{p['name']}**: ${p['price']} × {p['monthly_sales']:.0f} sales "
                        f"= ${p['monthly_revenue']:.0f}/mo")

        mem = mon.get("membership", {})
        st.markdown(f"- **Membership**: ${mem.get('monthly_revenue',0):.0f}/mo ({mem.get('note','')})")

        # Content strategy
        st.markdown("---")
        st.markdown("### 📝 Content Strategy / 内容策略")

        painpoint = strategy.get("painpoint_hypothesis", {})
        if painpoint:
            st.markdown("#### 🎯 Core Painpoint Diagnosis")
            st.markdown(f"- **Primary**: {painpoint.get('primary', '')}")
            for item in painpoint.get("secondary", []):
                st.markdown(f"- {item}")
            st.markdown(f"- **Content Goal**: {painpoint.get('content_goal', '')}")

        st.markdown("#### Title Formulas / 标题公式")
        for f in strategy.get("title_formulas", []):
            st.markdown(f"- {f}")

        playbook_formats = playbook.get("dominant_formats", [])
        if playbook_formats:
            st.markdown("#### Dominant Formats from Shortlist")
            st.markdown(" | ".join(f"`{fmt}`" for fmt in playbook_formats))

        st.markdown(f"#### ⏱️ {strategy.get('optimal_duration', '')}")
        st.markdown(f"#### 📅 {strategy.get('publish_schedule', '')}")

        st.markdown("#### 🖼️ Thumbnail Tips")
        for tip in strategy.get("thumbnail_tips", []):
            st.markdown(f"- {tip}")

        if strategy.get("content_themes"):
            st.markdown("#### 💡 Content Theme Ideas")
            for theme in strategy["content_themes"]:
                with st.expander(theme["theme"]):
                    st.markdown(f"**Why:** {theme['reason']}")
                    for ex in theme.get("example_titles", []):
                        st.markdown(f"- {ex}")

        if transcript_data.get("script_templates"):
            st.markdown("#### 🧠 Transcript-Grounded Script Blueprints")
            for template in transcript_data["script_templates"][:3]:
                with st.expander(template.get("name", "Template")):
                    st.caption(template.get("evidence", ""))
                    for step in template.get("steps", []):
                        st.markdown(f"- {step}")

        if strategy.get("confidence_notes"):
            st.markdown("#### Strategy Confidence Notes")
            for note in strategy.get("confidence_notes", []):
                st.markdown(f"- {note}")

        if strategy.get("seo_keywords"):
            st.markdown("#### 🏷️ SEO Keywords")
            st.markdown(" | ".join(f"`{kw}`" for kw in strategy["seo_keywords"][:15]))

        cold_start = strategy.get("cold_start_plan", {})
        if cold_start:
            st.markdown("---")
            st.markdown("### 🚀 Cold Start Execution Plan")

            setup = cold_start.get("setup_checklist", [])
            if setup:
                st.markdown("#### Setup Checklist")
                for item in setup:
                    st.markdown(f"- {item}")

            weekly_plan = cold_start.get("weekly_plan", [])
            if weekly_plan:
                st.markdown("#### Weekly Plan (4 Weeks)")
                weekly_df = pd.DataFrame(weekly_plan)
                st.dataframe(weekly_df, use_container_width=True, hide_index=True)

            exp_matrix = cold_start.get("experiment_matrix", [])
            if exp_matrix:
                st.markdown("#### Format x Topic x Hook Experiment Matrix")
                exp_df = pd.DataFrame(exp_matrix)
                st.dataframe(exp_df, use_container_width=True, hide_index=True)
