"""Centralised LLM prompt definitions.

All system prompts and prompt templates live here so they can be reviewed,
versioned, and overridden via environment variables without touching service
code.

Override mechanism
------------------
Set ``EXTRACTION_PROMPT_OVERRIDE`` or ``GENERATION_PROMPT_OVERRIDE`` in the
environment (or ``.env``) to replace the default prompt at runtime.  An empty
string (the default) means "use the built-in prompt below".

Usage::

    from app.core.prompts import EXTRACTION_PROMPT_TEMPLATE, GENERATION_SYSTEM_PROMPT
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(transcript=transcript_text)
"""

from __future__ import annotations

from app.core.config import settings

# ---------------------------------------------------------------------------
# Extraction pipeline
# ---------------------------------------------------------------------------

_DEFAULT_EXTRACTION_PROMPT_TEMPLATE = """\
You are an AI assistant helping a financial advisor extract structured notes
from a client meeting transcript.

Analyse the transcript below and extract context items. Return ONLY a JSON
object in this exact format:
{{
  "tags": [
    {{"category": "<category>", "content": "<concise note>"}},
    ...
  ]
}}

Valid categories (use exactly as written):
- personal_interest
- financial_goal
- family_event
- risk_tolerance

Rules:
- Only include items clearly supported by the transcript.
- Each tag must have exactly the fields "category" and "content".
- Do not include any commentary, markdown, or text outside the JSON object.

Transcript:
{transcript}
"""

EXTRACTION_PROMPT_TEMPLATE: str = (
    settings.EXTRACTION_PROMPT_OVERRIDE
    if settings.EXTRACTION_PROMPT_OVERRIDE.strip()
    else _DEFAULT_EXTRACTION_PROMPT_TEMPLATE
)

# ---------------------------------------------------------------------------
# Generation pipeline
# ---------------------------------------------------------------------------

_DEFAULT_GENERATION_SYSTEM_PROMPT = """\
You are an AI assistant helping a financial advisor write personalised client emails.

Write a warm, professional email body for the advisor to send to the client
named in the profile below.

Rules:
- Maximum 4 sentences.
- Refer to portfolio size approximately, rounded to the nearest $100,000 \
(e.g., "approximately $1.2M") — never print unrounded dollar amounts.
- Use only facts present in the profile. Do not invent information.
- Address the client by first name in the opening sentence.
- Return ONLY the email body text. No subject line, no "Dear ...", \
no sign-off, no markdown formatting.\
"""

GENERATION_SYSTEM_PROMPT: str = (
    settings.GENERATION_PROMPT_OVERRIDE
    if settings.GENERATION_PROMPT_OVERRIDE.strip()
    else _DEFAULT_GENERATION_SYSTEM_PROMPT
)
