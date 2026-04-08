#!/usr/bin/env python3
from __future__ import annotations

"""
Generate reproducible synthetic Council test cases.

Usage examples:
  python3 scripts/demo/generate_council_synthetic_cases.py
  python3 scripts/demo/generate_council_synthetic_cases.py --seed 20260406 --total-cases 80
  python3 scripts/demo/generate_council_synthetic_cases.py \
    --output data/demo/council-synthetic-cases-custom.json
"""

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "demo"
SUPPORTED_SPECIALISTS = (
    "cardiology",
    "neurology",
    "nephrology",
    "pharmacology",
    "endocrinology",
)

_TRIAGE_WEIGHTS = (
    ("routine_follow_up", 0.35),
    ("same_day_review", 0.35),
    ("emergency_escalation", 0.20),
    ("insufficient_data", 0.10),
)

_ROUTINE_SYMPTOMS = (
    "mild fatigue for 3 days",
    "intermittent palpitations for 1 week",
    "mild headache after work",
    "light ankle swelling in evening",
    "increased thirst but able to eat",
    "occasional dizziness when standing",
)
_ROUTINE_MEDS = (
    "metformin 500mg daily",
    "amlodipine 5mg daily",
    "atorvastatin 10mg nightly",
    "vitamin d supplement",
)
_ROUTINE_HISTORY = (
    "type 2 diabetes",
    "hypertension",
    "dyslipidemia",
    "family history of diabetes",
)

_SAME_DAY_SYMPTOMS = (
    "worsening palpitations today",
    "persistent dizziness for 24 hours",
    "moderate breathlessness on exertion",
    "moderate edema with reduced urine output",
    "polyuria and blurry vision for 2 days",
    "new reduced concentration episodes this morning",
)
_SAME_DAY_MEDS = (
    "metformin 1000mg daily",
    "ibuprofen 400mg as needed",
    "furosemide 20mg daily",
    "aspirin 81mg daily",
)
_SAME_DAY_HISTORY = (
    "type 2 diabetes",
    "chronic kidney disease stage 3",
    "prior transient ischemic attack",
    "heart failure history",
)

_EMERGENCY_PATTERNS: tuple[dict[str, Any], ...] = (
    {
        "symptoms": ["severe chest pain now", "shortness of breath worsening quickly"],
        "labs": lambda rng: {
            "troponin": round(rng.uniform(0.06, 0.20), 3),
            "bnp": round(rng.uniform(420, 980), 1),
            "glucose": round(rng.uniform(150, 260), 1),
        },
        "meds": ["warfarin 3mg daily", "metformin 500mg daily"],
        "history": ["coronary artery disease", "hypertension"],
    },
    {
        "symptoms": ["one sided weakness started 1 hour ago", "slurred speech"],
        "labs": lambda rng: {
            "glucose": round(rng.uniform(120, 220), 1),
            "creatinine": round(rng.uniform(0.9, 1.8), 2),
        },
        "meds": ["aspirin 81mg daily"],
        "history": ["prior stroke", "atrial fibrillation"],
    },
    {
        "symptoms": ["severe bleeding and black stool", "fainting episode today"],
        "labs": lambda rng: {
            "hemoglobin": round(rng.uniform(6.0, 9.5), 1),
            "potassium": round(rng.uniform(3.1, 4.9), 2),
        },
        "meds": ["warfarin 5mg daily", "ibuprofen 400mg"],
        "history": ["peptic ulcer history"],
    },
    {
        "symptoms": ["cannot breathe while resting", "confusion and sweating"],
        "labs": lambda rng: {
            "glucose": round(rng.uniform(42, 68), 1),
            "potassium": round(rng.uniform(5.9, 6.8), 2),
            "egfr": round(rng.uniform(18, 38), 1),
        },
        "meds": ["insulin therapy", "spironolactone 25mg"],
        "history": ["chronic kidney disease", "type 2 diabetes"],
    },
)

_INSUFFICIENT_SYMPTOMS = (
    "denies chest pain",
    "no shortness of breath",
    "fatigue",
    "not sure about symptom timeline",
)


def _safe_ratio(value: float, fallback: float) -> float:
    if not isinstance(value, (int, float)):
        return fallback
    parsed = float(value)
    if parsed < 0:
        return fallback
    return parsed


def _pick_weighted(rng: random.Random, weights: list[tuple[str, float]]) -> str:
    total = sum(weight for _, weight in weights)
    if total <= 0:
        return "routine_follow_up"
    roll = rng.uniform(0.0, total)
    running = 0.0
    for label, weight in weights:
        running += weight
        if roll <= running:
            return label
    return weights[-1][0]


def _pick_specialists(rng: random.Random) -> list[str]:
    count = rng.randint(2, len(SUPPORTED_SPECIALISTS))
    return sorted(rng.sample(list(SUPPORTED_SPECIALISTS), k=count))


def _sample_list(rng: random.Random, pool: tuple[str, ...], minimum: int, maximum: int) -> list[str]:
    if minimum > maximum:
        minimum, maximum = maximum, minimum
    upper = min(maximum, len(pool))
    lower = min(minimum, upper)
    if upper <= 0:
        return []
    count = rng.randint(lower, upper)
    return rng.sample(list(pool), k=count)


def _routine_case(rng: random.Random, case_id: str) -> dict[str, Any]:
    labs = {
        "glucose": round(rng.uniform(105, 185), 1),
        "egfr": round(rng.uniform(62, 96), 1),
        "creatinine": round(rng.uniform(0.7, 1.3), 2),
    }
    payload = {
        "symptoms": _sample_list(rng, _ROUTINE_SYMPTOMS, minimum=2, maximum=4),
        "labs": labs,
        "medications": _sample_list(rng, _ROUTINE_MEDS, minimum=1, maximum=2),
        "history": _sample_list(rng, _ROUTINE_HISTORY, minimum=1, maximum=2),
        "specialists": _pick_specialists(rng),
    }
    return {
        "case_id": case_id,
        "severity": "routine_follow_up",
        "payload": payload,
        "expectations": {
            "expected_min_triage": "routine_follow_up",
            "expect_emergency": False,
            "expect_needs_more_info": False,
            "expected_confidence_min": 0.35,
        },
    }


def _same_day_case(rng: random.Random, case_id: str) -> dict[str, Any]:
    labs = {
        "glucose": round(rng.uniform(190, 320), 1),
        "egfr": round(rng.uniform(42, 66), 1),
        "creatinine": round(rng.uniform(1.2, 2.3), 2),
        "potassium": round(rng.uniform(4.7, 5.6), 2),
    }
    payload = {
        "symptoms": _sample_list(rng, _SAME_DAY_SYMPTOMS, minimum=2, maximum=4),
        "labs": labs,
        "medications": _sample_list(rng, _SAME_DAY_MEDS, minimum=2, maximum=3),
        "history": _sample_list(rng, _SAME_DAY_HISTORY, minimum=1, maximum=2),
        "specialists": _pick_specialists(rng),
    }
    return {
        "case_id": case_id,
        "severity": "same_day_review",
        "payload": payload,
        "expectations": {
            "expected_min_triage": "routine_follow_up",
            "expect_needs_more_info": False,
            "expected_confidence_min": 0.30,
        },
    }


def _emergency_case(rng: random.Random, case_id: str) -> dict[str, Any]:
    template = rng.choice(_EMERGENCY_PATTERNS)
    payload = {
        "symptoms": list(template["symptoms"]),
        "labs": template["labs"](rng),
        "medications": list(template["meds"]),
        "history": list(template["history"]),
        "specialists": _pick_specialists(rng),
    }
    return {
        "case_id": case_id,
        "severity": "emergency_escalation",
        "payload": payload,
        "expectations": {
            "expected_min_triage": "emergency_escalation",
            "expect_emergency": True,
            "expect_needs_more_info": False,
            "expected_confidence_min": 0.30,
        },
    }


def _insufficient_case(rng: random.Random, case_id: str) -> dict[str, Any]:
    symptoms = _sample_list(rng, _INSUFFICIENT_SYMPTOMS, minimum=1, maximum=2)
    payload = {
        "symptoms": symptoms,
        "labs": {},
        "medications": [],
        "history": [],
        "specialists": _pick_specialists(rng),
    }
    return {
        "case_id": case_id,
        "severity": "insufficient_data",
        "payload": payload,
        "expectations": {
            "expected_min_triage": "routine_follow_up",
            "expect_emergency": False,
            "expect_needs_more_info": True,
            "expected_confidence_max": 0.55,
        },
    }


def _build_case(rng: random.Random, severity: str, case_id: str) -> dict[str, Any]:
    if severity == "routine_follow_up":
        return _routine_case(rng, case_id)
    if severity == "same_day_review":
        return _same_day_case(rng, case_id)
    if severity == "emergency_escalation":
        return _emergency_case(rng, case_id)
    return _insufficient_case(rng, case_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic Council test cases.")
    parser.add_argument("--seed", type=int, default=20260406)
    parser.add_argument("--total-cases", type=int, default=60)
    parser.add_argument("--routine-ratio", type=float, default=0.35)
    parser.add_argument("--same-day-ratio", type=float, default=0.35)
    parser.add_argument("--emergency-ratio", type=float, default=0.20)
    parser.add_argument("--insufficient-ratio", type=float, default=0.10)
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path. Default: data/demo/council-synthetic-cases-seed{seed}-n{n}.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    total_cases = max(int(args.total_cases), 1)
    rng = random.Random(int(args.seed))

    weights = [
        ("routine_follow_up", _safe_ratio(args.routine_ratio, _TRIAGE_WEIGHTS[0][1])),
        ("same_day_review", _safe_ratio(args.same_day_ratio, _TRIAGE_WEIGHTS[1][1])),
        ("emergency_escalation", _safe_ratio(args.emergency_ratio, _TRIAGE_WEIGHTS[2][1])),
        ("insufficient_data", _safe_ratio(args.insufficient_ratio, _TRIAGE_WEIGHTS[3][1])),
    ]
    if sum(weight for _, weight in weights) <= 0:
        weights = list(_TRIAGE_WEIGHTS)

    if args.output.strip():
        output_path = Path(args.output).resolve()
    else:
        output_path = (
            DEFAULT_OUTPUT_DIR
            / f"council-synthetic-cases-seed{int(args.seed)}-n{total_cases}.json"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    severity_plan: list[str] = []
    base_labels = [
        "routine_follow_up",
        "same_day_review",
        "emergency_escalation",
        "insufficient_data",
    ]
    if total_cases >= len(base_labels):
        severity_plan.extend(base_labels)
        while len(severity_plan) < total_cases:
            severity_plan.append(_pick_weighted(rng, weights))
        rng.shuffle(severity_plan)
    else:
        for _ in range(total_cases):
            severity_plan.append(_pick_weighted(rng, weights))

    cases: list[dict[str, Any]] = []
    for index, severity in enumerate(severity_plan, start=1):
        case_id = f"syn-{index:04d}"
        case = _build_case(rng, severity, case_id)
        case["generator_meta"] = {"seed": int(args.seed), "index": index}
        cases.append(case)

    severity_counts: dict[str, int] = {}
    for item in cases:
        severity = str(item.get("severity") or "unknown")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    payload = {
        "meta": {
            "generator": "council_synthetic_case_generator_v1",
            "seed": int(args.seed),
            "total_cases": total_cases,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "severity_counts": severity_counts,
            "notes": "Synthetic cases for local council endpoint evaluation only.",
        },
        "cases": cases,
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "[generate-council-synthetic-cases] "
        f"output={output_path} total_cases={total_cases} seed={int(args.seed)}"
    )


if __name__ == "__main__":
    main()
