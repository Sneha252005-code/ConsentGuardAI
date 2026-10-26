
"""Evaluate ConsentGuardAI prompt filtering against test cases."""

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from genai_gateway.prompt_filter import filter_prompt

EVALUATION_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALUATION_DIR / "results"
TEST_CASES_FILE = EVALUATION_DIR / "test_cases.csv"


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test cases file not found: {TEST_CASES_FILE}"
        )

    with TEST_CASES_FILE.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        reader = csv.DictReader(file)
        cases = list(reader)

    if not cases:
        raise ValueError("test_cases.csv contains no test cases.")

    print("CSV columns:", list(cases[0].keys()))

    results = []

    for case_number, case in enumerate(cases, start=1):
        prompt = (
            case.get("prompt")
            or case.get("input")
            or case.get("text")
            or ""
        ).strip()

        expected = (
            case.get("expected")
            or case.get("expected_result")
            or case.get("expected_label")
            or ""
        ).strip().lower()

        if not prompt:
            print(f"Skipping case {case_number}: missing prompt.")
            continue

        if not expected:
            print(f"Skipping case {case_number}: missing expected label.")
            continue

        expected_blocked = expected in {
            "block",
            "blocked",
            "true",
            "1",
            "unsafe",
            "reject",
        }

        try:
            outcome = filter_prompt(prompt)
            blocked = not outcome.allowed
            reason = outcome.reason
            error = ""
        except Exception as exc:
            blocked = None
            reason = ""
            error = str(exc)

        correct = (
            blocked == expected_blocked
            if blocked is not None
            else False
        )

        results.append({
            "case_number": case_number,
            "prompt": prompt,
            "expected_blocked": expected_blocked,
            "actual_blocked": blocked,
            "correct": correct,
            "reason": reason,
            "error": error,
        })

    if not results:
        raise ValueError(
            "No usable test cases found. Check the CSV headers "
            "and expected labels."
        )

    total = len(results)
    correct_count = sum(row["correct"] for row in results)
    blocked_count = sum(
        row["actual_blocked"] is True for row in results
    )
    allowed_count = sum(
        row["actual_blocked"] is False for row in results
    )
    error_count = sum(
        row["actual_blocked"] is None for row in results
    )

    metrics = {
        "total_cases": total,
        "correct_predictions": correct_count,
        "incorrect_predictions": total - correct_count,
        "accuracy": round(correct_count / total, 4),
        "blocked_cases": blocked_count,
        "allowed_cases": allowed_count,
        "error_cases": error_count,
    }

    metrics_path = RESULTS_DIR / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    comparison_path = RESULTS_DIR / "comparison.csv"
    with comparison_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(results[0].keys()),
        )
        writer.writeheader()
        writer.writerows(results)

    print("\nEvaluation results")
    print("------------------")
    print(json.dumps(metrics, indent=2))
    print(f"\nMetrics saved to: {metrics_path}")
    print(f"Comparison saved to: {comparison_path}")


if __name__ == "__main__":
    main()
