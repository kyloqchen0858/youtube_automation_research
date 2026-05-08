# Tool Guide

## Purpose

This project is a YouTube research and strategy tool, not just a channel scraper.

It does three jobs together:

1. find relevant competitor channels and videos for a chosen topic,
2. separate reliable signals from noisy signals,
3. turn those signals into strategy output and reports.

The only user-facing entrypoint is `app.py` for the Streamlit product flow.

`internal/cli/run_pipeline_v5.py` still exists as an internal baseline runner, but users should not need it to generate reports.

## End-to-End Workflow

### 1. Strategy Brief

The tool starts from a `StrategyBrief`.

This is the intent layer: what topic you are researching, what content direction you want, what kind of channel you are building, and what constraints matter.

Without this layer, the tool falls back to generic competitor scraping. With it, later ranking and planning are much more opinionated.

The workflow mode inside the brief is now operational, not just descriptive:

- `analysis_quality`: prefers reliable growth windows and more conservative strategy sources,
- `horizontal_benchmark`: keeps evidence broad across channels,
- `vertical_optimize`: focuses strategy on the first selected target channel,
- `single_viral`: prioritizes breakout-style outliers and replication clues.

### 2. Channel Discovery

The discovery step searches YouTube by keywords, collects candidate channels, then filters them by basic viability signals such as subscriber count, total views, average views per video, and recent activity.

This step answers: “Which channels are even worth comparing?”

### 3. Video / Comment / Transcript Collection

For shortlisted channels, the tool fetches:

- recent videos,
- comments from higher-view videos,
- transcripts where available.

For transcripts, the fetcher now tries the normal transcript API first and then a best-effort `yt-dlp` automatic-caption fallback.

That fallback improves coverage, but it is still subject to YouTube rate limits. If timedtext endpoints return `429`, the tool will continue without pretending it has transcript evidence.

This is the raw evidence layer. If transcript availability is low, strategy quality drops because the tool has less direct content-structure evidence.

### 4. Reliability and Growth Layer

Growth is measured with a fixed window: recent 3 months vs previous 3 months.

If one side of the window does not have enough videos, the channel is marked as insufficient instead of forcing a misleading comparison. This is one of the project’s core honesty constraints.

This layer now also includes deterministic decline diagnostics for channels that are reliably down over the fixed window.

The tool tries to separate:

- objective decline: publishing slowdown, post-viral mean reversion, unstable baseline,
- strategy decline: weaker packaging, topic drift, engagement deterioration, large format shifts,
- mixed decline: both forces at the same time.

### 5. Competitor Radar

`core/competitor_radar.py` does not simply rank by size.

It scores channels and breakout videos by topic relevance, format fit, execution fit, freshness, and growth context. That is why a smaller but tightly aligned channel can outrank a larger but loosely related channel.

This step answers: “Who should we learn from first?”

### 6. Reverse Engineering

`core/reverse_engineering.py` extracts patterns from the radar shortlist and available transcript evidence.

It looks for:

- dominant formats,
- title formulas,
- hook formulas,
- topic clusters,
- audience praise patterns,
- audience gap patterns,
- recommended adaptations.

This step answers: “What exactly is working inside the shortlisted competitors?”

### 7. Strategy Planning

`core/strategy_advisor.py` takes the brief, radar results, and reverse-engineering playbook and produces:

- north-star goal,
- milestones,
- checkpoint rules,
- weekly operating rules,
- confidence notes,
- recommended formats.

This step answers: “What should a new channel actually do next?”

### 8. Reports

The tool now produces three main outputs plus an evaluation:

- `DeepSeek` analysis report: concise synthesis, prioritization, decline diagnosis, strategic judgment.
- `Execution Manual`: a shorter operator-facing backlog and SOP document.
- `Copilot` report: statistics-first, less interpretive, more audit-like.

There is also an evaluation report that compares the two.

The intended use is not “pick one winner forever,” but “cross-check narrative against data and then move into execution quickly.”

## Why There Are Two Main Reports

The two reports play different roles.

`Copilot` is the control group. It is useful when you want to see what the raw numbers support without much creative synthesis.

`DeepSeek` is the strategy layer. It is useful when you want packaging ideas, decline interpretation, and a compressed directional read.

`Execution Manual` is the operator layer. It is useful when you already agree with the direction and need the next 30 days reduced to backlog, cadence, SOP, and guardrails.

If both reports point in the same direction, confidence increases.

If they disagree, treat that as a signal to inspect the evidence more closely rather than trusting the more persuasive wording.

## Visualization Logic

The visual layer lives in `core/visualizer.py`.

It is not decorative. Each chart is intended to answer a specific decision question.

### Top Videos Bar

Function: `plot_top_videos_bar`

What it shows:

- the top `N` videos by a chosen metric, usually views,
- shortened titles for readability,
- hover details for original title and channel.

How to use it:

- find which specific videos are pulling the benchmark upward,
- inspect whether the winners come from one channel or multiple channels,
- use it to pick videos for manual teardown.

Caveat:

This is a winner list, not a distribution view. It highlights standout outcomes but can hide what is normal.

### Duration Scatter

Function: `plot_duration_scatter`

What it shows:

- x-axis: duration in minutes,
- y-axis: views,
- color: engagement rate when available,
- point size: view count.

How to use it:

- find the duration cluster where good view volume and decent engagement overlap,
- detect whether very long videos only work for a few outliers,
- compare “short and sharp” vs “long and deep” styles.

Caveat:

Large outliers visually dominate the chart. Use the median-based duration summary alongside it.

### Publish Heatmap

Function: `plot_publish_heatmap`

What it shows:

- weekday on one axis,
- UTC hour on the other,
- color intensity from the heatmap matrix.

How to use it:

- identify where channels cluster their publishing behavior,
- see whether the niche is concentrated around a few time windows,
- choose an initial publishing cadence to test.

Caveat:

This chart reflects publishing distribution, not guaranteed publishing performance. It tells you where channels post, not automatically where they win.

### Channel Comparison Radar

Function: `plot_channel_comparison_radar`

What it shows:

- normalized scores for subscriber count,
- average views,
- top views,
- average duration,
- growth ratio.

How normalization works:

Each metric is scaled relative to the maximum value inside the current comparison set, mapping to `0-100`.

That means the radar is for shape comparison, not absolute scale.

How to use it:

- compare channel profiles quickly,
- spot whether a channel wins by scale, by efficiency, or by growth,
- distinguish “big but stale” from “smaller but sharper.”

Caveat:

Because normalization is relative, changing the comparison set changes the picture.

### Growth Trend

Function: `plot_growth_trend`

What it shows:

- chronological view counts by publish date,
- a linear trend line when there are enough points.

How to use it:

- inspect whether the channel’s baseline is rising, flat, or slipping,
- see if performance depends on one or two spikes,
- cross-check whether a claimed “growing channel” actually has a healthier baseline.

Caveat:

The trend line is a simple linear fit, not a forecast. Use it as a direction hint only.

### Title Word Cloud

Function: `plot_title_wordcloud`

What it shows:

- high-frequency title keywords after preprocessing.

How to use it:

- see repeated language patterns,
- spot topical concentration,
- identify packaging vocabulary worth testing.

Caveat:

Frequency is not the same as causal importance. A word can be common without being the reason something wins.

### Comment Word Cloud

Function: `plot_comment_wordcloud`

What it shows:

- repeated audience vocabulary from comments.

How to use it:

- find viewer language for pains, praise, confusion, and desired outcomes,
- improve title and hook wording by matching audience phrasing,
- identify repeated use cases or frustrations.

Caveat:

Comment samples are usually biased toward higher-view videos, so this is a directional signal, not a population-perfect survey.

## How To Read The Output In Practice

For a new topic, the fastest reading order is:

1. read the radar shortlist,
2. check reliable growth vs insufficient windows,
3. inspect top videos and duration cluster,
4. inspect transcript and comment insights,
5. read weekly rules and checkpoint rules,
6. only then decide what the first 3-5 videos should be.

This avoids the common mistake of jumping from raw views straight to topic copying.

## Current Limits

The tool is materially stronger than the earlier keyword-only version, but a few limits still matter:

1. transcript-driven analysis is still constrained by subtitle availability,
2. comments are sampled from higher-view videos, so they overrepresent what already broke out,
3. Streamlit workflow mode / stage wiring is still only partial,
4. some legacy report surfaces are still more statistics-first than evidence-synthesis-first.

Those are real constraints, not just polishing items.