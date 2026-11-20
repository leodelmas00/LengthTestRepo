# LengthTestRepo

Benchmark harness to measure which prompting technique makes an LLM respect a
requested response length (short vs long) while keeping a register (formal vs
informal). The focus is **length**; formality is the second, independent
dimension.
- Model: `mistralai/Mistral-Small-3.2-24B-Instruct-2506` (DeepInfra).
- Temperature `0`, no memory.
- 100 requests per experiment by default.
- Output: one **aggregated CSV** (`results/summary.csv`).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add DEEPINFRA_API_KEY
```

## Usage

```bash
python run.py --list                 # show the 39 experiments
python run.py --dry-run              # print assembled prompts, no API calls
python run.py --experiments baseline --n 2
python run.py --n 100 --concurrency 8 --out results/summary.csv
```

Select experiments by id (`combo__short_informal`) or by group
(`baseline`, `aislados`, `combinaciones`, `over_asking`, `unidad_a`, `unidad_b`,
`desacople_informal`, `one_shot`, `few_shot`, `retry_concrete`, `retry_generic`).

## Prompt assembly

```
BASE
{LENGTH MODULE}        (optional)
{FORMALITY MODULE}     (optional)
{ANTI-INTERFERENCE GUARDRAIL}   (always)
{EXAMPLE MODULE}       (optional)
```

The user prompt is fixed:
`Hi, can you book me a flight from Buenos Aires to Mexico?`

## Experiments (39)

| Group | Cells |
|---|---|
| `baseline` | BASE only |
| `aislados` | length-short, length-long, formality-formal, formality-informal |
| `combinaciones` | short/long × formal/informal |
| `over_asking` | 4 cells, over-asked length modules (short→60-90, long→200-260) |
| `unidad_a` | 4 cells, sentences-based length instruction |
| `unidad_b` | 4 cells, paragraphs-based length instruction |
| `desacople_informal` | short+informal, long+informal with decoupled informal module |
| `one_shot` | 4 cells, 1 example from `few_shot_bank.json` |
| `few_shot` | 4 cells, 3 fixed examples |
| `retry_concrete` | 4 cells, external word counter + numeric feedback (max 2 retries) |
| `retry_generic` | 4 cells, direction-only feedback (max 2 retries) |

Evaluation windows are always the **desired** ones: short `[30, 60]` (target 45),
long `[140, 200]` (target 170). Over-asking cells record both `target` and
`asked_target` so the per-cell correction factor can be derived.

## Metrics

Per experiment the aggregated CSV reports: `n`, `errors`, `mean/median/std/min/max`
words, `pct_in_window`, `pct_under`, `pct_over`, `mae_vs_target`,
`mean_sentences`, `mean_paragraphs`, `mean_retries`.

Word counting is done in code with `len(text.split())`, matching the
`word_count` values in `few_shot_bank.json`.

## Layout

```
config/prompts.py       # prompt modules + build_system_prompt / build_example_module
config/experiments.py   # 39 experiment definitions
src/client.py           # DeepInfra (OpenAI-compatible) client
src/metrics.py          # word / sentence / paragraph counting + window evaluation
src/runner.py           # generation + retry loop
src/storage.py          # aggregation + CSV writer
run.py                  # CLI
few_shot_bank.json      # example bank (6 situations × 4 cells)
```
