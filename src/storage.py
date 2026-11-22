"""Aggregation and aggregated-CSV output."""

import csv
import statistics
from collections import OrderedDict

COLUMNS = [
    "id",
    "name",
    "group",
    "length",
    "formality",
    "technique",
    "target",
    "lo",
    "hi",
    "asked_target",
    "n",
    "errors",
    "mean_words",
    "median_words",
    "std_words",
    "min_words",
    "max_words",
    "pct_in_window",
    "pct_under",
    "pct_over",
    "mae_vs_target",
    "mean_sentences",
    "mean_paragraphs",
    "mean_retries",
    "mean_initial_words",
    "pct_in_window_r0",
    "pct_in_window_r1",
    "pct_in_window_r2",
    "pct_in_window_r3",
    "pct_in_window_r4",
    "pct_in_window_r5",
    "mean_rounds",
    "mean_rejected",
    "mean_judge_calls",
]

RECORD_COLUMNS = [
    "id",
    "name",
    "group",
    "length",
    "formality",
    "technique",
    "run_index",
    "target",
    "lo",
    "hi",
    "asked_target",
    "user_question",
    "response",
    "word_count",
    "sentence_count",
    "paragraph_count",
    "in_window",
    "under",
    "over",
    "retries",
    "finish_reason",
    "error",
]


def _blank(value):
    return "" if value is None else value


def _round(value):
    return "" if value is None else round(value, 3)


def _pct(flags):
    flags = [flag for flag in flags if flag is not None]
    if not flags:
        return ""
    return round(100.0 * sum(1 for flag in flags if flag) / len(flags), 1)


def _mean(values):
    values = [value for value in values if value is not None]
    if not values:
        return ""
    return round(statistics.fmean(values), 3)


def _records_by_experiment(records):
    grouped = OrderedDict()
    for record in records:
        grouped.setdefault(record["experiment_id"], []).append(record)
    return grouped


def aggregate(records):
    """Collapse per-request records into one summary row per experiment."""
    rows = []
    for experiment_id, group in _records_by_experiment(records).items():
        first = group[0]
        word_counts = [r["word_count"] for r in group if r["word_count"] is not None]
        n = len(word_counts)

        if n:
            mean_words = round(statistics.fmean(word_counts), 3)
            median_words = round(statistics.median(word_counts), 3)
            std_words = round(statistics.pstdev(word_counts), 3) if n > 1 else 0.0
            min_words = min(word_counts)
            max_words = max(word_counts)
        else:
            mean_words = median_words = std_words = min_words = max_words = ""

        row = OrderedDict(
            [
                ("id", _blank(first.get("num_id"))),
                ("name", experiment_id),
                ("group", first["group"]),
                ("length", _blank(first["length"])),
                ("formality", _blank(first["formality"])),
                ("technique", first["technique"]),
                ("target", _blank(first["target"])),
                ("lo", _blank(first["lo"])),
                ("hi", _blank(first["hi"])),
                ("asked_target", _blank(first["asked_target"])),
                ("n", n),
                ("errors", sum(1 for r in group if r["error"])),
                ("mean_words", mean_words),
                ("median_words", median_words),
                ("std_words", std_words),
                ("min_words", min_words),
                ("max_words", max_words),
                ("pct_in_window", _pct([r["in_window"] for r in group])),
                ("pct_under", _pct([r["under"] for r in group])),
                ("pct_over", _pct([r["over"] for r in group])),
                ("mae_vs_target", _mean([r["abs_error"] for r in group])),
                ("mean_sentences", _mean([r["sentence_count"] for r in group])),
                ("mean_paragraphs", _mean([r["paragraph_count"] for r in group])),
                ("mean_retries", _mean([r["retries"] for r in group])),
                (
                    "mean_initial_words",
                    _mean([r.get("initial_word_count") for r in group]),
                ),
                ("pct_in_window_r0", _pct([r.get("in_window_r0") for r in group])),
                ("pct_in_window_r1", _pct([r.get("in_window_r1") for r in group])),
                ("pct_in_window_r2", _pct([r.get("in_window_r2") for r in group])),
                ("pct_in_window_r3", _pct([r.get("in_window_r3") for r in group])),
                ("pct_in_window_r4", _pct([r.get("in_window_r4") for r in group])),
                ("pct_in_window_r5", _pct([r.get("in_window_r5") for r in group])),
                ("mean_rounds", _mean([r.get("rounds") for r in group])),
                ("mean_rejected", _mean([r.get("rejected") for r in group])),
                ("mean_judge_calls", _mean([r.get("judge_calls") for r in group])),
            ]
        )
        rows.append(row)
    rows.sort(key=lambda row: row["id"] if isinstance(row["id"], int) else 0)
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_records_csv(path, records):
    """Write one row per request (includes the user question and response)."""
    records = sorted(
        records,
        key=lambda r: (r.get("num_id") or 0, r.get("run_index") or 0),
    )
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECORD_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "id": _blank(record.get("num_id")),
                    "name": record.get("experiment_id", ""),
                    "group": record.get("group", ""),
                    "length": _blank(record.get("length")),
                    "formality": _blank(record.get("formality")),
                    "technique": record.get("technique", ""),
                    "run_index": _blank(record.get("run_index")),
                    "target": _blank(record.get("target")),
                    "lo": _blank(record.get("lo")),
                    "hi": _blank(record.get("hi")),
                    "asked_target": _blank(record.get("asked_target")),
                    "user_question": record.get("user_question", ""),
                    "response": record.get("response", ""),
                    "word_count": _blank(record.get("word_count")),
                    "sentence_count": _blank(record.get("sentence_count")),
                    "paragraph_count": _blank(record.get("paragraph_count")),
                    "in_window": _blank(record.get("in_window")),
                    "under": _blank(record.get("under")),
                    "over": _blank(record.get("over")),
                    "retries": _blank(record.get("retries")),
                    "finish_reason": _blank(record.get("finish_reason")),
                    "error": _blank(record.get("error")),
                }
            )
