# YouTube Competitive Research Tool

YouTube 竞品调研自动化工具 — 基于 Streamlit + YouTube Data API v3

## Scope

This repository is intentionally trimmed to two execution surfaces only:

- `app.py` via Streamlit for normal user-facing analysis
- `internal/cli/run_pipeline_v5.py` for internal baseline validation

Do not add new parallel runners or scratch utilities unless they are wired into one of those two entrypoints.

## User Entry

For normal use, there is only one entrypoint: `app.py` via Streamlit.

If you are a user who wants to generate a report, you should not need to edit Python files or run internal pipeline scripts.

The CLI baseline is kept only for internal validation and lives at `internal/cli/run_pipeline_v5.py`.

Historical pipeline snapshots and standalone transcript/cookie helper scripts have been removed so the repository stays centered on the shipped app flow and the current internal baseline.

Generated artifacts under `output/` are operational byproducts, not maintained source assets.
Keep only the latest validated report set plus the canonical CSV exports needed for the current handoff.

## Configuration

The Streamlit app does not need a local secrets file for normal use. Users enter their YouTube API key in the UI and it stays in the browser session.

The internal CLI baseline expects environment variables from the shell or deployment platform. `.env.example` is a template only; this repository does not auto-load `.env` files.

This public repository is kept free of runtime credentials:

- no committed YouTube API key
- no committed DeepSeek API key
- no committed cookie files
- local `.env` files and `.streamlit/secrets.toml` are ignored

Required for `internal/cli/run_pipeline_v5.py`:

- `YOUTUBE_API_KEY`
- `DEEPSEEK_API_KEY`

Optional overrides for the internal baseline:

- `DEEPSEEK_MODEL`
- `YT_RESEARCH_*`

## Features

- **🔑 API Setup**: Step-by-step API key setup and niche configuration
- **🔍 Channel Discovery**: Keyword-based competitor discovery with recent-growth checks
- **📊 Deep Analysis**: Channel/video comparison, transcript-assisted pattern extraction, and charts
- **📥 Report Export**: Downloadable PDF plus raw CSV and transcript exports

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

```bash
streamlit run app.py
```

### 3. Open in browser

The app will open at `http://localhost:8501`

### 4. Run the internal baseline CLI

PowerShell example:

```powershell
$env:YOUTUBE_API_KEY="your_youtube_api_key"
$env:DEEPSEEK_API_KEY="your_deepseek_api_key"
python internal/cli/run_pipeline_v5.py
```

## Usage Flow

1. **🔑 API Setup**: Enter your YouTube API key + select niche preset or custom keywords
2. **🔍 Channel Discovery**: Search → view results → select channels for analysis
3. **📊 Deep Analysis**: Click "Start" → watch 8-step progress → explore interactive dashboard
4. **📥 Download**: Download PDF report + raw CSV data

## Limits

- Growth signals are comparative, not predictive.
- Transcript coverage depends on what YouTube exposes and can be partial.
- Publish timing summaries describe the observed sample and should not be treated as guaranteed winning slots.
- Revenue numbers are rough scenarios, not commitments or forecasts.

## Getting a YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "YouTube Data API v3"
4. Create an API key under Credentials
5. Paste into the app

> Free tier: 10,000 units/day. One full analysis uses ~200-500 units.

## Deploy to Cloud (Streamlit Community Cloud)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file path: `app.py`
5. Deploy

> Note: keep the public Streamlit deployment on the app flow. The internal CLI baseline should stay behind operator-controlled environment variables.

## Project Structure

```
├── app.py                          # Only user-facing entrypoint
├── pages/
│   ├── 1_🔑_API_Setup.py          # API key + niche config
│   ├── 2_🔍_Channel_Discovery.py  # Channel search + growth detection
│   ├── 3_📊_Deep_Analysis.py      # Analysis pipeline + dashboard
│   └── 4_📥_Download_Report.py    # PDF preview + download
├── core/
│   ├── fetcher.py                  # YouTube API data fetching
│   ├── analyzer.py                 # Data analysis + metrics
│   ├── visualizer.py               # Charts (Plotly + Matplotlib)
│   ├── growth_detector.py          # Rising channel detection
│   ├── strategy_advisor.py         # Growth plan + monetization
│   └── report_generator.py         # PDF report (fpdf2)
├── internal/
│   └── cli/
│       └── run_pipeline_v5.py      # Internal baseline runner, not user entry
├── .env.example                    # Shell/deployment env template for CLI baseline
├── requirements.txt
└── .streamlit/config.toml          # Theme config
```

## Tech Stack

| Component | Library |
|-----------|---------|
| Web UI | Streamlit |
| YouTube API | google-api-python-client |
| Transcripts | youtube-transcript-api (zero quota) |
| Data | pandas, numpy |
| Charts | Plotly (interactive), Matplotlib (word clouds) |
| Chinese NLP | jieba |
| PDF | fpdf2 |

## API Quota Optimization

This tool is optimized to minimize YouTube API quota usage:

| Operation | Standard Cost | Our Approach | Savings |
|-----------|--------------|--------------|---------|
| Find channel videos | search.list (100/req) | playlistItems.list (1/req) | **99%** |
| Video details | videos.list (1/50 videos) | Batch requests | Optimal |
| Transcripts | captions API (OAuth required) | youtube-transcript-api | **Free** |

Typical full analysis: **~200-500 units** out of 10,000 daily quota.
