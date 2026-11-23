# LengthTestRepo

Benchmark harness to measure which prompting technique makes an LLM respect a
requested response length (short vs long) while keeping a register (formal vs
informal). The focus is **length**; formality is the second, independent
dimension.
- Model: `mistralai/Mistral-Small-3.2-24B-Instruct-2506` (DeepInfra).
- Temperature `0`, no memory.
- 100 requests per experiment by default.
- Outputs: aggregated `results/summary.csv` plus one per-technique CSV with
  one row per request (includes the user question and the model response).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add DEEPINFRA_API_KEY
```

## Usage

```bash
python run.py --list                 # show all experiments with numeric ids
python run.py --dry-run              # print assembled prompts, no API calls
python run.py --experiments baseline --n 2
python run.py --n 100 --concurrency 8 --out results/summary.csv
```

Select experiments by id (`unidad_a__short_informal`), by group
(`baseline`, `aislados`, `combinaciones`, `over_asking`, `unidad_a - sentences`,
`unidad_b - paragraphs`, `desacople_informal`, `one_shot`, `few_shot`,
`retry_concrete`, `retry_generic`, `retry_mh`, `countdown`) or by numeric id
(`14`).

### Parameters

| Flag | Default | Purpose |
|---|---|---|
| `--experiments` | `all` | Comma-separated ids, groups and/or numeric ids to run. |
| `--n` | `100` | Requests per experiment (each "point" of the matrix). |
| `--concurrency` | `8` | Parallel worker threads. |
| `--out` | `results/summary.csv` | Aggregated CSV path; per-technique CSVs are written next to it. |
| `--temperature` | `0.0` | Sampling temperature (keep at 0). |
| `--max-retries` | `2` | Max retries for the retry experiments. |
| `--dry-run` | — | Print the assembled prompts; no API calls. |
| `--list` | — | List the 47 experiments with ids and exit. |

Examples:

```bash
python run.py --list                                   # see all experiments
python run.py --dry-run --experiments countdown        # inspect prompts, no API
python run.py --experiments retry_mh --n 100           # one technique, all cells
python run.py --experiments 14,15 --n 5                # by numeric id, quick test
python run.py --experiments retry_mh,retry_concrete --max-retries 5 --n 100  # fair comparison
python run.py --n 100 --concurrency 8 --out results/summary.csv
```

Note: retry experiments (`retry_concrete`, `retry_generic`, `retry_mh`) may make
more than one API call per request when a response lands outside the window.

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

## Experiments (47)

| Group | Cells |
|---|---|
| `baseline` | BASE only |
| `aislados` | length-short, length-long, formality-formal, formality-informal |
| `combinaciones` | short/long × formal/informal |
| `over_asking` | 4 cells, over-asked length modules (short→60-90, long→200-260) |
| `unidad_a - sentences` | 4 cells, sentences-based length instruction |
| `unidad_b - paragraphs` | 4 cells, paragraphs-based length instruction |
| `desacople_informal` | short+informal, long+informal with decoupled informal module |
| `one_shot` | 4 cells, 1 example from `few_shot_bank.json` |
| `few_shot` | 4 cells, 3 fixed examples |
| `retry_concrete` | 4 cells, external word counter + numeric feedback (max 2 retries) |
| `retry_generic` | 4 cells, direction-only feedback (max 2 retries) |
| `retry_mh` | 4 cells, Metropolis-Hastings iterative sampling + judge (max 5 rounds) |
| `countdown` | 4 cells, CAPEL countdown markers for exact length (one-shot) |

Evaluation windows are always the **desired** ones: short `[30, 60]` (target 45),
long `[140, 200]` (target 170). Over-asking cells record both `target` and
`asked_target` so the per-cell correction factor can be derived.

## Metrics

`results/summary.csv` is aggregated: one row per experiment with `id` (numeric),
`name` (readable key), `group`, `length`, `formality`, `technique`, `n`,
`errors`, `mean/median/std/min/max` words, `pct_in_window`, `pct_under`,
`pct_over`, `mae_vs_target`, `mean_sentences`, `mean_paragraphs`,
`mean_retries`, plus the `retry_mh` columns.

Each `results/<technique>.csv` is per-request: `id, name, group, length,
formality, technique, run_index, target, lo, hi, asked_target, user_question,
response, word_count, sentence_count, paragraph_count, in_window, under, over,
retries, finish_reason, error`. For `countdown`, `response` is already cleaned
of `<k>` markers.

Column reference (what each one means and why some cells are blank) is in
[COLUMNS.md](COLUMNS.md).

Word counting is done in code with `len(text.split())`, matching the
`word_count` values in `few_shot_bank.json`.

For `retry_mh` the CSV also reports `mean_initial_words`, the cumulative success
curve `pct_in_window_r0` … `pct_in_window_r5`, `mean_rounds`, `mean_rejected`
and `mean_judge_calls`. Other techniques leave these columns blank.

## Metropolis-Hastings (`retry_mh`)

Implements the iterative-sampling scheme from *Length Controlled Generation for
Black-box LLMs*. Flow: generate the initial response → if in the window, stop
(round 0); otherwise build `REVISION FEEDBACK`, generate a candidate and, if it
is in the window, accept it. If not, the judge (same Mistral, temperature 0)
scores candidate vs previous and the code computes
`ratio = (dist_prev / dist_cand) × (score_cand / score_prev)`. The candidate
replaces the previous if `ratio >= 1`; otherwise it is rejected and the loop
stops (deterministic at temperature 0). Maximum 5 rounds.

Constants: `MAX_ROUNDS=5`, `NEAR_THRESHOLD=3` words, `MARGIN=5` words.

Fair comparison against the numeric retry: run both with the same round budget.

```bash
python run.py --experiments retry_mh,retry_concrete --max-retries 5 --n 100
```

### Declared deviations from the paper

- `Keep the same register` and `Reply only with the new response` added.
- `+5` word margin in the near-window feedback.
- The score ratio is computed by code, not by the model.
- The judge uses a register-adherence criterion and switches to `conciseness`
  in short.
- Acceptance is deterministic instead of random sampling (temperature 0).
- The judge is not called when the candidate is already inside the window.

## CAPEL countdown (`countdown`)

A prompt-based, one-shot strategy: instead of a numeric instruction, the length
module asks the model to write while counting, emitting a `<k>` marker before
each word (`<N> ... <1>`) and terminating with `<0>`. The numeric length sentence
is replaced while the non-numeric instruction (`Develop the topic in depth…` for
long, `Do not add information…` for short) is kept. Formality and guardrail are
unchanged. The code strips the markers with
`re.sub(r"<\d+>", " ", text).strip()` before counting words, so only the real
words are measured. There is no retry loop and no judge.

The technique is isolated via `Experiment.strip_markers`; other experiments are
unaffected.

## Layout

```
config/prompts.py       # prompt modules + build_system_prompt / build_example_module
config/experiments.py   # 47 experiment definitions
src/client.py           # DeepInfra (OpenAI-compatible) client
src/metrics.py          # word / sentence / paragraph counting + window evaluation
src/runner.py           # generation + retry loop
src/mh.py               # Metropolis-Hastings sampler + judge filter
src/storage.py          # aggregation + CSV writer
run.py                  # CLI
few_shot_bank.json      # example bank (6 situations × 4 cells)
```
