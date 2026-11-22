"""CLI entrypoint for the length-control benchmark.

Examples:
    python run.py --list
    python run.py --dry-run
    python run.py --experiments baseline --n 2
    python run.py --n 100 --concurrency 8 --out results/summary.csv

Outputs:
    results/summary.csv        aggregated, one row per experiment
    results/<technique>.csv    one row per request (question + response + metrics)
"""

import argparse
import os
import re
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.experiments import EXPERIMENTS, GROUPS
from src.runner import build_system, run_request
from src.storage import aggregate, write_csv, write_records_csv


def select_experiments(spec):
    if not spec or spec.strip() == "all":
        return list(EXPERIMENTS)

    wanted = [item.strip() for item in spec.split(",") if item.strip()]
    selected = [
        exp
        for exp in EXPERIMENTS
        if exp.id in wanted or exp.group in wanted or str(exp.num_id) in wanted
    ]
    known = (
        {exp.id for exp in EXPERIMENTS}
        | {exp.group for exp in EXPERIMENTS}
        | {str(exp.num_id) for exp in EXPERIMENTS}
    )
    missing = [item for item in wanted if item not in known]
    if missing:
        print("Advertencia: ids/grupos desconocidos: %s" % ", ".join(missing), file=sys.stderr)
    return selected


def _slug(text):
    return re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_")


def main():
    parser = argparse.ArgumentParser(description="Length-control benchmark harness.")
    parser.add_argument(
        "--experiments",
        default="all",
        help="Comma-separated experiment ids, groups or numeric ids (default: all).",
    )
    parser.add_argument("--n", type=int, default=100, help="Requests per experiment.")
    parser.add_argument("--concurrency", type=int, default=8, help="Concurrent requests.")
    parser.add_argument(
        "--out", default="results/summary.csv", help="Aggregated CSV output path."
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--max-retries", type=int, default=2, help="Max retries for retry experiments."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print assembled system prompts; no API calls.",
    )
    parser.add_argument(
        "--list", action="store_true", help="List experiments and exit."
    )
    args = parser.parse_args()

    if args.list:
        for exp in EXPERIMENTS:
            print(
                "%-3d %-40s %-24s %s/%s"
                % (exp.num_id, exp.id, exp.group, exp.length, exp.formality)
            )
        print("\nTotal: %d experiments (%d groups)" % (len(EXPERIMENTS), len(GROUPS)))
        return

    experiments = select_experiments(args.experiments)
    if not experiments:
        print("No hay experimentos seleccionados.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        for exp in experiments:
            print("=" * 90)
            print("[%d] %s" % (exp.num_id, exp.id))
            print("-" * 90)
            print(build_system(exp))
        return

    from src.client import DeepInfraClient

    client = DeepInfraClient()
    total = len(experiments) * args.n
    print(
        "Ejecutando %d experimentos x %d requests = %d requests (concurrency=%d)"
        % (len(experiments), args.n, total, args.concurrency)
    )

    tasks = [(exp, index) for exp in experiments for index in range(args.n)]
    records = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(
                run_request, client, exp, args.max_retries, args.temperature
            ): (exp, run_index)
            for exp, run_index in tasks
        }
        for future in as_completed(futures):
            exp, run_index = futures[future]
            try:
                record = future.result()
            except Exception as exc:  # noqa: BLE001 - defensive, run continues
                record = {
                    "experiment_id": exp.id,
                    "num_id": exp.num_id,
                    "group": exp.group,
                    "length": exp.length,
                    "formality": exp.formality,
                    "technique": exp.technique,
                    "target": exp.target,
                    "lo": exp.lo,
                    "hi": exp.hi,
                    "asked_target": exp.asked_target,
                    "word_count": None,
                    "sentence_count": None,
                    "paragraph_count": None,
                    "in_window": None,
                    "under": None,
                    "over": None,
                    "abs_error": None,
                    "retries": 0,
                    "latency_ms": 0.0,
                    "finish_reason": None,
                    "error": "%s: %s" % (type(exc).__name__, exc),
                    "user_question": "",
                    "response": "",
                }
            record["run_index"] = run_index
            records.append(record)
            done += 1
            if record["error"]:
                print(
                    "  [%d/%d] ERROR %s -> %s"
                    % (done, total, record["experiment_id"], record["error"]),
                    file=sys.stderr,
                )
            else:
                print(
                    "  [%d/%d] %s (run %d) -> %s words"
                    % (
                        done,
                        total,
                        record["experiment_id"],
                        run_index,
                        record["word_count"],
                    )
                )

    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    rows = aggregate(records)
    write_csv(args.out, rows)

    by_group = OrderedDict()
    for record in records:
        by_group.setdefault(record["group"], []).append(record)
    for group, group_records in by_group.items():
        path = os.path.join(out_dir, _slug(group) + ".csv")
        write_records_csv(path, group_records)

    print("Resumen agregado escrito en: %s (%d filas)" % (args.out, len(rows)))
    print("CSV por tecnica escritos en: %s (%d archivos)" % (out_dir, len(by_group)))


if __name__ == "__main__":
    main()
