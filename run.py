"""CLI entrypoint for the length-control benchmark.

Examples:
    python run.py --list
    python run.py --dry-run
    python run.py --experiments baseline --n 2
    python run.py --n 100 --concurrency 8 --out results/summary.csv
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.experiments import EXPERIMENTS, GROUPS
from src.runner import build_system, run_request
from src.storage import aggregate, write_csv


def select_experiments(spec):
    if not spec or spec.strip() == "all":
        return list(EXPERIMENTS)

    wanted = [item.strip() for item in spec.split(",") if item.strip()]
    selected = [
        exp
        for exp in EXPERIMENTS
        if exp.id in wanted or exp.group in wanted
    ]
    known = {exp.id for exp in EXPERIMENTS} | {exp.group for exp in EXPERIMENTS}
    missing = [item for item in wanted if item not in known]
    if missing:
        print("Advertencia: ids/grupos desconocidos: %s" % ", ".join(missing), file=sys.stderr)
    return selected


def main():
    parser = argparse.ArgumentParser(description="Length-control benchmark harness.")
    parser.add_argument(
        "--experiments",
        default="all",
        help="Comma-separated experiment ids and/or groups (default: all).",
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
            print("%-40s %-22s %s/%s" % (exp.id, exp.group, exp.length, exp.formality))
        print("\nTotal: %d experiments (%d groups)" % (len(EXPERIMENTS), len(GROUPS)))
        return

    experiments = select_experiments(args.experiments)
    if not experiments:
        print("No hay experimentos seleccionados.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        for exp in experiments:
            print("=" * 90)
            print(exp.id)
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

    records = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(
                run_request, client, exp, args.max_retries, args.temperature
            ): exp.id
            for exp in experiments
            for _ in range(args.n)
        }
        for future in as_completed(futures):
            experiment_id = futures[future]
            try:
                record = future.result()
            except Exception as exc:  # noqa: BLE001 - defensive, run continues
                record = {
                    "experiment_id": experiment_id,
                    "group": "",
                    "length": None,
                    "formality": None,
                    "technique": "",
                    "target": None,
                    "lo": None,
                    "hi": None,
                    "asked_target": None,
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
                    "initial_word_count": None,
                    "initial_in_window": None,
                    "rounds": None,
                    "rejected": None,
                    "judge_calls": None,
                    "in_window_r0": None,
                    "in_window_r1": None,
                    "in_window_r2": None,
                    "in_window_r3": None,
                    "in_window_r4": None,
                    "in_window_r5": None,
                }
            records.append(record)
            done += 1
            if record["error"]:
                print(
                    "  [%d/%d] ERROR %s -> %s"
                    % (done, total, experiment_id, record["error"]),
                    file=sys.stderr,
                )
            elif done % max(1, args.concurrency) == 0 or done == total:
                print("  [%d/%d] completados" % (done, total))

    rows = aggregate(records)
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    write_csv(args.out, rows)
    print("Resumen agregado escrito en: %s (%d filas)" % (args.out, len(rows)))


if __name__ == "__main__":
    main()
