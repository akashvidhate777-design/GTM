"""ICP lead-scoring engine.

Score = ICP title tier (40) + function relevance (15) + industry fit (25)
      + company scale (10) + revenue (5) + data completeness (5)
      + news bonus (up to +5), capped at 100.

Grades: A >= 90, B 75-89, C 55-74, D < 55. See docs/ARCHITECTURE.md section 3.
"""
import re

from .models import Lead, ScoreBreakdown

TIER1 = [
    r"\bceo\b", r"chief executive", r"\bcfo\b", r"chief financial",
    r"\bcto\b", r"chief technology", r"\bcoo\b", r"chief operating",
    r"\bcio\b", r"chief information", r"chief digital", r"\bcdo\b",
    r"chief supply chain", r"chief commercial", r"chief business",
    r"founder", r"co-?founder", r"managing director", r"\bmd\b",
    r"president", r"owner", r"chairman", r"chairperson", r"promoter",
    r"managing partner", r"\bceo\b", r"chief growth",
]
TIER2 = [r"executive vice president", r"\bevp\b", r"senior vice president",
         r"\bsvp\b", r"vice president", r"\bvp\b", r"\bavp\b",
         r"chief [a-z]+ officer"]  # off-center C-suite (e.g. CMO) ranks with VPs
TIER3 = [r"director", r"head\b", r"\bhead of", r"general manager", r"\bgm\b"]
TIER4 = [r"manager", r"\blead\b", r"in-?charge", r"controller"]

# Excludes: titles that pattern-match a tier but are outside the buying group.
NON_BUYER = [r"chief medical", r"\bcmo doctor\b", r"medical officer"]

FUNCTION_HIGH = [
    "operation", "supply chain", "logistic", "procurement", "sourcing",
    "warehouse", "distribution", "planning", "technology", "digital",
    " it ", "information", "finance", "financial", "account", "commercial",
    "merchandis", "e-commerce", "ecommerce", "retail", "category",
    "transformation", "strategy", "manufacturing", "production", "quality",
    "business",
]
FUNCTION_MID = ["sales", "marketing", "growth", "brand", "export"]
FUNCTION_LOW = ["human resource", "hr ", "talent", "legal", "admin", "safety",
                "medical", "communication"]

INDUSTRY_CORE = [
    "retail", "apparel", "fashion", "food & beverages", "beverage",
    "consumer goods", "supermarket", "restaurant", "luxury", "jewelry",
    "wholesale", "e-commerce",
]
INDUSTRY_ADJACENT = [
    "food production", "farming", "textile", "furniture", "manufacturing",
    "electronic", "packaging", "dairy", "agri",
]


def _title_tier(title_l: str) -> tuple[str, int]:
    for pat in NON_BUYER:
        if re.search(pat, title_l):
            return "Non-ICP", 5
    for pat in TIER1:
        if re.search(pat, title_l):
            return "Tier 1 - C-Suite/Founder", 40
    for pat in TIER2:
        if re.search(pat, title_l):
            return "Tier 2 - VP", 30
    for pat in TIER3:
        if re.search(pat, title_l):
            return "Tier 3 - Director/Head", 24
    for pat in TIER4:
        if re.search(pat, title_l):
            return "Tier 4 - Manager", 12
    return "Non-ICP", 5


def _function_score(title_l: str) -> tuple[str, int]:
    padded = f" {title_l} "
    for kw in FUNCTION_LOW:
        if kw in padded:
            return "Support function", 2
    for kw in FUNCTION_HIGH:
        if kw in padded:
            return "Ops/Tech/Finance/Commercial", 15
    for kw in FUNCTION_MID:
        if kw in padded:
            return "Sales/Marketing", 5
    # Pure C-level titles ("CEO", "Founder") carry no function keyword but own
    # every function.
    if re.search(r"ceo|founder|managing director|president|owner|chairman|coo|cfo|cto|cio",
                 title_l):
        return "General management", 13
    return "General", 6


def _industry_score(industry_l: str) -> int:
    if any(kw in industry_l for kw in INDUSTRY_CORE):
        return 25
    if any(kw in industry_l for kw in INDUSTRY_ADJACENT):
        return 16
    return 6


def _scale_score(employees: int | None) -> int:
    """Sweet spot: mid-market where one buyer can green-light a pilot.
    Mega-enterprises score lower — longer cycles, procurement gates."""
    if employees is None:
        return 2
    if 500 <= employees <= 20_000:
        return 10
    if 20_000 < employees <= 100_000 or 200 <= employees < 500:
        return 7
    if employees > 100_000:
        return 5
    if 50 <= employees < 200:
        return 3
    return 1


def _revenue_score(revenue: float | None) -> int:
    if revenue is None:
        return 1
    if 100_000_000 <= revenue < 2_000_000_000:
        return 5
    if revenue >= 2_000_000_000:
        return 4
    if revenue >= 10_000_000:
        return 3
    return 1


def score_lead(lead: Lead, news_signal: str = "", news_bonus: int = 0) -> ScoreBreakdown:
    title_l = lead.title.lower()
    tier_name, tier_pts = _title_tier(title_l)
    func_name, func_pts = _function_score(title_l)

    completeness = (3 if lead.has_valid_email else 0) + (2 if lead.person_linkedin else 0)

    return ScoreBreakdown(
        icp_title=tier_pts,
        function=func_pts,
        industry=_industry_score(lead.industry),
        scale=_scale_score(lead.employees),
        revenue=_revenue_score(lead.annual_revenue),
        completeness=completeness,
        news_bonus=max(0, min(5, news_bonus)),
        icp_tier=tier_name,
        persona=f"{tier_name.split(' - ')[-1]} / {func_name}",
        news_signal=news_signal,
    )
