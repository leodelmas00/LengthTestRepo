"""Metropolis-Hastings iterative sampling with importance sampling acceleration.

The sampler corrects the length of an already generated response without
touching the model or the cell's prompt modules. Acceptance is deterministic
(temperature 0): the score ratio is computed in code, not by the model.
"""

import json
import re

from config import prompts as P
from src.metrics import evaluate

MAX_ROUNDS = 5
NEAR_THRESHOLD = 3
MARGIN = 5
JUDGE_MAX_TOKENS = 512


def _distance(word_count, lo, hi):
    """Distance from ``word_count`` to the nearest window edge (0 if inside)."""
    if word_count < lo:
        return lo - word_count
    if word_count > hi:
        return word_count - hi
    return 0


def _parse_scores(text):
    """Extract (score_1, score_2) from the judge output, or None on failure."""
    if not text:
        return None
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return float(data["score_1"]), float(data["score_2"])
    except (ValueError, KeyError, TypeError):
        return None


def acceptance_ratio(dist_prev, dist_cand, score_cand, score_prev):
    """Metropolis-Hastings ratio; falls back to the distance term if no judge."""
    if dist_cand <= 0:
        return float("inf")
    distance_factor = dist_prev / dist_cand
    if score_prev and score_cand is not None:
        return distance_factor * (score_cand / score_prev)
    return distance_factor


def _judge(client, experiment, candidate, previous, temperature):
    try:
        result = client.chat(
            P.judge_messages(
                experiment.length,
                experiment.formality,
                P.USER_PROMPT,
                candidate,
                previous,
            ),
            temperature=temperature,
            max_tokens=JUDGE_MAX_TOKENS,
        )
        return _parse_scores(result["text"])
    except Exception:  # noqa: BLE001 - judge failure must not break the request
        return None


def run_mh(client, experiment, system_prompt, temperature=0.0):
    """Run the iterative MH sampler; returns the final response and its metrics."""
    lo, hi, target = experiment.lo, experiment.hi, experiment.target
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": P.USER_PROMPT},
    ]

    result = client.chat(base_messages, temperature=temperature)
    prev_text = result["text"]
    finish_reason = result["finish_reason"]
    prev_eval = evaluate(prev_text, lo, hi, target)

    initial_word_count = prev_eval["word_count"]
    initial_in_window = prev_eval["in_window"]

    rounds = 0
    rejected = 0
    judge_calls = 0
    round_flags = [initial_in_window]

    while not prev_eval["in_window"] and rounds < MAX_ROUNDS:
        feedback = P.revision_feedback(
            prev_eval["word_count"], lo, hi, target, NEAR_THRESHOLD, MARGIN
        )
        messages = base_messages + [
            {"role": "assistant", "content": prev_text},
            {"role": "user", "content": feedback},
        ]
        cand_result = client.chat(messages, temperature=temperature)
        cand_text = cand_result["text"]
        finish_reason = cand_result["finish_reason"]
        cand_eval = evaluate(cand_text, lo, hi, target)
        rounds += 1

        if cand_eval["in_window"]:
            prev_text = cand_text
            prev_eval = cand_eval
            round_flags.append(True)
            break

        dist_prev = _distance(prev_eval["word_count"], lo, hi)
        dist_cand = _distance(cand_eval["word_count"], lo, hi)

        judge_calls += 1
        scores = _judge(client, experiment, cand_text, prev_text, temperature)
        if scores is None:
            ratio = acceptance_ratio(dist_prev, dist_cand, None, None)
        else:
            score_cand, score_prev = scores
            ratio = acceptance_ratio(dist_prev, dist_cand, score_cand, score_prev)

        if ratio >= 1.0:
            prev_text = cand_text
            prev_eval = cand_eval
            round_flags.append(prev_eval["in_window"])
        else:
            rejected += 1
            round_flags.append(prev_eval["in_window"])
            break

    while len(round_flags) <= MAX_ROUNDS:
        round_flags.append(round_flags[-1])

    return {
        "text": prev_text,
        "finish_reason": finish_reason,
        "evaluation": prev_eval,
        "rounds": rounds,
        "rejected": rejected,
        "judge_calls": judge_calls,
        "initial_word_count": initial_word_count,
        "initial_in_window": initial_in_window,
        "round_flags": round_flags,
    }
