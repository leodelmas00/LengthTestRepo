"""Prompt modules and system-prompt assembly.

Every experiment builds its system prompt as:

    BASE
    {LENGTH MODULE}      (optional)
    {FORMALITY MODULE}   (optional)
    {ANTI-INTERFERENCE GUARDRAIL}   (always)
    {EXAMPLE MODULE}     (optional)

The user prompt is fixed for every request (see USER_PROMPT).
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_BANK_PATH = os.path.join(os.path.dirname(_HERE), "few_shot_bank.json")

with open(_BANK_PATH, encoding="utf-8") as _f:
    BANK = json.load(_f)


USER_PROMPT = "Hi, can you book me a flight from Buenos Aires to Mexico?"

BASE = (
    "You are a conversational assistant answering user queries about travel "
    "planning. Respond in English."
)


# --- Length modules -------------------------------------------------------

LENGTH_SHORT = (
    "Respond in between 30 and 60 words total; aim for approximately 45 words. "
    "Do not add information beyond what is strictly requested, even if other "
    "modules suggest further development."
)

LENGTH_LONG = (
    "Respond in between 140 and 200 words total; aim for approximately 170 words. "
    "Develop the topic in depth with examples where applicable."
)

# Over-asking variants (ask above the desired target to compensate underproduction)
LENGTH_SHORT_OVER = (
    "Respond in between 60 and 90 words total; aim for approximately 75 words. "
    "Do not add information beyond what is strictly requested, even if other "
    "modules suggest further development."
)

LENGTH_LONG_OVER = (
    "Respond in between 200 and 260 words total; aim for approximately 230 words. "
    "Develop the topic in depth with examples where applicable."
)

# Alternative unit A: sentences
LENGTH_SHORT_SENT = (
    "Respond in exactly 3 sentences, each of about 15 words. Write them as "
    "continuous prose, with no lists. Do not add information beyond what is "
    "strictly requested. Count your sentences before responding."
)

LENGTH_LONG_SENT = (
    "Respond in exactly 9 to 10 sentences, each of about 18 words. Write them as "
    "continuous prose, with no lists. Develop the topic in depth with examples "
    "where applicable. Count your sentences before responding."
)

# Alternative unit B: paragraphs
LENGTH_SHORT_PAR = (
    "Respond in exactly 2 paragraphs of 2 sentences each. Each sentence should be "
    "about 11 words long. Do not add information beyond what is strictly "
    "requested. Count your paragraphs and sentences before responding."
)

LENGTH_LONG_PAR = (
    "Respond in exactly 3 paragraphs of 3 sentences each. Each sentence should be "
    "about 18 words long. Develop the topic in depth with examples where "
    "applicable. Count your paragraphs and sentences before responding."
)


# --- Formality modules ----------------------------------------------------

FORMALITY_FORMAL = (
    'write out every word in full (use "do not" and "it is" in their complete '
    "forms). Use precise terminology, careful syntax, and impersonal or "
    "third-person constructions throughout. Maintain an elevated, professional "
    "tone in every sentence. long level only: A formal answer here is economical, "
    "not padded: make your point in no more than 9 sentences and stop."
)

FORMALITY_INFORMAL = (
    "contractions ('don't', 'it's'), everyday vocabulary, second-person address "
    "('you'). Avoid unnecessary technical terms when a common equivalent exists. "
    "Allowed: moderate interjections ('sure', 'look'). You are texting a friend "
    "back. Not advising them, not helping them - just replying. Speak from your "
    "own experience: say what you did or what you'd do, never what \"one can\" or "
    "\"you should\" do."
)

# Decoupled from brevity (no "just replying" / "texting a friend" cues)
FORMALITY_INFORMAL_DECOUPLED = (
    'Use an informal register: contractions ("don\'t", "it\'s"), everyday '
    'vocabulary, and second-person address ("you"). Avoid technical terms when a '
    'common equivalent exists. Moderate interjections ("sure", "look") are '
    "allowed. Speak from your own experience: say what you did or what you'd do, "
    'never what "one can" or "you should" do. Informal does not mean short. Share '
    "details, small stories and specific tips, and develop each point fully, the "
    "way you would in a long, friendly voice message. Sentence structure is free: "
    "write complete, flowing sentences."
)


# --- Anti-interference guardrail (always included) ------------------------

GUARDRAIL = (
    "The 2 dimensions (length, formality) are INDEPENDENT. Satisfy BOTH "
    "SIMULTANEOUSLY without one relaxing the other. Specifically:\n"
    "- A short response can be fully informal without exceeding the word limit.\n"
    "- A formal response can be short.\n"
    "- A long response reaches the SAME word count in either register.\n"
    "Casual phrasing is not a reason to finish early, and formal phrasing is not "
    "a reason to run past the limit. Hit the stated target either way.\n"
    "- Register never justifies going over or under the word count, and the word "
    "count never justifies dropping the register.\n"
    "Before responding, verify internally that both conditions are met."
)


# --- Example module (one-shot / few-shot) ---------------------------------

EXAMPLE_HEADER = (
    "Here is an example of the expected length and register. It covers a "
    "different topic: match its length and style, not its content."
)

ONE_SHOT_IDS = tuple(BANK["meta"]["fixed_sets"]["1shot"])
FEW_SHOT_IDS = tuple(BANK["meta"]["fixed_sets"]["3shot_fixed"])


def build_example_module(length, register, ids):
    """Render the EXAMPLE MODULE for a cell (length x register) from the bank."""
    cell = BANK["bank"][length][register]
    by_id = {entry["id"]: entry for entry in cell}
    lines = [EXAMPLE_HEADER]
    for index, example_id in enumerate(ids, start=1):
        example = by_id[example_id]
        lines.append("")
        lines.append("[Example %d]" % index)
        lines.append("User: %s" % example["user"])
        lines.append("Assistant: %s" % example["assistant"])
    return "\n".join(lines)


def build_system_prompt(length_module=None, formality_module=None, example_module=None):
    """Assemble the full system prompt. The guardrail is always included."""
    parts = [BASE]
    if length_module:
        parts.append(length_module)
    if formality_module:
        parts.append(formality_module)
    parts.append(GUARDRAIL)
    if example_module:
        parts.append(example_module)
    return "\n\n".join(parts)
