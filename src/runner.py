"""Generation loop, including the retry / iterative-sampling mechanisms."""

import time

from config import prompts as P
from src.metrics import evaluate
from src.mh import MAX_ROUNDS, run_mh


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


def _empty_evaluation():
    return {
        "word_count": None,
        "sentence_count": None,
        "paragraph_count": None,
        "in_window": None,
        "under": None,
        "over": None,
        "abs_error": None,
    }


def _run_simple_retry(client, experiment, messages, max_retries, temperature):
    """Generate once, then apply concrete/generic feedback retries."""
    result = client.chat(messages, temperature=temperature)
    text = result["text"]
    finish_reason = result["finish_reason"]
    retries = 0

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

    return text, finish_reason, retries


def run_request(client, experiment, max_retries=2, temperature=0.0):
    """Generate one response for an experiment, applying the configured mechanism."""
    system_prompt = build_system(experiment)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": P.USER_PROMPT},
    ]

    started = time.time()
    error = None
    text = ""
    finish_reason = None
    retries = 0
    evaluation = None
    mh_result = None

    try:
        if experiment.retry_mode == "mh":
            mh_result = run_mh(
                client, experiment, system_prompt, temperature=temperature
            )
            text = mh_result["text"]
            finish_reason = mh_result["finish_reason"]
            evaluation = mh_result["evaluation"]
            retries = mh_result["rounds"]
        else:
            text, finish_reason, retries = _run_simple_retry(
                client, experiment, messages, max_retries, temperature
            )
            evaluation = evaluate(
                text, experiment.lo, experiment.hi, experiment.target
            )
    except Exception as exc:  # noqa: BLE001 - recorded per request, run continues
        error = "%s: %s" % (type(exc).__name__, exc)
        evaluation = _empty_evaluation()

    latency_ms = (time.time() - started) * 1000.0

    record = {
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
        # MH-specific fields (None for the other techniques)
        "initial_word_count": None,
        "initial_in_window": None,
        "rounds": None,
        "rejected": None,
        "judge_calls": None,
    }
    for index in range(MAX_ROUNDS + 1):
        record["in_window_r%d" % index] = None

    if mh_result is not None and error is None:
        record["initial_word_count"] = mh_result["initial_word_count"]
        record["initial_in_window"] = mh_result["initial_in_window"]
        record["rounds"] = mh_result["rounds"]
        record["rejected"] = mh_result["rejected"]
        record["judge_calls"] = mh_result["judge_calls"]
        for index, flag in enumerate(mh_result["round_flags"]):
            record["in_window_r%d" % index] = flag

    return record
