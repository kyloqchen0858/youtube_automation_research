"""
Page 1: API Setup & Niche Configuration
API 设置 + 赛道配置
"""

import streamlit as st
from core.fetcher import YouTubeFetcher
from core.strategy_models import get_strategy_brief, sync_strategy_brief

st.set_page_config(page_title="API Setup", page_icon="🔑", layout="wide")

st.title("🔑 API Setup & Niche Configuration")
st.markdown("### API 设置与赛道配置")

# ── Section 1: API Key Tutorial ─────────────────────────────
with st.expander("📖 How to Get a YouTube API Key / 如何获取 API Key（点击展开教程）", expanded=not st.session_state.get("api_key_valid", False)):
    st.markdown("""
    **Step-by-step guide / 分步教程：**

    **Step 1**: Go to [Google Cloud Console](https://console.cloud.google.com/)
    - Sign in with your Google account / 用 Google 账号登录

    **Step 2**: Create a new project / 创建新项目
    - Click "Select a project" → "NEW PROJECT"
    - Name it anything, e.g., "YouTube Research"
    - Click "CREATE"

    **Step 3**: Enable YouTube Data API v3 / 启用 API
    - In the left menu, go to "APIs & Services" → "Library"
    - Search for "YouTube Data API v3"
    - Click on it → Click "ENABLE"

    **Step 4**: Create API Key / 创建密钥
    - Go to "APIs & Services" → "Credentials"
    - Click "+ CREATE CREDENTIALS" → "API key"
    - Copy the generated key

    **Step 5**: Paste the key below / 粘贴到下方输入框

    ---
    > ⚠️ **Free quota**: 10,000 units/day. This tool is optimized to use ~200-500 units per full analysis.
    >
    > 💡 **Security**: Your API key is stored only in your browser session and never saved to disk.
    """)

# ── Section 2: API Key Input ────────────────────────────────
st.markdown("---")
st.markdown("### 🔐 Enter Your API Key")

col1, col2 = st.columns([3, 1])

with col1:
    api_key = st.text_input(
        "YouTube Data API Key",
        type="password",
        value=st.session_state.get("api_key", ""),
        placeholder="AIzaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        help="Paste your API key here. It will not be stored permanently.",
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    validate_btn = st.button("✅ Validate Key", use_container_width=True)

if validate_btn and api_key:
    with st.spinner("Validating API key..."):
        try:
            fetcher = YouTubeFetcher(api_key)
            if fetcher.validate_api_key():
                st.session_state.api_key = api_key
                st.session_state.api_key_valid = True
                st.success("✅ API Key is valid! You're ready to go.")
            else:
                st.session_state.api_key_valid = False
                st.error("❌ Invalid API Key. Please check and try again.")
        except Exception as e:
            st.session_state.api_key_valid = False
            st.error(f"❌ Validation failed: {str(e)}")

if st.session_state.get("api_key_valid"):
    st.info("✅ API Key is connected and valid.")

# ── Section 3: Niche Configuration ──────────────────────────
st.markdown("---")
st.markdown("### 🎯 Niche Configuration / 赛道配置")

# Preset templates
NICHE_PRESETS = {
    "AI Workflow Tutorials / AI 工作流教程": {
        "description": "AI 工作流 / 自动化教程，面向创作者与小团队运营者",
        "keywords_en": [
            "ai workflow tutorial",
            "ai agent tutorial",
            "chatgpt workflow tutorial",
            "cursor tutorial",
            "n8n ai automation",
            "claude workflow",
            "ai tools for creators",
        ],
        "keywords_zh": [
            "AI 工作流 教程",
            "AI 自动化",
            "AI agent 教程",
            "创作者 AI 工具",
            "运营 自动化",
            "提示词 工作流",
        ],
    },
    "Ancient Wisdom × Career/Business (古代智慧 × 职场商业)": {
        "description": "职场发展/自由职业 + 中国古代智慧",
        "keywords_en": [
            "Sun Tzu Art of War business strategy",
            "ancient wisdom career success",
            "Tao Te Ching leadership",
            "36 stratagems business",
            "stoicism entrepreneurship",
            "philosophy freelance",
            "eastern philosophy career",
        ],
        "keywords_zh": [
            "孙子兵法 商业策略",
            "鬼谷子 职场",
            "道德经 创业",
            "曾国藩 管理智慧",
            "资治通鉴 领导力",
            "古代智慧 自由职业",
            "国学 商业思维",
        ],
    },
    "Self Improvement / 个人成长": {
        "description": "个人成长/自我提升",
        "keywords_en": [
            "self improvement tips",
            "productivity habits",
            "mindset shift",
            "personal development",
            "life advice",
        ],
        "keywords_zh": [
            "个人成长",
            "自律习惯",
            "思维升级",
            "认知提升",
        ],
    },
    "Freelance & Solopreneur / 自由职业": {
        "description": "自由职业/一人创业",
        "keywords_en": [
            "freelance tips",
            "solopreneur",
            "work from home business",
            "online business start",
            "side hustle to full time",
        ],
        "keywords_zh": [
            "自由职业 赚钱",
            "副业 全职",
            "一人公司",
            "远程工作",
        ],
    },
    "Custom / 自定义": {
        "description": "",
        "keywords_en": [],
        "keywords_zh": [],
    },
}

# Niche selector
selected_niche = st.selectbox(
    "Select a niche preset / 选择赛道模板",
    list(NICHE_PRESETS.keys()),
    index=0,
    help="Choose a preset or select 'Custom' to define your own keywords",
)

preset = NICHE_PRESETS[selected_niche]

# Niche description
niche_description = st.text_input(
    "Niche Description / 赛道描述",
    value=preset["description"],
    placeholder="e.g., AI 工作流 / 自动化教程，面向创作者与运营者",
)

# Keywords
col_en, col_zh = st.columns(2)

with col_en:
    keywords_en = st.text_area(
        "English Keywords (one per line)",
        value="\n".join(preset["keywords_en"]),
        height=200,
        help="One keyword per line. These will be used to search YouTube.",
    )

with col_zh:
    keywords_zh = st.text_area(
        "中文关键词 (每行一个)",
        value="\n".join(preset["keywords_zh"]),
        height=200,
        help="每行一个关键词，用于搜索 YouTube。",
    )

# Additional channel IDs
st.markdown("#### 📺 Additional Channel IDs (Optional)")
st.markdown("If you already know specific competitor channel IDs, paste them here (one per line):")
manual_channels = st.text_area(
    "Channel IDs",
    placeholder="UCxxxxxxxxxxxxxxxxxx\nUCyyyyyyyyyyyyyyyyyy",
    height=100,
    help="Channel ID format: UC... (24 characters). Find it from the channel page URL.",
)

# Save configuration
st.markdown("---")

if st.button("💾 Save Configuration / 保存配置", type="primary", use_container_width=True):
    # Parse keywords
    all_keywords = []
    if keywords_en:
        all_keywords.extend([kw.strip() for kw in keywords_en.strip().split("\n") if kw.strip()])
    if keywords_zh:
        all_keywords.extend([kw.strip() for kw in keywords_zh.strip().split("\n") if kw.strip()])

    # Parse channel IDs
    manual_ch_ids = []
    if manual_channels:
        manual_ch_ids = [ch.strip() for ch in manual_channels.strip().split("\n") if ch.strip()]

    if not all_keywords and not manual_ch_ids:
        st.error("Please enter at least one keyword or channel ID.")
    else:
        st.session_state.niche = niche_description
        st.session_state.keywords = all_keywords
        st.session_state.manual_channel_ids = manual_ch_ids

        brief = get_strategy_brief(st.session_state, niche_override=niche_description)
        updated_payload = brief.to_dict()
        updated_payload["niche"] = niche_description
        updated_payload["discovery_keywords"] = all_keywords
        sync_strategy_brief(st.session_state, brief.from_dict(updated_payload))

        st.success(
            f"✅ Configuration saved! "
            f"{len(all_keywords)} keywords + {len(manual_ch_ids)} manual channels.\n\n"
            f"👉 Go to **🔍 Channel Discovery** page to find competitor channels."
        )

# ── Status Summary ──────────────────────────────────────────
st.markdown("---")
st.markdown("### Current Configuration / 当前配置")

c1, c2, c3 = st.columns(3)
c1.metric("API Key", "✅ Valid" if st.session_state.get("api_key_valid") else "❌ Not Set")
c2.metric("Keywords", len(st.session_state.get("keywords", [])))
c3.metric("Manual Channels", len(st.session_state.get("manual_channel_ids", [])))
