# Column reference

Two kinds of CSV are produced.

## `results/summary.csv` (aggregated, one row per experiment)

Identification

- `id` — numeric, unique experiment id (1..47, assignment order).
- `name` — readable key, e.g. `unidad_a__short_informal` (used for CLI selection).
- `group` — technique group (e.g. `unidad_a - sentences`).
- `length` — `short` / `long`; **blank** when the experiment has no length dimension.
- `formality` — `formal` / `informal`; **blank** when it has no formality dimension.
- `technique` — short technique code (e.g. `combo`, `sentences`, `metropolis_hastings`).

Length window (desired)

- `target` — desired word target: 45 (short) / 170 (long). **Blank** without a length module.
- `lo` / `hi` — desired window bounds: 30–60 (short), 140–200 (long).
- `asked_target` — target actually written in the prompt. Usually equals `target`;
  in `over_asking` it is larger on purpose (75 / 230).

Sample

- `n` — number of valid responses (with a word count). With `--n 1` this is 1.
- `errors` — failed requests.

Word statistics (computed on the cleaned text)

- `mean_words`, `median_words`, `std_words`, `min_words`, `max_words`.
  With `n=1`, mean = median = min = max and `std_words = 0`.

Window compliance

- `pct_in_window` — % of responses within `[lo, hi]`.
- `pct_under` — % below `lo`.
- `pct_over` — % above `hi`.
- `mae_vs_target` — mean absolute error in words vs `target`.

Structure / cost

- `mean_sentences`, `mean_paragraphs` — average sentence / paragraph counts.
- `mean_retries` — average retries used (0 for one-shot; retries for retry, rounds for MH).

`retry_mh` only (blank for every other technique)

- `mean_initial_words` — words in the initial response before revisions.
- `pct_in_window_r0` … `pct_in_window_r5` — % in window after k rounds (r0 = initial).
- `mean_rounds` — average rounds used.
- `mean_rejected` — average rejected candidates.
- `mean_judge_calls` — average judge calls.

### Why some fields are blank

- `baseline__base` has neither dimension → `length`, `formality`, `target`, `lo`, `hi` blank.
- `aislado__length_*` has only length → `formality` blank.
- `aislado__formality_*` has only formality → `length`, `target`, `lo`, `hi` blank.
- The `retry_mh` columns are only filled for the 4 `retry_mh` cells.

## `results/<technique>.csv` (per request, one row per request)

- `id`, `name`, `group`, `length`, `formality`, `technique` — as above.
- `run_index` — which repetition this is (`0..n-1`).
- `target`, `lo`, `hi`, `asked_target` — as above.
- `user_question` — the fixed user prompt.
- `response` — the model's final response (for `countdown`, markers already removed).
- `word_count`, `sentence_count`, `paragraph_count` — counts on the response.
- `in_window`, `under`, `over` — window result for this request.
- `retries` — retries/rounds used for this request.
- `finish_reason` — model stop reason.
- `error` — error message if the request failed, else blank.
