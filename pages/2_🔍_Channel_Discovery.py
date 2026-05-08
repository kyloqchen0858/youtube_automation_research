"""
Page 2: Channel Discovery
频道发现 — 关键词搜索 + 暴涨频道检测
"""

import streamlit as st
import pandas as pd
from core.fetcher import YouTubeFetcher
from core.growth_detector import detect_growth

st.set_page_config(page_title="Channel Discovery", page_icon="🔍", layout="wide")

st.title("🔍 Channel Discovery / 频道发现")

# ── 前置检查 ────────────────────────────────────────────────
if not st.session_state.get("api_key_valid"):
    st.warning("⚠️ Please set up your API key first → Go to **🔑 API Setup** page")
    st.stop()

if not st.session_state.get("keywords") and not st.session_state.get("manual_channel_ids"):
    st.warning("⚠️ Please configure your niche keywords first → Go to **🔑 API Setup** page")
    st.stop()

fetcher = YouTubeFetcher(st.session_state.api_key)

# ── Section 1: Auto Discovery ──────────────────────────────
st.markdown("### 🤖 Auto Discovery / 自动发现频道")
st.markdown("Search YouTube for channels matching your niche keywords.")

col1, col2 = st.columns([3, 1])
with col1:
    max_per_keyword = st.slider("Max channels per keyword", 3, 15, 5)
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    search_btn = st.button("🚀 Start Search", type="primary", use_container_width=True)

if search_btn:
    keywords = st.session_state.get("keywords", [])
    manual_ids = st.session_state.get("manual_channel_ids", [])

    all_channels = {}

    with st.status("Searching channels...", expanded=True) as status:
        # Search by keywords
        if keywords:
            total_kw = len(keywords)
            for i, kw in enumerate(keywords):
                st.write(f"🔍 Searching: `{kw}` ({i+1}/{total_kw})")
                try:
                    channels = fetcher.search_channels(kw, max_results=max_per_keyword)
                    for ch in channels:
                        if ch["channel_id"] not in all_channels:
                            all_channels[ch["channel_id"]] = ch
                    st.write(f"   Found {len(channels)} channels")
                except Exception as e:
                    st.warning(f"   ⚠️ Search failed for '{kw}': {e}")

        # Fetch manual channel IDs
        if manual_ids:
            st.write(f"📺 Fetching {len(manual_ids)} manual channel(s)...")
            for ch_id in manual_ids:
                if ch_id not in all_channels:
                    try:
                        info = fetcher.get_channel_info(ch_id)
                        if info:
                            all_channels[ch_id] = info
                    except Exception as e:
                        st.warning(f"   ⚠️ Failed to fetch {ch_id}: {e}")

        status.update(label=f"✅ Found {len(all_channels)} unique channels", state="complete")

    # Detect growth for each channel
    if all_channels:
        st.markdown("### 📈 Analyzing Growth Trends...")

        progress = st.progress(0)
        channel_list = []
        total = len(all_channels)

        for idx, (ch_id, ch_info) in enumerate(all_channels.items()):
            try:
                # Get recent videos for growth detection
                videos_df = fetcher.get_channel_videos(ch_id, max_videos=30)
                growth = detect_growth(videos_df)

                channel_list.append({
                    **ch_info,
                    **growth,
                    "_videos_df": videos_df,
                })
            except Exception as e:
                channel_list.append({
                    **ch_info,
                    "growth_ratio": 1.0,
                    "status": "Error",
                    "status_emoji": "⚠️",
                    "avg_recent_views": 0,
                    "avg_older_views": 0,
                    "_videos_df": pd.DataFrame(),
                })

            progress.progress((idx + 1) / total)

        # Sort by growth ratio
        channel_list.sort(key=lambda x: x.get("growth_ratio", 0), reverse=True)
        st.session_state.discovered_channels = channel_list

# ── Section 2: Display Results ──────────────────────────────
if st.session_state.get("discovered_channels"):
    channels = st.session_state.discovered_channels

    # Rising channels section
    rising = [c for c in channels if c.get("growth_ratio", 1) >= 1.5]
    if rising:
        st.markdown("---")
        st.markdown("### 🚀 Rising Channels / 暴涨频道")
        st.markdown("Channels with significant recent growth (1.5x+ view velocity):")

        for ch in rising[:5]:
            with st.expander(
                f"{ch.get('status_emoji', '')} **{ch.get('title', 'N/A')}** — "
                f"Growth: {ch.get('growth_ratio', 0)}x | "
                f"Subs: {ch.get('subscriber_count', 0):,}",
                expanded=False,
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Subscribers", f"{ch.get('subscriber_count', 0):,}")
                c2.metric("Growth Ratio", f"{ch.get('growth_ratio', 0):.1f}x")
                c3.metric("Recent Avg Views", f"{ch.get('avg_recent_views', 0):,}")
                c4.metric("Older Avg Views", f"{ch.get('avg_older_views', 0):,}")

                if ch.get("description"):
                    st.markdown(f"**Description:** {ch['description'][:200]}...")

    # All channels table
    st.markdown("---")
    st.markdown("### 📋 All Discovered Channels / 所有发现频道")
    st.markdown("Select channels for deep analysis:")

    # Build display DataFrame
    display_data = []
    for ch in channels:
        display_data.append({
            "Select": False,
            "Channel": ch.get("title", "N/A"),
            "Subscribers": ch.get("subscriber_count", 0),
            "Videos": ch.get("video_count", 0),
            "Growth": f"{ch.get('status_emoji', '')} {ch.get('growth_ratio', 1.0):.1f}x",
            "Status": ch.get("status", "N/A"),
            "Channel ID": ch.get("channel_id", ""),
        })

    display_df = pd.DataFrame(display_data)

    # Editable data editor for selection
    edited_df = st.data_editor(
        display_df,
        column_config={
            "Select": st.column_config.CheckboxColumn("✅ Select", default=False),
            "Subscribers": st.column_config.NumberColumn("Subscribers", format="%d"),
            "Videos": st.column_config.NumberColumn("Videos", format="%d"),
        },
        disabled=["Channel", "Subscribers", "Videos", "Growth", "Status", "Channel ID"],
        hide_index=True,
        use_container_width=True,
    )

    # Manual channel ID input
    st.markdown("#### ➕ Add Channel by ID")
    new_ch_id = st.text_input(
        "Channel ID",
        placeholder="UCxxxxxxxxxxxxxxxxxx",
        help="Paste a YouTube channel ID to add it to analysis",
    )
    if st.button("Add Channel") and new_ch_id:
        try:
            info = fetcher.get_channel_info(new_ch_id)
            if info:
                videos_df = fetcher.get_channel_videos(new_ch_id, max_videos=30)
                growth = detect_growth(videos_df)
                new_entry = {**info, **growth, "_videos_df": videos_df}
                st.session_state.discovered_channels.append(new_entry)
                st.success(f"✅ Added: {info.get('title', new_ch_id)}")
                st.rerun()
            else:
                st.error("Channel not found. Please check the ID.")
        except Exception as e:
            st.error(f"Error: {e}")

    # Confirm selection
    st.markdown("---")
    if st.button("🎯 Confirm Selection & Proceed to Analysis", type="primary", use_container_width=True):
        selected_ids = edited_df[edited_df["Select"]]["Channel ID"].tolist()

        if not selected_ids:
            st.error("Please select at least one channel.")
        else:
            # Map selected IDs to full channel data
            selected = []
            for ch in channels:
                if ch.get("channel_id") in selected_ids:
                    selected.append(ch)

            st.session_state.selected_channels = selected
            st.success(
                f"✅ Selected {len(selected)} channels. "
                f"Go to **📊 Deep Analysis** page to start analysis."
            )
