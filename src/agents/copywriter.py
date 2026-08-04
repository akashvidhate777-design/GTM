"""OpenAI-powered copywriter for Alepo Digital BSS outbound pitches."""

from __future__ import annotations

import logging

from openai import OpenAI

from src.config.settings import require_openai_api_key

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior telecom sales copywriter for Alepo.
Alepo sells Digital BSS (Business Support Systems) to telecom operators and
CSPs in Africa. The primary value hook is Omnichannel Customer Engagement:
AI-powered self-care portals, personalization engines, and automated campaigns.

Write clean, direct plain text only. No markdown headers, no bullet lists,
no subject line prefixes, no sign-off blocks unless naturally part of the
closing CTA. Exactly three short paragraphs after the greeting line."""


def _build_user_prompt(
    first_name: str,
    company: str,
    country: str,
    services: str,
) -> str:
    return f"""Write a personalized cold outreach email for this telecom contact.

Contact:
- First Name: {first_name}
- Company: {company}
- Country: {country}
- Services / offerings: {services or "telecom / digital services"}

Required structure (exactly this shape, plain text):

Hi {first_name},

<Paragraph 1 — deep local research angle: {company}'s market penetration /
positioning around {services or "their core services"} in {country}. Be specific
and credible; avoid generic filler.>

<Paragraph 2 — concrete fit: transition to Alepo Digital BSS with strict focus
on Omnichannel Customer Engagement (unified AI-driven self-care portals and
automated contextual marketing campaigns to maximize ARPU).>

<Paragraph 3 — carrier-grade business hook + strong CTA asking for a live /
discovery platform demo.>

Output only the email body text."""


def generate_personalized_pitch(
    first_name: str,
    company: str,
    country: str,
    services: str,
    client: OpenAI | None = None,
) -> str:
    """Generate a three-section personalized Alepo pitch via gpt-4o."""
    api_key = require_openai_api_key()
    if client is None:
        client = OpenAI(api_key=api_key)

    logger.info(
        "Generating pitch for %s @ %s (%s)",
        first_name,
        company,
        country,
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.7,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(first_name, company, country, services),
            },
        ],
    )

    body = (response.choices[0].message.content or "").strip()
    if not body:
        raise RuntimeError("OpenAI returned an empty pitch body")

    # Soft guard: ensure greeting is present
    greeting = f"Hi {first_name},"
    if not body.startswith(greeting):
        body = f"{greeting}\n\n{body}"

    logger.info("Pitch generated (%d chars) for %s", len(body), first_name)
    return body
