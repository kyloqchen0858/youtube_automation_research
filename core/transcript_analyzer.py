"""Rule-based transcript intelligence for offline YouTube content analysis."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

MIN_TRANSCRIPT_WORDS = 80

STOPWORDS = {
    "about", "after", "again", "against", "also", "because", "before", "being",
    "between", "could", "every", "first", "from", "have", "here", "into", "just",
    "like", "more", "most", "much", "only", "other", "over", "really", "should",
    "some", "such", "than", "that", "their", "them", "then", "there", "these",
    "they", "this", "those", "through", "very", "want", "what", "when", "where",
    "which", "while", "with", "would", "your", "you're", "youre", "video", "channel",
    "people", "thing", "things", "going", "today", "about", "into", "dont", "that's",
}

HOOK_LABELS = {
    "direct_pain_promise": {
        "label": "Pain-first promise",
        "description": "Opens by naming the viewer's present problem and promising a concrete payoff within the first beat.",
    },
    "numbered_framework": {
        "label": "Numbered framework",
        "description": "Starts with a visible list, count, or rule-set so the viewer immediately knows the path of the video.",
    },
    "authority_source": {
        "label": "Authority-source opening",
        "description": "Leads with a book, thinker, doctrine, or source text to borrow authority before interpretation begins.",
    },
    "story_or_personal": {
        "label": "Host-led anecdote",
        "description": "Begins with the creator's own voice, scene-setting, or personal framing before moving into the lesson.",
    },
    "warning_boundary": {
        "label": "Warning / boundary hook",
        "description": "Uses 'never', 'don't', 'stop', or other loss-aversion language to create urgency and emotional tension.",
    },
    "question_challenge": {
        "label": "Question / belief challenge",
        "description": "Kicks off with a provocative question or challenge to the viewer's current assumption.",
    },
}

STRUCTURE_LABELS = {
    "numbered_breakdown": {
        "label": "Numbered breakdown",
        "description": "Main body is built around explicit steps, lessons, rules, or points that are easy to skim and remember.",
    },
    "problem_solution": {
        "label": "Problem-solution flow",
        "description": "Names the pain, expands the stakes, and then resolves it with a framework, reframe, or action sequence.",
    },
    "book_summary_reframe": {
        "label": "Book/source summary",
        "description": "Takes a dense source text and reorganizes it into modern, usable lessons for the target audience.",
    },
    "qa_coaching": {
        "label": "Q&A coaching",
        "description": "Moves through repeated practical questions and answers, usually with concise formulas or interview-style guidance.",
    },
    "argumentative_essay": {
        "label": "Argumentative essay",
        "description": "Builds a thesis, contrasts competing views, and then lands on a larger interpretation or worldview.",
    },
    "source_narration": {
        "label": "Source narration",
        "description": "Uses long-form narration or chapter-style delivery, with the source material itself doing much of the heavy lifting.",
    },
}

PROMISE_LABELS = {
    "avoid_pain_or_loss": {
        "label": "Avoid pain / loss",
        "description": "Packages the topic around what the viewer must stop, avoid, or prevent.",
    },
    "specific_framework": {
        "label": "Specific framework",
        "description": "Promises an exact count, formula, or concrete structure that reduces ambiguity before the click.",
    },
    "classic_source_translation": {
        "label": "Classic source translation",
        "description": "Uses a known book, philosopher, or historical source as the promise vehicle for modern relevance.",
    },
    "skill_upgrade": {
        "label": "Skill upgrade",
        "description": "Frames the video as a practical improvement in capability, decision quality, or communication.",
    },
    "belief_challenge": {
        "label": "Belief challenge",
        "description": "Sells the click by attacking a current assumption or inviting the viewer into a debate.",
    },
}

CTA_LABELS = {
    "subscribe_next_step": {
        "label": "Subscribe / next-step CTA",
        "description": "Ends with an explicit push to watch more, subscribe, or continue deeper into the content ecosystem.",
    },
    "comment_prompt": {
        "label": "Comment prompt",
        "description": "Closes by asking for a response, opinion, or personal story to drive interaction.",
    },
    "description_resource": {
        "label": "Description resource CTA",
        "description": "Uses a link, checklist, download, playlist, or off-platform resource as the final conversion step.",
    },
    "action_command": {
        "label": "Action command",
        "description": "Ends by telling the viewer exactly what to do next in life, work, or practice.",
    },
    "reflective_close": {
        "label": "Reflective close",
        "description": "Closes on an idea, quote, or emotional landing instead of a hard conversion move.",
    },
}

EVIDENCE_LABELS = {
    "historical_or_textual": {
        "label": "Historical / textual authority",
        "description": "Uses books, philosophers, history, doctrines, or canonical material as the main trust anchor.",
    },
    "personal_experience": {
        "label": "Personal experience",
        "description": "Uses the creator's own life, feelings, or observation as an interpretive frame.",
    },
    "teaching_examples": {
        "label": "Worked examples",
        "description": "Relies on examples, imagined situations, and concrete cases to make the lesson easy to transfer.",
    },
    "research_or_data": {
        "label": "Research / data",
        "description": "Leans on studies, reports, numbers, or formal evidence to support the claim.",
    },
    "direct_coaching": {
        "label": "Direct coaching",
        "description": "Speaks straight to the viewer's next move using imperative, advisory, or training language.",
    },
}


def analyze_transcript_patterns(
    transcripts: Any,
    video_info_map: dict[str, Any] | None = None,
    max_videos: int = 10,
) -> dict[str, Any]:
    """Analyze transcript structure, hook patterns, and reusable script templates."""
    records = _normalize_transcript_records(transcripts, video_info_map)
    usable_records = []

    for record in records:
        normalized_text = _normalize_text(record.get("text", ""))
        word_count = _count_words(normalized_text)
        if word_count < MIN_TRANSCRIPT_WORDS:
            continue
        record["text"] = normalized_text
        record["word_count"] = word_count
        usable_records.append(record)

    if not usable_records:
        return {
            "has_data": False,
            "message": "No transcript sample was large enough for structural analysis.",
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
            "method_note": "Offline rule-based transcript parsing was skipped because no usable transcript text was available.",
        }

    usable_records.sort(key=lambda item: (item.get("view_count", 0), item.get("word_count", 0)), reverse=True)
    selected_records = usable_records[:max_videos] if max_videos > 0 else usable_records

    features = []
    for record in selected_records:
        opening = _opening_excerpt(record["text"])
        closing = _closing_excerpt(record["text"])
        title = record.get("title", "")

        feature = {
            "video_id": record.get("video_id", ""),
            "title": title,
            "channel_title": record.get("channel_title", "Unknown"),
            "view_count": record.get("view_count", 0),
            "published_at": record.get("published_at"),
            "word_count": record.get("word_count", 0),
            "hook_type": _classify_hook(title, opening),
            "structure_type": _classify_structure(title, record["text"]),
            "promise_type": _classify_promise(title, opening),
            "cta_type": _classify_cta(closing),
            "evidence_type": _classify_evidence(record["text"]),
            "opening_excerpt": opening[:180],
            "closing_excerpt": closing[:180],
        }
        features.append(feature)

    total_words = sum(item["word_count"] for item in features)
    analyzed_channels = {item["channel_title"] for item in features}

    hook_patterns = _summarize_patterns(features, "hook_type", HOOK_LABELS)
    structure_patterns = _summarize_patterns(features, "structure_type", STRUCTURE_LABELS)
    promise_patterns = _summarize_patterns(features, "promise_type", PROMISE_LABELS)
    cta_patterns = _summarize_patterns(features, "cta_type", CTA_LABELS)
    evidence_patterns = _summarize_patterns(features, "evidence_type", EVIDENCE_LABELS)

    return {
        "has_data": True,
        "message": "Transcript intelligence generated from local transcript text without using any LLM or external API.",
        "coverage": {
            "candidate_videos": len(usable_records),
            "analyzed_videos": len(features),
            "analyzed_channels": len(analyzed_channels),
            "total_words": total_words,
            "avg_words_per_video": int(total_words / max(len(features), 1)),
        },
        "hook_patterns": hook_patterns,
        "structure_patterns": structure_patterns,
        "promise_patterns": promise_patterns,
        "cta_patterns": cta_patterns,
        "evidence_patterns": evidence_patterns,
        "signal_terms": _extract_signal_terms(features),
        "video_breakdowns": features,
        "channel_signatures": _build_channel_signatures(features),
        "evolution_signals": _build_evolution_signals(features),
        "strategy_recommendations": _build_strategy_recommendations(
            hook_patterns,
            structure_patterns,
            promise_patterns,
            cta_patterns,
            evidence_patterns,
        ),
        "script_templates": _build_script_templates(
            hook_patterns,
            structure_patterns,
            promise_patterns,
            cta_patterns,
            evidence_patterns,
        ),
        "method_note": (
            "Offline rule-based parsing of title packaging, opening hooks, closing CTAs, and recurring transcript structures. "
            "Use it when API quota is blocked or when you want to validate transcript patterns against saved transcript archives."
        ),
    }


def _normalize_transcript_records(
    transcripts: Any,
    video_info_map: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    video_info_map = video_info_map or {}

    if isinstance(transcripts, list):
        iterable = []
        for item in transcripts:
            if not isinstance(item, dict):
                continue
            iterable.append((item.get("video_id", ""), item))
    elif isinstance(transcripts, dict):
        iterable = list(transcripts.items())
    else:
        iterable = []

    for video_id, raw_value in iterable:
        title = ""
        channel_title = ""
        view_count = 0
        published_at = None

        if isinstance(raw_value, dict):
            text = raw_value.get("text") or raw_value.get("transcript") or ""
            title = raw_value.get("title", "")
            channel_title = raw_value.get("channel_title") or raw_value.get("channel", "")
            view_count = _safe_int(raw_value.get("view_count", raw_value.get("views", 0)))
            published_at = raw_value.get("published_at")
        else:
            text = str(raw_value or "")

        info = video_info_map.get(video_id, {}) if video_id else {}
        title = title or info.get("title", "")
        channel_title = channel_title or info.get("channel_title") or info.get("channel", "Unknown")
        view_count = view_count or _safe_int(info.get("view_count", info.get("views", 0)))
        published_at = published_at or info.get("published_at")

        records.append(
            {
                "video_id": video_id,
                "title": title or video_id or "Untitled transcript",
                "channel_title": channel_title or "Unknown",
                "view_count": view_count,
                "published_at": published_at,
                "text": text,
            }
        )

    return records


def _summarize_patterns(
    features: list[dict[str, Any]],
    key: str,
    label_map: dict[str, dict[str, str]],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    counter = Counter(feature[key] for feature in features)
    total = max(len(features), 1)
    summarized = []

    for pattern_key, count in counter.most_common(top_n):
        meta = label_map[pattern_key]
        examples = [
            feature["title"]
            for feature in sorted(features, key=lambda item: item.get("view_count", 0), reverse=True)
            if feature[key] == pattern_key
        ][:3]
        summarized.append(
            {
                "key": pattern_key,
                "label": meta["label"],
                "description": meta["description"],
                "count": count,
                "share": round(count / total, 2),
                "confidence": _confidence_label(count / total),
                "examples": examples,
            }
        )

    return summarized


def _build_channel_signatures(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feature in features:
        grouped[feature["channel_title"]].append(feature)

    signatures = []
    for channel_title, items in grouped.items():
        hook_key = _most_common_key(items, "hook_type")
        structure_key = _most_common_key(items, "structure_type")
        promise_key = _most_common_key(items, "promise_type")
        cta_key = _most_common_key(items, "cta_type")

        signatures.append(
            {
                "channel": channel_title,
                "videos": len(items),
                "avg_views": int(sum(item.get("view_count", 0) for item in items) / max(len(items), 1)),
                "dominant_hook": HOOK_LABELS[hook_key]["label"],
                "dominant_structure": STRUCTURE_LABELS[structure_key]["label"],
                "dominant_promise": PROMISE_LABELS[promise_key]["label"],
                "dominant_cta": CTA_LABELS[cta_key]["label"],
                "summary": (
                    f"{channel_title} mostly wins with {HOOK_LABELS[hook_key]['label'].lower()} hooks and "
                    f"{STRUCTURE_LABELS[structure_key]['label'].lower()} structure, usually packaging the click as "
                    f"{PROMISE_LABELS[promise_key]['label'].lower()} and closing with "
                    f"{CTA_LABELS[cta_key]['label'].lower()}."
                ),
            }
        )

    signatures.sort(key=lambda item: (item["videos"], item["avg_views"]), reverse=True)
    return signatures


def _build_evolution_signals(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feature in features:
        if feature.get("published_at"):
            grouped[feature["channel_title"]].append(feature)

    evolution = []
    for channel_title, items in grouped.items():
        if len(items) < 3:
            continue
        items.sort(key=lambda item: _published_sort_key(item.get("published_at")))

        split = max(1, len(items) // 2)
        early = items[:split]
        recent = items[-split:]

        early_hook = _most_common_key(early, "hook_type")
        recent_hook = _most_common_key(recent, "hook_type")
        early_structure = _most_common_key(early, "structure_type")
        recent_structure = _most_common_key(recent, "structure_type")

        if early_hook == recent_hook and early_structure == recent_structure:
            summary = (
                f"{channel_title} kept a stable content spine from earlier videos into the recent sample: "
                f"{HOOK_LABELS[recent_hook]['label'].lower()} plus {STRUCTURE_LABELS[recent_structure]['label'].lower()}."
            )
        else:
            change_parts = []
            if early_hook != recent_hook:
                change_parts.append(
                    f"hook shifted from {HOOK_LABELS[early_hook]['label'].lower()} to {HOOK_LABELS[recent_hook]['label'].lower()}"
                )
            if early_structure != recent_structure:
                change_parts.append(
                    f"structure shifted from {STRUCTURE_LABELS[early_structure]['label'].lower()} to {STRUCTURE_LABELS[recent_structure]['label'].lower()}"
                )
            summary = f"{channel_title} shows format drift in the transcript sample: " + "; ".join(change_parts) + "."

        evolution.append(
            {
                "channel": channel_title,
                "summary": summary,
                "early_hook": HOOK_LABELS[early_hook]["label"],
                "recent_hook": HOOK_LABELS[recent_hook]["label"],
                "early_structure": STRUCTURE_LABELS[early_structure]["label"],
                "recent_structure": STRUCTURE_LABELS[recent_structure]["label"],
            }
        )

    return evolution


def _build_strategy_recommendations(
    hook_patterns: list[dict[str, Any]],
    structure_patterns: list[dict[str, Any]],
    promise_patterns: list[dict[str, Any]],
    cta_patterns: list[dict[str, Any]],
    evidence_patterns: list[dict[str, Any]],
) -> list[dict[str, str]]:
    recommendations = []

    if hook_patterns:
        top_hook = hook_patterns[0]
        recommendations.append(
            {
                "title": "Front-load the payoff",
                "recommendation": "Open with the viewer's pain, tension, or promised payoff before any long background setup.",
                "evidence": f"{top_hook['share']:.0%} of the transcript sample uses {top_hook['label'].lower()} as the opening move.",
                "confidence": top_hook["confidence"],
            }
        )

    if structure_patterns:
        top_structure = structure_patterns[0]
        recommendations.append(
            {
                "title": "Package long ideas as guided structure",
                "recommendation": "Even when the source material is deep, translate it into visible steps, sections, or clearly signposted narrative blocks.",
                "evidence": f"The dominant transcript structure is {top_structure['label'].lower()} ({top_structure['share']:.0%} share).",
                "confidence": top_structure["confidence"],
            }
        )

    if promise_patterns:
        top_promise = promise_patterns[0]
        recommendations.append(
            {
                "title": "Sell the click with a stronger promise",
                "recommendation": "Package videos around either a concrete framework, a risk to avoid, or a belief to challenge instead of generic inspiration.",
                "evidence": f"Top title promise pattern: {top_promise['label'].lower()} ({top_promise['share']:.0%} share).",
                "confidence": top_promise["confidence"],
            }
        )

    if evidence_patterns:
        top_evidence = evidence_patterns[0]
        recommendations.append(
            {
                "title": "Ground authority in something visible",
                "recommendation": "Anchor each video in a source, example, or direct coaching frame that the audience can immediately trust and reuse.",
                "evidence": f"Most transcripts rely on {top_evidence['label'].lower()} to carry trust.",
                "confidence": top_evidence["confidence"],
            }
        )

    if cta_patterns:
        top_cta = cta_patterns[0]
        if top_cta["key"] == "reflective_close":
            recommendation = "Keep CTAs soft and aligned with the tone: use a reflective landing plus one low-friction next step instead of a hard sell."
        elif top_cta["key"] == "description_resource":
            recommendation = "Move the viewer from video to asset: end with a free worksheet, guide, playlist, or download instead of stopping at inspiration."
        else:
            recommendation = "Design the final 10-20 seconds as a deliberate conversion move instead of letting the video fade out without direction."
        recommendations.append(
            {
                "title": "Make the last beat intentional",
                "recommendation": recommendation,
                "evidence": f"Dominant closing pattern: {top_cta['label'].lower()} ({top_cta['share']:.0%} share).",
                "confidence": top_cta["confidence"],
            }
        )

    return recommendations[:5]


def _build_script_templates(
    hook_patterns: list[dict[str, Any]],
    structure_patterns: list[dict[str, Any]],
    promise_patterns: list[dict[str, Any]],
    cta_patterns: list[dict[str, Any]],
    evidence_patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    templates = []
    added = set()

    top_cta_key = cta_patterns[0]["key"] if cta_patterns else "reflective_close"
    top_evidence_key = evidence_patterns[0]["key"] if evidence_patterns else "direct_coaching"
    top_hook_key = hook_patterns[0]["key"] if hook_patterns else "direct_pain_promise"

    for structure in structure_patterns[:3]:
        structure_key = structure["key"]
        template = _template_for_structure(structure_key, top_hook_key, top_cta_key, top_evidence_key, structure)
        if template and template["name"] not in added:
            templates.append(template)
            added.add(template["name"])

    if "Classic Wisdom to Modern Tension" not in added:
        templates.append(
            {
                "name": "Classic Wisdom to Modern Tension",
                "why_it_works": "The transcript sample repeatedly wins by translating an existing authority source into a concrete modern payoff.",
                "evidence": _pattern_evidence(structure_patterns, "book_summary_reframe", "classic-source framing")
                or _pattern_evidence(evidence_patterns, "historical_or_textual", "historical/textual authority"),
                "steps": [
                    "Open with a present-day fear or frustration in one sentence.",
                    "Bring in one ancient text, strategist, philosopher, or doctrine as the authority anchor.",
                    "Translate it into 3-5 modern lessons using clear numbered or signposted blocks.",
                    "After each lesson, add one workplace, creator, or life application so it never stays abstract.",
                    _cta_step(top_cta_key),
                ],
                "example_titles": [
                    "AI Workflows for Creators Who Hate Busywork",
                    "3 Automation Rules for Surviving Small-Team Chaos",
                ],
            }
        )

    return templates[:5]


def _template_for_structure(
    structure_key: str,
    top_hook_key: str,
    top_cta_key: str,
    top_evidence_key: str,
    structure: dict[str, Any],
) -> dict[str, Any] | None:
    hook_line = _hook_step(top_hook_key)
    evidence_line = _evidence_step(top_evidence_key)
    cta_line = _cta_step(top_cta_key)
    evidence = f"Observed transcript winner: {structure['label'].lower()} ({structure['share']:.0%} share)."

    if structure_key == "numbered_breakdown":
        return {
            "name": "Pain-First Numbered Breakdown",
            "why_it_works": "List structure lowers audience uncertainty, increases retention, and lets the creator keep dense material easy to follow.",
            "evidence": evidence,
            "steps": [
                hook_line,
                "Tell the viewer exactly how many lessons, rules, or mistakes you are about to cover.",
                "Give each point one sentence of principle and one sentence of consequence.",
                evidence_line,
                cta_line,
            ],
            "example_titles": [
                "7 Ancient Rules for Handling Career Chaos",
                "5 Mistakes Ambitious People Make When They Chase Status",
            ],
        }

    if structure_key == "book_summary_reframe":
        return {
            "name": "Modernized Source Summary",
            "why_it_works": "A dense source text becomes easier to binge when the creator acts like a translator, curator, and modern strategist at once.",
            "evidence": evidence,
            "steps": [
                hook_line,
                "Name the book, thinker, or source and tell the viewer why it matters now.",
                "Reorder the source into 3-5 modern takeaways instead of retelling it chapter by chapter.",
                evidence_line,
                cta_line,
            ],
            "example_titles": [
                "What The Art of War Actually Says About Modern Careers",
                "Marcus Aurelius for Burned-Out Knowledge Workers",
            ],
        }

    if structure_key == "qa_coaching":
        return {
            "name": "Question-Bank Coaching",
            "why_it_works": "This format works when the viewer already knows the situation they are in and wants a direct answer instead of inspiration.",
            "evidence": evidence,
            "steps": [
                hook_line,
                "State the exact scenario or question set the video will solve.",
                "Move through each question with one formula, one example, and one mistake to avoid.",
                evidence_line,
                cta_line,
            ],
            "example_titles": [
                "Top 5 AI Workflow Questions, Answered for Busy Operators",
                "What to Automate First When Your Team Is Drowning",
            ],
        }

    if structure_key == "argumentative_essay":
        return {
            "name": "Belief-Challenge Essay",
            "why_it_works": "Thesis-led essays win when the packaging promises a mental shift, not just a lesson list.",
            "evidence": evidence,
            "steps": [
                hook_line,
                "State the dominant belief you are challenging in plain language.",
                "Build the case with contrast, examples, and one clear through-line.",
                evidence_line,
                cta_line,
            ],
            "example_titles": [
                "Why Hustle Culture Misreads Ancient Discipline",
                "The Problem with Career Advice That Ignores Power",
            ],
        }

    if structure_key == "problem_solution":
        return {
            "name": "Problem to Reframe to Action",
            "why_it_works": "Good for viewers in immediate pain because it gives emotional recognition before tactics.",
            "evidence": evidence,
            "steps": [
                hook_line,
                "Name the cost of staying stuck in the problem.",
                "Introduce one reframe and then 3 practical moves.",
                evidence_line,
                cta_line,
            ],
            "example_titles": [
                "What to Do When You Feel Stuck but Can't Quit",
                "How to Think Clearly When Your Career Feels Unstable",
            ],
        }

    if structure_key == "source_narration":
        return {
            "name": "Narrated Wisdom with Guided Commentary",
            "why_it_works": "Long-form narration can keep authority high, but it works best when the creator adds clear interpretation checkpoints.",
            "evidence": evidence,
            "steps": [
                hook_line,
                "Frame the source and the listening goal before the narration begins.",
                "Break the narration into sections and insert short modern commentary between them.",
                evidence_line,
                cta_line,
            ],
            "example_titles": [
                "The Tao Te Ching for Modern Anxiety, Explained as You Listen",
                "A Guided Reading of The Prince for People in Competitive Careers",
            ],
        }

    return None


def _extract_signal_terms(features: list[dict[str, Any]], top_n: int = 12) -> list[str]:
    counter = Counter()
    for feature in features:
        text = f"{feature['title']} {feature['opening_excerpt']}"
        for token in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", text.lower()):
            if token in STOPWORDS or token.isdigit():
                continue
            counter[token] += 1
    return [token for token, _ in counter.most_common(top_n)]


def _classify_hook(title: str, opening: str) -> str:
    title_lower = title.lower()
    opening_lower = opening.lower()
    combined = f"{title_lower} {opening_lower}"

    if re.search(r"\b(never|don't|dont|stop|avoid|mistake|problem|protect|warning)\b", combined):
        return "warning_boundary"
    if re.search(r"\b(summary|chapter|book|meditations|art of war|discourses|stoic|narration)\b", combined):
        return "authority_source"
    if re.search(r"\b(top|rules|lessons|principles|questions|ways|things)\b", combined) or re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b", opening_lower):
        return "numbered_framework"
    if "?" in title or re.search(r"\b(why|was|problem with|wrong about|vs\.?|question)\b", title_lower):
        return "question_challenge"
    if re.search(r"\b(my name is|let me tell you|i was|i'm going to|im going to|before number one|okay)\b", opening_lower):
        return "story_or_personal"
    if re.search(r"\b(if you|you want|you need|struggling|worried|let's get into|lets get into|grab pen and paper)\b", opening_lower):
        return "direct_pain_promise"
    return "direct_pain_promise"


def _classify_structure(title: str, text: str) -> str:
    title_lower = title.lower()
    text_lower = text.lower()

    number_markers = _count_matches(
        text_lower,
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|first|second|third|fourth|fifth)\b",
    )
    question_markers = text.count("?") + _count_matches(text_lower, r"\b(question|answer|interview)\b")
    source_markers = _count_matches(text_lower, r"\b(chapter|book|meditations|discourses|sun tzu|marcus|epictetus|stoic|narration)\b")
    problem_markers = _count_matches(text_lower, r"\b(problem|solution|here's|heres|what you want to do|that means|therefore|so what)\b")

    if "summary" in title_lower or (source_markers >= 4 and "narration" not in title_lower and number_markers >= 3):
        return "book_summary_reframe"
    if "narration" in title_lower or source_markers >= 8:
        return "source_narration"
    if question_markers >= 6 and re.search(r"\b(question|interview|answered|answer)\b", title_lower + " " + text_lower):
        return "qa_coaching"
    if number_markers >= 6 or re.search(r"\b(top|rules|lessons|principles|questions|things|ways)\b", title_lower):
        return "numbered_breakdown"
    if problem_markers >= 5:
        return "problem_solution"
    return "argumentative_essay"


def _classify_promise(title: str, opening: str) -> str:
    combined = f"{title.lower()} {opening.lower()}"
    if re.search(r"\b(never|don't|dont|stop|mistake|problem|avoid|wrong)\b", combined):
        return "avoid_pain_or_loss"
    if re.search(r"\b(how to|answered|learn|master|ultralearning|interview)\b", combined):
        return "skill_upgrade"
    if re.search(r"\b(was|problem with|wrong about|vs\.?|question)\b", title.lower()):
        return "belief_challenge"
    if re.search(r"\b(summary|meditations|art of war|discourses|tao|stoic|philosophy)\b", combined):
        return "classic_source_translation"
    return "specific_framework"


def _classify_cta(closing: str) -> str:
    closing_lower = closing.lower()
    if re.search(r"\b(link in the description|description box|download|grab it|playlist below|nebula|patreon|free resource)\b", closing_lower):
        return "description_resource"
    if re.search(r"\b(subscribe|see you in the next|next one|watch the next|check out)\b", closing_lower):
        return "subscribe_next_step"
    if re.search(r"\b(let me know|comment|tell me in the comments|drop a comment)\b", closing_lower):
        return "comment_prompt"
    if re.search(r"\b(remember|practice|start|do this|take action|get back on track)\b", closing_lower):
        return "action_command"
    return "reflective_close"


def _classify_evidence(text: str) -> str:
    text_lower = text.lower()
    scores = {
        "historical_or_textual": _count_matches(text_lower, r"\b(chapter|book|history|ancient|marcus|epictetus|sun tzu|stoic|philosophy)\b"),
        "personal_experience": _count_matches(text_lower, r"\b(i|my|me)\b"),
        "teaching_examples": _count_matches(text_lower, r"\b(for example|for instance|imagine|suppose|let's say|lets say)\b"),
        "research_or_data": _count_matches(text_lower, r"\b(study|research|data|report|statistics|scientists|evidence)\b"),
        "direct_coaching": _count_matches(text_lower, r"\b(you|your|you want|you need|what you want to do)\b"),
    }
    return max(scores.items(), key=lambda item: item[1])[0]


def _hook_step(hook_key: str) -> str:
    if hook_key == "warning_boundary":
        return "Lead with a boundary, mistake, or consequence before any context."
    if hook_key == "authority_source":
        return "Open by naming the authority source and the modern payoff of listening now."
    if hook_key == "question_challenge":
        return "Start with a provocative question that makes the viewer test their current belief."
    if hook_key == "numbered_framework":
        return "Open with the exact count or framework the viewer is about to receive."
    if hook_key == "story_or_personal":
        return "Open with one short personal or observed scene, then pivot quickly to the lesson."
    return "Open with the pain, tension, or desired outcome in the viewer's current life."


def _cta_step(cta_key: str) -> str:
    if cta_key == "description_resource":
        return "Close by pushing the viewer toward a guide, worksheet, playlist, or description link."
    if cta_key == "subscribe_next_step":
        return "Close with one clean next-step CTA instead of stacking multiple asks."
    if cta_key == "comment_prompt":
        return "Finish with one specific question that invites the viewer to reveal their situation."
    if cta_key == "action_command":
        return "End with one concrete action the viewer can take immediately after the video."
    return "Land on one reflective line and then add a low-friction next step."


def _evidence_step(evidence_key: str) -> str:
    if evidence_key == "historical_or_textual":
        return "Support each section with one source-based example and one modern interpretation."
    if evidence_key == "personal_experience":
        return "Use one lived observation to make the lesson feel embodied instead of abstract."
    if evidence_key == "research_or_data":
        return "Add one piece of evidence or quantified proof before you generalize the lesson."
    if evidence_key == "teaching_examples":
        return "Translate each abstract idea into one easy-to-picture example."
    return "Keep the lesson in direct coaching language so the viewer always knows what to do next."


def _pattern_evidence(patterns: list[dict[str, Any]], key: str, fallback: str) -> str:
    for pattern in patterns:
        if pattern["key"] == key:
            return f"Observed {pattern['label'].lower()} in {pattern['share']:.0%} of the sample."
    return f"Supported by the transcript sample through recurring {fallback}."


def _most_common_key(items: list[dict[str, Any]], key: str) -> str:
    return Counter(item[key] for item in items).most_common(1)[0][0]


def _confidence_label(share: float) -> str:
    if share >= 0.6:
        return "high"
    if share >= 0.35:
        return "medium"
    return "low"


def _normalize_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _opening_excerpt(text: str, max_sentences: int = 3, max_chars: int = 280) -> str:
    sentences = _split_sentences(text)
    excerpt = " ".join(sentences[:max_sentences]) if sentences else text[:max_chars]
    return excerpt[:max_chars].strip()


def _closing_excerpt(text: str, max_sentences: int = 3, max_chars: int = 280) -> str:
    sentences = _split_sentences(text)
    excerpt = " ".join(sentences[-max_sentences:]) if sentences else text[-max_chars:]
    return excerpt[-max_chars:].strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z']+", text))


def _count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _published_sort_key(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.min