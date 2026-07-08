#!/usr/bin/env python3
"""SEO / AEO / GEO analysis agent: fetches a target page plus competitor
pages, extracts on-page ranking signals with rule-based checks, scores them
across three lenses, and produces a gap report with prioritized improvement
recommendations.

Lenses:
  SEO  - classic search engine optimization (titles, meta, schema, speed).
  AEO  - answer engine optimization (featured snippets, voice, FAQ schema).
  GEO  - generative engine optimization (AI Overviews, ChatGPT, Perplexity,
         Claude answers): AI-crawler access, entity/E-E-A-T signals,
         citation-worthy content.

Setup:
  1. pip install -r requirements.txt
  2. export ANTHROPIC_API_KEY=...   (optional: enables the narrative report
     and prioritized recommendations; the scored comparison table works
     without it)
  3. python seo_aeo_geo_agent.py --url https://example.com \
       --competitors https://competitor-a.com https://competitor-b.com
"""
import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seo_aeo_geo_agent")

USER_AGENT = "Mozilla/5.0 (compatible; GTM-SEO-AEO-GEO-Agent/1.0; +https://github.com/)"
TIMEOUT = 15

AI_CRAWLERS = [
    "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "ClaudeBot", "Claude-User", "anthropic-ai",
    "PerplexityBot", "Google-Extended", "CCBot", "Bytespider", "Applebot-Extended",
]

ENTITY_SCHEMA_TYPES = {"Organization", "Product", "Review", "AggregateRating", "Article", "BreadcrumbList", "LocalBusiness"}

QUESTION_RE = re.compile(r"^\s*(who|what|why|how|when|where|which|can|does|do|is|are|should)\b", re.IGNORECASE)
STAT_RE = re.compile(r"\d+(\.\d+)?\s?(%|x\b|percent)|\$\s?\d+")
DEFINITIONAL_RE = re.compile(r"\b(is a|is an|are a|are an|refers to|is the process of|is defined as)\b", re.IGNORECASE)
COMPARISON_RE = re.compile(r"\b(vs\.?|versus|compared to|comparison)\b", re.IGNORECASE)


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def fetch(url: str):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
    return resp


def fetch_optional_text(url: str):
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.text
    except requests.RequestException:
        pass
    return None


# --------------------------------------------------------------------------
# Signal extraction
# --------------------------------------------------------------------------

def robots_ai_access(robots_txt: str) -> dict:
    """For each known AI crawler, determine allowed/disallowed/unlisted."""
    if not robots_txt:
        return {bot: "unlisted (default allow, robots.txt missing)" for bot in AI_CRAWLERS}

    blocks = {}
    current_agents = []
    for line in robots_txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            current_agents = [value]
            for agent in current_agents:
                blocks.setdefault(agent, [])
        elif key == "disallow" and current_agents:
            for agent in current_agents:
                blocks.setdefault(agent, []).append(value)

    result = {}
    for bot in AI_CRAWLERS:
        rules = blocks.get(bot)
        if rules is None:
            result[bot] = "unlisted (default allow)"
        elif "/" in rules:
            result[bot] = "disallowed"
        elif rules:
            result[bot] = f"partially disallowed ({len(rules)} rule(s))"
        else:
            result[bot] = "allowed"
    return result


def extract_json_ld_types(soup: BeautifulSoup) -> list:
    types = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict):
                t = item.get("@type")
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)
                for graph_item in item.get("@graph", []) if isinstance(item.get("@graph"), list) else []:
                    if isinstance(graph_item, dict) and graph_item.get("@type"):
                        types.append(graph_item["@type"])
    return types


def analyze_site(url: str) -> dict:
    """Fetch a URL and its robots.txt/sitemap.xml/llms.txt, then extract
    every SEO/AEO/GEO signal used by the scoring rubric below."""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    resp = fetch(url)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    robots_txt = fetch_optional_text(urljoin(origin, "/robots.txt"))
    sitemap_present = fetch_optional_text(urljoin(origin, "/sitemap.xml")) is not None
    llms_txt_present = fetch_optional_text(urljoin(origin, "/llms.txt")) is not None

    title_tag = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    canonical_tag = soup.find("link", rel="canonical")
    viewport_tag = soup.find("meta", attrs={"name": "viewport"})

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]
    h3_tags = [h.get_text(strip=True) for h in soup.find_all("h3")]
    all_question_headings = [h for h in (h1_tags + h2_tags + h3_tags) if QUESTION_RE.match(h)]

    body_text = soup.get_text(separator=" ", strip=True)
    word_count = len(body_text.split())

    images = soup.find_all("img")
    images_missing_alt = [img for img in images if not img.get("alt", "").strip()]

    internal_links, external_links = 0, 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        joined = urljoin(url, href)
        if urlparse(joined).netloc == parsed.netloc:
            internal_links += 1
        else:
            external_links += 1

    og_tags = {m.get("property"): m.get("content") for m in soup.find_all("meta", property=re.compile(r"^og:"))}
    twitter_tags = {m.get("name"): m.get("content") for m in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")})}

    json_ld_types = extract_json_ld_types(soup)
    faq_schema_present = "FAQPage" in json_ld_types
    howto_schema_present = "HowTo" in json_ld_types
    entity_schema_types = sorted(set(json_ld_types) & ENTITY_SCHEMA_TYPES)

    author_present = bool(
        soup.find(attrs={"rel": "author"})
        or soup.find(attrs={"class": re.compile(r"author", re.IGNORECASE)})
        or soup.find("meta", attrs={"name": "author"})
        or "author" in json.dumps(json_ld_types).lower()
        or any("Person" in t for t in json_ld_types)
    )
    date_present = bool(
        soup.find("meta", attrs={"property": re.compile(r"article:(published|modified)_time")})
        or soup.find("time")
    )

    # Direct-answer paragraph: a <p> of ~20-60 words immediately following a
    # question-formatted heading (the shape featured snippets/AI answers pull).
    direct_answer_found = False
    for heading in soup.find_all(["h1", "h2", "h3"]):
        if not QUESTION_RE.match(heading.get_text(strip=True)):
            continue
        sib = heading.find_next_sibling()
        if sib and sib.name == "p":
            words = len(sib.get_text(strip=True).split())
            if 20 <= words <= 60:
                direct_answer_found = True
                break

    stats_matches = len(STAT_RE.findall(body_text))
    stats_density_per_500w = (stats_matches / word_count * 500) if word_count else 0
    definitional_near_top = bool(DEFINITIONAL_RE.search(body_text[:1500]))
    comparison_content_present = bool(COMPARISON_RE.search(body_text)) or any(
        COMPARISON_RE.search(h) for h in (h1_tags + h2_tags)
    )

    return {
        "url": url,
        "status_code": resp.status_code,
        "response_time_ms": round(resp.elapsed.total_seconds() * 1000),
        "https": parsed.scheme == "https",
        "title": title_tag,
        "title_len": len(title_tag),
        "meta_description": meta_description,
        "meta_description_len": len(meta_description),
        "canonical_present": canonical_tag is not None,
        "viewport_present": viewport_tag is not None,
        "h1_count": len(h1_tags),
        "h2_count": len(h2_tags),
        "word_count": word_count,
        "image_count": len(images),
        "images_missing_alt": len(images_missing_alt),
        "internal_links": internal_links,
        "external_links": external_links,
        "og_tags_present": len(og_tags) >= 3,
        "twitter_tags_present": len(twitter_tags) >= 2,
        "json_ld_types": sorted(set(json_ld_types)),
        "sitemap_present": sitemap_present,
        "robots_txt_present": robots_txt is not None,
        "llms_txt_present": llms_txt_present,
        "ai_crawler_access": robots_ai_access(robots_txt),
        "faq_schema_present": faq_schema_present,
        "howto_schema_present": howto_schema_present,
        "question_headings_count": len(all_question_headings),
        "direct_answer_found": direct_answer_found,
        "list_count": len(soup.find_all(["ul", "ol"])),
        "table_count": len(soup.find_all("table")),
        "entity_schema_types": entity_schema_types,
        "author_signal_present": author_present,
        "date_signal_present": date_present,
        "stats_density_per_500w": round(stats_density_per_500w, 2),
        "definitional_sentence_near_top": definitional_near_top,
        "comparison_content_present": comparison_content_present,
    }


# --------------------------------------------------------------------------
# Scoring rubrics
# --------------------------------------------------------------------------
# Each rubric is a list of (parameter, weight, check(signals) -> bool, note-fn).

def seo_rubric():
    return [
        ("Title tag present (10-60 chars)", 10, lambda s: bool(s["title"]) and 10 <= s["title_len"] <= 60),
        ("Meta description present (50-160 chars)", 10, lambda s: 50 <= s["meta_description_len"] <= 160),
        ("Exactly one H1", 10, lambda s: s["h1_count"] == 1),
        ("H2 subheadings present", 5, lambda s: s["h2_count"] >= 2),
        ("Canonical tag present", 10, lambda s: s["canonical_present"]),
        ("Served over HTTPS", 10, lambda s: s["https"]),
        ("Mobile viewport meta present", 10, lambda s: s["viewport_present"]),
        ("Image alt-text coverage >= 80%", 10, lambda s: s["images_missing_alt"] == 0 if s["image_count"] == 0 else (s["image_count"] - s["images_missing_alt"]) / s["image_count"] >= 0.8),
        ("Open Graph tags present", 10, lambda s: s["og_tags_present"]),
        ("Structured data (any JSON-LD) present", 10, lambda s: len(s["json_ld_types"]) > 0),
        ("sitemap.xml reachable", 5, lambda s: s["sitemap_present"]),
        ("Content length >= 300 words", 10, lambda s: s["word_count"] >= 300),
    ]


def aeo_rubric():
    return [
        ("FAQPage schema present", 25, lambda s: s["faq_schema_present"]),
        ("HowTo schema present", 10, lambda s: s["howto_schema_present"]),
        ("Question-formatted headings present", 20, lambda s: s["question_headings_count"] >= 1),
        ("Concise direct-answer paragraph under a question heading", 20, lambda s: s["direct_answer_found"]),
        ("Lists (ul/ol) present", 15, lambda s: s["list_count"] >= 1),
        ("Comparison/spec tables present", 10, lambda s: s["table_count"] >= 1),
    ]


def geo_rubric():
    return [
        ("llms.txt present", 15, lambda s: s["llms_txt_present"]),
        ("AI crawlers (GPTBot/ClaudeBot/PerplexityBot/Google-Extended) not blocked", 20,
         lambda s: all(v in ("allowed", "unlisted (default allow)") or "unlisted" in v for v in s["ai_crawler_access"].values())),
        ("Entity structured data present (Organization/Product/Review/...)", 15, lambda s: len(s["entity_schema_types"]) > 0),
        ("Author / expertise (E-E-A-T) signal present", 15, lambda s: s["author_signal_present"]),
        ("Freshness signal present (published/modified date)", 10, lambda s: s["date_signal_present"]),
        ("Statistics/data density >= 1 per 500 words", 10, lambda s: s["stats_density_per_500w"] >= 1),
        ("Quotable definitional sentence near top of content", 10, lambda s: s["definitional_sentence_near_top"]),
        ("Comparison content present (vs./versus/comparison)", 5, lambda s: s["comparison_content_present"]),
    ]


def score(signals: dict, rubric: list) -> tuple:
    total_weight = sum(w for _, w, _ in rubric)
    achieved = 0
    breakdown = []
    for name, weight, check in rubric:
        try:
            passed = bool(check(signals))
        except (KeyError, ZeroDivisionError, TypeError):
            passed = False
        achieved += weight if passed else 0
        breakdown.append({"parameter": name, "weight": weight, "passed": passed})
    pct = round(achieved / total_weight * 100) if total_weight else 0
    return pct, breakdown


def score_all(signals: dict) -> dict:
    seo_pct, seo_breakdown = score(signals, seo_rubric())
    aeo_pct, aeo_breakdown = score(signals, aeo_rubric())
    geo_pct, geo_breakdown = score(signals, geo_rubric())
    return {
        "seo": {"score": seo_pct, "breakdown": seo_breakdown},
        "aeo": {"score": aeo_pct, "breakdown": aeo_breakdown},
        "geo": {"score": geo_pct, "breakdown": geo_breakdown},
    }


# --------------------------------------------------------------------------
# Gap analysis
# --------------------------------------------------------------------------

def build_gaps(target_scored: dict, competitor_scored: list) -> list:
    """For every failed target parameter, flag it as a gap if any competitor passes it."""
    gaps = []
    for category in ("seo", "aeo", "geo"):
        target_breakdown = {b["parameter"]: b for b in target_scored[category]["breakdown"]}
        for param, tb in target_breakdown.items():
            if tb["passed"]:
                continue
            winners = [c["label"] for c in competitor_scored if any(
                b["parameter"] == param and b["passed"] for b in c["scored"][category]["breakdown"]
            )]
            if winners:
                priority = "High" if tb["weight"] >= 15 else ("Medium" if tb["weight"] >= 10 else "Low")
                gaps.append({
                    "category": category.upper(),
                    "parameter": param,
                    "weight": tb["weight"],
                    "priority": priority,
                    "competitors_ahead": winners,
                })
    gaps.sort(key=lambda g: (-g["weight"], g["category"]))
    return gaps


# --------------------------------------------------------------------------
# Claude synthesis (optional)
# --------------------------------------------------------------------------

GAP_REPORT_TOOL = {
    "name": "submit_gap_report",
    "description": "Submit the prioritized SEO/AEO/GEO improvement plan derived from the scored comparison data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "narrative_summary": {
                "type": "string",
                "description": "3-5 sentence executive summary of where the target site stands vs competitors across SEO, AEO, and GEO.",
            },
            "quick_wins": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Low-effort, high-impact fixes the target site should ship first.",
            },
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "parameter": {"type": "string"},
                        "category": {"type": "string", "enum": ["SEO", "AEO", "GEO"]},
                        "recommendation": {"type": "string", "description": "Specific, actionable fix."},
                        "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "effort": {"type": "string", "enum": ["Low", "Medium", "High"]},
                    },
                    "required": ["parameter", "category", "recommendation", "priority", "effort"],
                },
            },
        },
        "required": ["narrative_summary", "quick_wins", "recommendations"],
    },
}


def synthesize_recommendations(client, target_label: str, target_scored: dict, competitor_scored: list, gaps: list) -> dict:
    payload = {
        "target": {"label": target_label, "scores": {k: v["score"] for k, v in target_scored.items()}},
        "competitors": [{"label": c["label"], "scores": {k: v["score"] for k, v in c["scored"].items()}} for c in competitor_scored],
        "gaps": gaps,
    }
    prompt = f"""You are a GTM growth analyst. Below is structured SEO/AEO/GEO scoring data
extracted from a target site and its competitors (SEO = classic search, AEO = answer engine
optimization / featured snippets & voice, GEO = generative engine optimization for AI answers
like ChatGPT/Perplexity/AI Overviews).

{json.dumps(payload, indent=2)}

Call submit_gap_report with a prioritized improvement plan. Order recommendations by priority
(High first). Ground every recommendation in the gap data above; do not invent metrics that
aren't present."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        tools=[GAP_REPORT_TOOL],
        tool_choice={"type": "tool", "name": "submit_gap_report"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_gap_report":
            return block.input
    raise RuntimeError("Model did not return a tool call for the gap report")


# --------------------------------------------------------------------------
# Report rendering
# --------------------------------------------------------------------------

def render_markdown(target_label, target_scored, competitor_scored, gaps, ai_report):
    lines = []
    lines.append(f"# SEO / AEO / GEO Gap Report — {target_label}")
    lines.append("")
    lines.append(f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    lines.append("## Score summary")
    lines.append("")
    header = ["Site", "SEO", "AEO", "GEO"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    lines.append(f"| **{target_label} (target)** | {target_scored['seo']['score']} | {target_scored['aeo']['score']} | {target_scored['geo']['score']} |")
    for c in competitor_scored:
        s = c["scored"]
        lines.append(f"| {c['label']} | {s['seo']['score']} | {s['aeo']['score']} | {s['geo']['score']} |")
    lines.append("")

    if ai_report:
        lines.append("## Executive summary")
        lines.append("")
        lines.append(ai_report["narrative_summary"])
        lines.append("")
        lines.append("## Quick wins")
        lines.append("")
        for qw in ai_report["quick_wins"]:
            lines.append(f"- {qw}")
        lines.append("")

    lines.append("## Improvement parameters vs. competitors")
    lines.append("")
    lines.append("| Priority | Category | Parameter | Target | Competitors ahead |")
    lines.append("|---|---|---|---|---|")
    for g in gaps:
        lines.append(f"| {g['priority']} | {g['category']} | {g['parameter']} | ❌ Missing | {', '.join(g['competitors_ahead'])} |")
    if not gaps:
        lines.append("| — | — | No gaps found: target matches or beats all competitors on every tracked parameter. | | |")
    lines.append("")

    if ai_report:
        lines.append("## Prioritized recommendations")
        lines.append("")
        lines.append("| Priority | Effort | Category | Parameter | Recommendation |")
        lines.append("|---|---|---|---|---|")
        for r in ai_report["recommendations"]:
            lines.append(f"| {r['priority']} | {r['effort']} | {r['category']} | {r['parameter']} | {r['recommendation']} |")
        lines.append("")

    lines.append("## Full signal breakdown")
    lines.append("")
    for category, title in (("seo", "SEO"), ("aeo", "AEO"), ("geo", "GEO")):
        lines.append(f"### {title} ({target_scored[category]['score']}/100)")
        lines.append("")
        lines.append("| Parameter | Weight | Target | " + " | ".join(c["label"] for c in competitor_scored) + " |")
        lines.append("|---|---|---|" + "---|" * len(competitor_scored))
        target_breakdown = {b["parameter"]: b for b in target_scored[category]["breakdown"]}
        for param, tb in target_breakdown.items():
            row = [param, str(tb["weight"]), "✅" if tb["passed"] else "❌"]
            for c in competitor_scored:
                cb = {b["parameter"]: b for b in c["scored"][category]["breakdown"]}
                row.append("✅" if cb[param]["passed"] else "❌")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def label_for(url: str) -> str:
    return urlparse(url).netloc


def main():
    parser = argparse.ArgumentParser(description="SEO/AEO/GEO analysis agent with competitor gap report")
    parser.add_argument("--url", required=True, help="Target website or product page URL")
    parser.add_argument("--competitors", nargs="*", default=[], help="One or more competitor URLs to compare against")
    parser.add_argument("--output", default=None, help="Output markdown file path (default: reports/<domain>-gap-report.md)")
    parser.add_argument("--no-llm", action="store_true", help="Skip Claude synthesis; emit the scored comparison only")
    args = parser.parse_args()

    log.info("Fetching target: %s", args.url)
    try:
        target_signals = analyze_site(args.url)
    except requests.RequestException as e:
        log.error("Failed to fetch target %s: %s", args.url, e)
        sys.exit(1)
    target_scored = score_all(target_signals)
    target_label = label_for(args.url)

    competitor_scored = []
    for comp_url in args.competitors:
        log.info("Fetching competitor: %s", comp_url)
        try:
            comp_signals = analyze_site(comp_url)
        except requests.RequestException as e:
            log.warning("Skipping competitor %s: %s", comp_url, e)
            continue
        competitor_scored.append({
            "label": label_for(comp_url),
            "signals": comp_signals,
            "scored": score_all(comp_signals),
        })

    if not competitor_scored:
        log.warning("No competitors were reachable; gap report will only show the target's own scores.")

    gaps = build_gaps(target_scored, competitor_scored)

    ai_report = None
    if not args.no_llm:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log.warning("ANTHROPIC_API_KEY not set; skipping narrative synthesis (scored tables still generated).")
        else:
            import anthropic
            claude = anthropic.Anthropic()
            log.info("Synthesizing prioritized recommendations with Claude...")
            ai_report = synthesize_recommendations(claude, target_label, target_scored, competitor_scored, gaps)

    report = render_markdown(target_label, target_scored, competitor_scored, gaps, ai_report)

    output_path = args.output or os.path.join("reports", f"{target_label.replace('.', '_')}-gap-report.md")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    log.info("Report written to %s", output_path)
    print(f"\nSEO {target_scored['seo']['score']}/100  |  AEO {target_scored['aeo']['score']}/100  |  GEO {target_scored['geo']['score']}/100")
    print(f"Gaps found: {len(gaps)}  |  Report: {output_path}")


if __name__ == "__main__":
    main()
