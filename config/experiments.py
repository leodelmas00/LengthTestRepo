"""Declarative definition of every experiment.

Each experiment is one prompt configuration (a cell plus a technique) that is
repeated `--n` times (100 by default) against the same user prompt.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from config import prompts as P


@dataclass(frozen=True)
class Experiment:
    id: str
    group: str
    length: Optional[str]           # "short" | "long" | None
    formality: Optional[str]        # "formal" | "informal" | None
    technique: str
    length_module: Optional[str]
    formality_module: Optional[str]
    example_ids: Optional[Tuple[str, ...]]
    retry_mode: Optional[str]       # "concrete" | "generic" | None
    target: Optional[int]           # desired word target (evaluation)
    lo: Optional[int]               # desired window lower bound
    hi: Optional[int]               # desired window upper bound
    asked_target: Optional[int]     # target actually requested in the prompt


CELLS = [
    ("short", "formal"),
    ("short", "informal"),
    ("long", "formal"),
    ("long", "informal"),
]

# Desired evaluation window: (target, lo, hi)
WINDOWS = {
    "short": (45, 30, 60),
    "long": (170, 140, 200),
}

FORMALITY_MODS = {
    "formal": P.FORMALITY_FORMAL,
    "informal": P.FORMALITY_INFORMAL,
}


def _build():
    exps = []

    # 1. Baseline: BASE only (guardrail is always appended).
    exps.append(
        Experiment(
            "baseline__base", "baseline", None, None, "baseline",
            None, None, None, None, None, None, None, None,
        )
    )

    # 2. Isolated elements (one dimension active).
    exps.append(
        Experiment(
            "aislado__length_short", "aislados", "short", None, "length_only",
            P.LENGTH_SHORT, None, None, None, 45, 30, 60, 45,
        )
    )
    exps.append(
        Experiment(
            "aislado__length_long", "aislados", "long", None, "length_only",
            P.LENGTH_LONG, None, None, None, 170, 140, 200, 170,
        )
    )
    exps.append(
        Experiment(
            "aislado__formality_formal", "aislados", None, "formal", "formality_only",
            None, P.FORMALITY_FORMAL, None, None, None, None, None, None,
        )
    )
    exps.append(
        Experiment(
            "aislado__formality_informal", "aislados", None, "informal", "formality_only",
            None, P.FORMALITY_INFORMAL, None, None, None, None, None, None,
        )
    )

    def add_cells(group, technique, length_mods, formality_mods,
                  example_ids=None, retry_mode=None, asked=None):
        for length, formality in CELLS:
            target, lo, hi = WINDOWS[length]
            asked_target = asked[length] if asked else target
            exps.append(
                Experiment(
                    "%s__%s_%s" % (group, length, formality),
                    group,
                    length,
                    formality,
                    technique,
                    length_mods[length],
                    formality_mods[formality],
                    example_ids,
                    retry_mode,
                    target,
                    lo,
                    hi,
                    asked_target,
                )
            )

    # 3. Combinations (interference baseline).
    add_cells(
        "combinaciones", "combo",
        {"short": P.LENGTH_SHORT, "long": P.LENGTH_LONG},
        FORMALITY_MODS,
    )

    # 4. Over-asking.
    add_cells(
        "over_asking", "over_asking",
        {"short": P.LENGTH_SHORT_OVER, "long": P.LENGTH_LONG_OVER},
        FORMALITY_MODS,
        asked={"short": 75, "long": 230},
    )

    # 5. Alternative unit A: sentences.
    add_cells(
        "unidad_a", "sentences",
        {"short": P.LENGTH_SHORT_SENT, "long": P.LENGTH_LONG_SENT},
        FORMALITY_MODS,
    )

    # 6. Alternative unit B: paragraphs.
    add_cells(
        "unidad_b", "paragraphs",
        {"short": P.LENGTH_SHORT_PAR, "long": P.LENGTH_LONG_PAR},
        FORMALITY_MODS,
    )

    # 7. Decoupling the informal module from brevity.
    for length in ("short", "long"):
        target, lo, hi = WINDOWS[length]
        exps.append(
            Experiment(
                "desacople_informal__%s_informal" % length,
                "desacople_informal",
                length,
                "informal",
                "informal_decoupled",
                P.LENGTH_SHORT if length == "short" else P.LENGTH_LONG,
                P.FORMALITY_INFORMAL_DECOUPLED,
                None,
                None,
                target,
                lo,
                hi,
                target,
            )
        )

    # 8. One-shot examples.
    add_cells(
        "one_shot", "one_shot",
        {"short": P.LENGTH_SHORT, "long": P.LENGTH_LONG},
        FORMALITY_MODS,
        example_ids=P.ONE_SHOT_IDS,
    )

    # 9. Few-shot examples (3 fixed).
    add_cells(
        "few_shot", "few_shot",
        {"short": P.LENGTH_SHORT, "long": P.LENGTH_LONG},
        FORMALITY_MODS,
        example_ids=P.FEW_SHOT_IDS,
    )

    # 10. Retry with concrete feedback.
    add_cells(
        "retry_concrete", "retry_concrete",
        {"short": P.LENGTH_SHORT, "long": P.LENGTH_LONG},
        FORMALITY_MODS,
        retry_mode="concrete",
    )

    # 11. Retry with generic feedback.
    add_cells(
        "retry_generic", "retry_generic",
        {"short": P.LENGTH_SHORT, "long": P.LENGTH_LONG},
        FORMALITY_MODS,
        retry_mode="generic",
    )

    return exps


EXPERIMENTS = _build()
EXPERIMENT_IDS = {exp.id for exp in EXPERIMENTS}
GROUPS = {exp.group for exp in EXPERIMENTS}
