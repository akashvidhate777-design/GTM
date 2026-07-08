"""Message generation: LinkedIn connection + 2 follow-ups and a 3-step email
sequence, personalized by persona (ICP tier + function) and industry.

Two engines:
  * Template engine (default) — deterministic, offline, no API cost. Varies
    phrasing per lead via a hash-seeded pick from curated pools so no two
    messages read identically templated.
  * Claude engine (--use-claude) — calls the Anthropic Messages API with a
    forced tool call for production-quality, fully bespoke copy.

Placeholders {{SENDER_NAME}}, {{SENDER_EMAIL}}, {{CALENDLY_URL}} are resolved
from env at send time (n8n WF-2), so the workbook stays credential-free.
"""
import hashlib
import os
import textwrap

from .models import Lead, ScoreBreakdown, Sequence

OFFERING = (
    "AI solutions that plug into your existing ERP for small, high-impact "
    "use cases across retail ecosystems"
)

# Industry -> (use case phrase, pain phrase)
INDUSTRY_USE_CASES = {
    "retail": ("SKU-level demand forecasting and auto-replenishment on top of your ERP",
               "stockouts and excess inventory that the ERP reports only after the fact"),
    "apparel": ("size-curve planning and season-buy optimization that reads straight from your ERP",
                "broken size sets and end-of-season markdowns"),
    "fashion": ("size-curve planning and season-buy optimization that reads straight from your ERP",
                "broken size sets and end-of-season markdowns"),
    "food & beverages": ("expiry-aware replenishment and wastage prediction wired into your ERP",
                         "near-expiry write-offs and distributor claim reconciliation"),
    "food production": ("yield prediction and QC anomaly detection fed by your ERP batch data",
                        "batch-to-batch yield swings and manual quality paperwork"),
    "textile": ("production scheduling and order-to-dispatch tracking layered on your ERP",
                "delivery-date slippage and yarn/greige inventory pile-ups"),
    "farming": ("procurement price forecasting and supply planning connected to your ERP",
                "volatile procurement prices and manual arrival planning"),
    "furniture": ("made-to-order lead-time prediction driven by your ERP order book",
                  "quoted-vs-actual delivery gaps on custom orders"),
    "_default": ("AI add-ons for your ERP — invoice matching, PO automation, demand forecasting",
                 "manual reconciliation work your ERP wasn't built to remove"),
}

# Persona angle by (tier, function bucket)
ANGLES = {
    "finance": "recovering margin leakage and freeing working capital trapped in inventory",
    "tech": "adding AI capability without any rip-and-replace of the current ERP",
    "ops": "fewer stockouts and far less manual reconciliation",
    "exec": "measurable margin and working-capital gains within a quarter",
    "manager": "getting the repetitive ERP grunt work off your team's plate",
}


def _persona_bucket(lead: Lead) -> str:
    t = lead.title.lower()
    if any(k in t for k in ("cfo", "finance", "financial", "account")):
        return "finance"
    if any(k in t for k in ("cto", "cio", "technology", "digital", "information")):
        return "tech"
    if any(k in t for k in ("operation", "supply chain", "logistic", "procurement",
                            "warehouse", "distribution", "planning", "production")):
        return "ops"
    if any(k in t for k in ("ceo", "founder", "managing director", "president",
                            "owner", "chairman", "coo", "chief")):
        return "exec"
    return "manager"


def _use_case(lead: Lead) -> tuple[str, str]:
    ind = lead.industry.lower()
    for key, val in INDUSTRY_USE_CASES.items():
        if key != "_default" and key in ind:
            return val
    return INDUSTRY_USE_CASES["_default"]


def _pick(options: list[str], lead: Lead, salt: str) -> str:
    seed = hashlib.md5(f"{lead.email}|{lead.full_name}|{salt}".encode()).hexdigest()
    return options[int(seed, 16) % len(options)]


def generate_sequence(lead: Lead, score: ScoreBreakdown) -> Sequence:
    first = lead.first_name or "there"
    company = lead.company or "your company"
    use_case, pain = _use_case(lead)
    angle = ANGLES[_persona_bucket(lead)]
    role_ref = lead.title if lead.title else "your role"

    # --- LinkedIn ---------------------------------------------------------
    li_conn = _pick([
        f"Hi {first}, your work as {role_ref} at {company} caught my eye. We build "
        f"small AI use cases that sit on top of existing ERPs — think {angle}. "
        f"Would be glad to connect.",
        f"Hi {first}, I work with {lead.industry or 'retail'} leaders on {angle} — "
        f"lightweight AI that plugs into the ERP you already run. Given your seat at "
        f"{company}, thought it was worth connecting.",
        f"Hi {first}, we help teams like {company}'s tackle {pain} with AI add-ons "
        f"to their existing ERP — no replatforming. Keen to connect and swap notes.",
    ], lead, "li1")
    if len(li_conn) > 300:
        li_conn = li_conn[:297].rsplit(" ", 1)[0] + "..."

    li_fu1 = _pick([
        f"Thanks for connecting, {first}. Quick context: we ship {use_case}. "
        f"Teams typically start with one narrow use case and see results in weeks, "
        f"not an ERP-project timeline. Worth a short look for {company}?",
        f"Appreciate the connect, {first}. One idea for {company}: {use_case}. "
        f"It runs alongside your current ERP, so there's no migration risk — just "
        f"one contained pilot. Happy to share how similar teams structure it.",
        f"Glad to be connected, {first}. Most {lead.industry or 'retail'} teams we "
        f"meet struggle with {pain}. We fix exactly that with {use_case}. "
        f"Open to a 15-minute walkthrough?",
    ], lead, "li2")

    li_fu2 = _pick([
        f"{first}, I'll leave this here rather than keep nudging — if {pain} ever "
        f"climbs the priority list at {company}, a 15-minute call is all it takes "
        f"to see if there's a fit. Either way, good luck this quarter.",
        f"Last note from me, {first} — timing is everything with these projects. "
        f"If an AI-on-ERP pilot becomes relevant at {company} later, my line's open. "
        f"Wishing you a strong quarter.",
        f"{first}, closing the loop so I'm not another unread ping. If it's useful, "
        f"I can send a one-pager on {use_case} for {company} — zero meetings needed. "
        f"Just say the word.",
    ], lead, "li3")

    # --- Email ------------------------------------------------------------
    e1_subject = _pick([
        f"{pain.split(' and ')[0].capitalize()} at {company}?",
        f"AI on top of {company}'s ERP — one small use case",
        f"{first}, a faster fix for {pain.split(' and ')[0]}",
    ], lead, "e1s")
    e1_body = textwrap.dedent(f"""\
        Hi {first},

        As {role_ref} at {company}, you likely see {pain} more closely than anyone.

        We build {OFFERING} — starting with {use_case}. No rip-and-replace: it reads
        from and writes back to the ERP you already run, and one contained use case is
        usually live in weeks.

        For someone in your seat, the payoff is {angle}.

        Open to a 15-minute call to see if there's a fit for {company}?

        Best,
        {{{{SENDER_NAME}}}}
        {{{{SENDER_EMAIL}}}} | Book directly: {{{{CALENDLY_URL}}}}

        P.S. If this isn't relevant, reply "no thanks" and I won't follow up again.""")

    e2_subject = _pick([
        f"Re: one small AI use case for {company}",
        f"How teams like {company} start with AI on ERP",
        f"{first} — the 3-week pilot version",
    ], lead, "e2s")
    e2_body = textwrap.dedent(f"""\
        Hi {first},

        Following up on my last note. The pattern that works in {lead.industry or 'retail'}:
        pick one painful, well-bounded problem — for most teams that's {pain} — and put a
        narrow AI layer on the ERP data you already have.

        What that looks like in practice:
        - Week 1: connect read-only to the ERP, baseline the problem with your data
        - Week 2-3: pilot {use_case}
        - Then: keep it only if the numbers justify it

        No new platform, no long IT project. Would a 15-minute walkthrough this week or
        next work? {{{{CALENDLY_URL}}}}

        Best,
        {{{{SENDER_NAME}}}}""")

    e3_subject = _pick([
        f"Closing the loop, {first}",
        f"Last note — AI on ERP at {company}",
        f"Should I stay or should I go, {first}?",
    ], lead, "e3s")
    e3_body = textwrap.dedent(f"""\
        Hi {first},

        I'll close the loop here — inbox zero is sacred.

        If {pain} becomes a priority at {company} this year, we're a 15-minute
        conversation away: {{{{CALENDLY_URL}}}}. If it's easier, I can also send a
        one-page overview of {use_case} that you can forward internally — just reply
        "send it".

        Either way, thanks for reading, and good luck this quarter.

        Best,
        {{{{SENDER_NAME}}}}
        (Reply "unsubscribe" and you won't hear from me again.)""")

    return Sequence(
        linkedin_connection=li_conn,
        linkedin_followup_1=li_fu1,
        linkedin_followup_2=li_fu2,
        email_1_subject=e1_subject,
        email_1_body=e1_body,
        email_2_subject=e2_subject,
        email_2_body=e2_body,
        email_3_subject=e3_subject,
        email_3_body=e3_body,
    )


# ---------------------------------------------------------------------------
# Claude engine (opt-in, requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

GENERATE_OUTREACH_TOOL = {
    "name": "generate_outreach",
    "description": "Submit the personalized 3-step LinkedIn + email outreach sequence for a lead.",
    "input_schema": {
        "type": "object",
        "properties": {
            "linkedin_connection": {"type": "string", "description": "Connection request note, max 300 chars."},
            "linkedin_followup_1": {"type": "string"},
            "linkedin_followup_2": {"type": "string"},
            "email_1_subject": {"type": "string"},
            "email_1_body": {"type": "string"},
            "email_2_subject": {"type": "string"},
            "email_2_body": {"type": "string"},
            "email_3_subject": {"type": "string"},
            "email_3_body": {"type": "string"},
        },
        "required": [
            "linkedin_connection", "linkedin_followup_1", "linkedin_followup_2",
            "email_1_subject", "email_1_body", "email_2_subject", "email_2_body",
            "email_3_subject", "email_3_body",
        ],
    },
}

CLAUDE_MODEL = os.environ.get("OUTREACH_CLAUDE_MODEL", "claude-sonnet-5")


def generate_with_claude(lead: Lead, score: ScoreBreakdown, client=None) -> Sequence:
    import anthropic
    client = client or anthropic.Anthropic()
    use_case, pain = _use_case(lead)
    prompt = f"""You write B2B outbound for this offering: {OFFERING}.

Lead:
- Name: {lead.full_name}
- Title: {lead.title}
- Company: {lead.company} ({lead.industry or 'unknown industry'}, {lead.employees or '?'} employees, {lead.city}, {lead.country})
- Persona: {score.persona} | ICP tier: {score.icp_tier} | Lead score: {score.total}/100
- Recent news signal: {score.news_signal or 'none found'}
- Likely pain: {pain}
- Best-fit use case: {use_case}

Write a 3-step sequence: LinkedIn connection note (<=300 chars) + 2 LinkedIn
follow-ups, and 3 emails (subject + body, each body <=120 words).
Rules: mention {lead.company} by name; angle for the persona (C-suite = business
outcomes; VP/Director = team efficiency; managers = easier day-to-day); never
invent statistics, customers, or news; include exactly these placeholders in
email bodies where natural: {{{{SENDER_NAME}}}}, {{{{CALENDLY_URL}}}}; email 3 must
include an opt-out line; soft CTAs only (15-min call). Vary structure so nothing
reads templated. Call generate_outreach with the result."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        tools=[GENERATE_OUTREACH_TOOL],
        tool_choice={"type": "tool", "name": "generate_outreach"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "generate_outreach":
            return Sequence(**block.input)
    raise RuntimeError(f"No tool call returned for {lead.full_name}")
