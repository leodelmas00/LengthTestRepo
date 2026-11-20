"""Generation loop, including the retry mechanisms."""

import time

from config import prompts as P
from src.metrics import evaluate


def _example_module(experiment):
    if not experiment.example_ids:
        return None
    return P.build_example_module(
        experiment.length, experiment.formality, experiment.example_ids
    )


def build_system(experiment):
    return P.build_system_prompt(
        experiment.length_module,
        experiment.formality_module,
        _example_module(experiment),
    )


def concrete_feedback(word_count, lo, hi, target, too_short):
    if too_short:
        action = (
            "expanding it with more detail and examples until it reaches about "
            "%d words" % target
        )
    else:
        action = (
            "shortening it by removing secondary details until it reaches about "
            "%d words" % target
        )
    return (
        "Your response has %d words. The required length is between %d and %d "
        "words (aim for about %d). Rewrite your previous response, %s. Keep the "
        "same register. Reply only with the new response, without comments."
        % (word_count, lo, hi, target, action)
    )


def generic_feedback(too_short):
    if too_short:
        return (
            "Your response is too short. Rewrite it so that it is longer. Keep the "
            "same register. Reply only with the new response, without comments."
        )
    return (
        "Your response is too long. Rewrite it so that it is shorter. Keep the "
        "same register. Reply only with the new response, without comments."
    )


def run_request(client, experiment, max_retries=2, temperature=0.0):
    """Generate one response for an experiment, applying retries if requested."""
    messages = [
        {"role": "system", "content": build_system(experiment)},
        {"role": "user", "content": P.USER_PROMPT},
    ]

    started = time.time()
    retries = 0
    error = None
    text = ""
    finish_reason = None

    try:
        result = client.chat(messages, temperature=temperature)
        text = result["text"]
        finish_reason = result["finish_reason"]

        while experiment.retry_mode and experiment.lo is not None:
            current = evaluate(text, experiment.lo, experiment.hi, experiment.target)
            if current["in_window"] or retries >= max_retries:
                break

            too_short = bool(current["under"])
            if experiment.retry_mode == "concrete":
                feedback = concrete_feedback(
                    current["word_count"],
                    experiment.lo,
                    experiment.hi,
                    experiment.target,
                    too_short,
                )
            elif experiment.retry_mode == "generic":
                feedback = generic_feedback(too_short)
            else:
                break

            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": feedback},
            ]
            retries += 1
            result = client.chat(messages, temperature=temperature)
            text = result["text"]
            finish_reason = result["finish_reason"]
    except Exception as exc:  # noqa: BLE001 - recorded per request, run continues
        error = "%s: %s" % (type(exc).__name__, exc)

    latency_ms = (time.time() - started) * 1000.0

    if error is None:
        evaluation = evaluate(text, experiment.lo, experiment.hi, experiment.target)
    else:
        evaluation = {
            "word_count": None,
            "sentence_count": None,
            "paragraph_count": None,
            "in_window": None,
            "under": None,
            "over": None,
            "abs_error": None,
        }

    return {
        "experiment_id": experiment.id,
        "group": experiment.group,
        "length": experiment.length,
        "formality": experiment.formality,
        "technique": experiment.technique,
        "target": experiment.target,
        "lo": experiment.lo,
        "hi": experiment.hi,
        "asked_target": experiment.asked_target,
        "word_count": evaluation["word_count"],
        "sentence_count": evaluation["sentence_count"],
        "paragraph_count": evaluation["paragraph_count"],
        "in_window": evaluation["in_window"],
        "under": evaluation["under"],
        "over": evaluation["over"],
        "abs_error": evaluation["abs_error"],
        "retries": retries,
        "latency_ms": latency_ms,
        "finish_reason": finish_reason,
        "error": error,
    }
