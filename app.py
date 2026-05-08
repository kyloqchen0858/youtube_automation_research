"""
YouTube Competitive Research Tool — Main Entry
YouTube 竞品调研工具 — 主入口
"""

import streamlit as st

st.set_page_config(
    page_title="YouTube Research Tool",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 初始化 Session State ────────────────────────────────────
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "api_key_valid" not in st.session_state:
    st.session_state.api_key_valid = False
if "niche" not in st.session_state:
    st.session_state.niche = ""
if "keywords" not in st.session_state:
    st.session_state.keywords = []
if "discovered_channels" not in st.session_state:
    st.session_state.discovered_channels = []
if "selected_channels" not in st.session_state:
    st.session_state.selected_channels = []
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "report_bytes" not in st.session_state:
    st.session_state.report_bytes = None
if "workflow_mode" not in st.session_state:
    st.session_state.workflow_mode = "analysis_quality"
if "output_language" not in st.session_state:
    st.session_state.output_language = "zh"
if "delivery_mode" not in st.session_state:
    st.session_state.delivery_mode = "single_report"
if "creator_stage" not in st.session_state:
    st.session_state.creator_stage = "cold_start"
if "strategy_keywords" not in st.session_state:
    st.session_state.strategy_keywords = []
if "strategy_brief" not in st.session_state:
    st.session_state.strategy_brief = None
if "content_direction" not in st.session_state:
    st.session_state.content_direction = "ai_tool_tutorial"
if "primary_goal" not in st.session_state:
    st.session_state.primary_goal = "breakout_growth"
if "format_preferences" not in st.session_state:
    st.session_state.format_preferences = []
if "production_constraints" not in st.session_state:
    st.session_state.production_constraints = {"team_model": "solo"}
if "channel_context" not in st.session_state:
    st.session_state.channel_context = {}
if "success_definition" not in st.session_state:
    st.session_state.success_definition = {}

# ── 侧边栏状态 ─────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 YT Research Tool")
    st.markdown("---")

    # 状态指示
    st.markdown("### Status")

    if st.session_state.api_key_valid:
        st.success("✅ API Key Connected")
    else:
        st.warning("⚠️ API Key Not Set")

    if st.session_state.niche:
        st.info(f"🎯 Niche: {st.session_state.niche}")

    st.info(f"🧭 Mode: {st.session_state.workflow_mode}")
    st.info(f"🧠 Direction: {st.session_state.content_direction}")
    st.info(f"🎯 Goal: {st.session_state.primary_goal}")
    st.info(f"🌐 Language: {st.session_state.output_language.upper()}")

    if st.session_state.selected_channels:
        st.info(f"📺 Channels: {len(st.session_state.selected_channels)} selected")

    if st.session_state.analysis_results:
        st.success("📊 Analysis Complete")

    if st.session_state.report_bytes:
        st.success("📄 Report Ready")

    st.markdown("---")
    st.markdown(
        """
        ### Quick Start
        0. 🎯 Select Workflow
        1. 🔑 Set API Key
        2. 🔍 Discover Channels
        3. 📊 Run Analysis
        4. 📥 Download Report
        """
    )

    st.markdown("---")
    st.caption("Built with Streamlit + YouTube Data API v3")

# ── 首页内容 ────────────────────────────────────────────────
st.title("🎯 YouTube Competitive Research Tool")
st.markdown("### YouTube 竞品调研自动化工具")
st.info("This is the only user-facing entrypoint. Normal report generation should happen in this app, not by editing or running pipeline scripts.")

st.markdown("""
---

**What this tool does / 这个工具做什么：**

| Step | Description |
|------|-------------|
| **🔑 API Setup** | Connect your YouTube API key and configure your niche |
| **🔍 Channel Discovery** | Find competitor channels by keywords + detect rising channels |
| **📊 Deep Analysis** | Analyze videos, engagement, content patterns, growth trends |
| **📥 Download Report** | Generate a comprehensive PDF report with actionable insights |

---
""")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 🎯 Niche-Focused")
    st.markdown(
        "Input your niche keywords, and the tool automatically finds "
        "competitor channels and analyzes their content strategy."
    )

with col2:
    st.markdown("#### 📈 Growth Detection")
    st.markdown(
        "Identify channels with explosive recent growth using our "
        "view velocity algorithm — no historical data needed."
    )

with col3:
    st.markdown("#### 💰 Monetization Plan")
    st.markdown(
        "Get a 0→1000 subscriber roadmap with revenue projections "
        "for AdSense, courses, membership, and affiliates."
    )

st.markdown("---")

st.markdown("""
> **⚡ Tip**: Use the left sidebar to navigate between pages, or click the page tabs above.
>
> **🔧 First time?** Start with the **🔑 API Setup** page to connect your YouTube API key.
> Need help getting an API key? The setup page includes a step-by-step tutorial.
>
> **🚪 One entry only**: If you want a report as a user, stay inside this app flow. The CLI pipeline is kept under `internal/cli/` for internal baselines only.
""")
