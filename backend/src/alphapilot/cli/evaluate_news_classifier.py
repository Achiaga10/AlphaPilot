from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.core.config import settings
from alphapilot.news.classifier import HostedNewsClassifier
from alphapilot.news.models import (
    ClassificationStatus,
    NewsImpact,
    NewsSeverity,
    NormalizedNewsArticle,
)
from alphapilot.news.policy import hard_event_confirmation, source_confidence


async def evaluate(path: Path) -> dict[str, Any]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    classifier = HostedNewsClassifier(settings)
    event_correct = impact_correct = severity_reasonable = failures = unknowns = 0
    latencies: list[float] = []
    results: list[dict[str, Any]] = []
    for case in cases:
        now = datetime.now(UTC)
        article = NormalizedNewsArticle(
            ticker="TEST",
            company_name="Controlled Test Company",
            provider="CONTROLLED_EVALUATION",
            provider_article_id=case["id"],
            canonical_url=None,
            headline=case["headline"],
            summary=case["summary"],
            source=case.get("source", "Reuters"),
            published_at=now,
            received_at=now,
        )
        started = time.perf_counter()
        attempt = await classifier.classify(article)
        latency = time.perf_counter() - started
        latencies.append(latency)
        output = attempt.output
        if attempt.status is not ClassificationStatus.CLASSIFIED or output is None:
            failures += 1
            hard_exit_eligible = False
        else:
            event_correct += output.event_type.value == case["event_type"]
            impact_correct += output.impact.value == case["impact"]
            severity_reasonable += output.severity.value in case["severity"]
            unknowns += (
                output.event_type.value == "UNKNOWN"
                or output.impact.value == "UNKNOWN"
                or output.severity.value == "UNKNOWN"
            )
            hard_exit_eligible = (
                output.impact is NewsImpact.NEGATIVE
                and output.severity is NewsSeverity.SEVERE
                and output.confidence >= 0.90
                and hard_event_confirmation(
                    event_type=output.event_type,
                    headline=case["headline"],
                    summary=case["summary"],
                    source=source_confidence(
                        case.get("source", "Reuters"),
                        company_name="Controlled Test Company",
                    ),
                )
            )
        results.append(
            {
                "id": case["id"],
                "status": attempt.status.value,
                "latency_seconds": round(latency, 3),
                "classification": output.model_dump(mode="json") if output else None,
                "failure_code": attempt.failure_code,
                "hard_exit_eligible": hard_exit_eligible,
                "expected_hard_exit_eligible": case.get("eligible_for_hard_exit_evidence"),
            }
        )
    count = len(cases)
    safety_cases = [item for item in results if item["expected_hard_exit_eligible"] is not None]
    unsupported_exits = sum(
        bool(item["hard_exit_eligible"]) and not bool(item["expected_hard_exit_eligible"])
        for item in safety_cases
    )
    supported_exits = sum(
        bool(item["hard_exit_eligible"]) and bool(item["expected_hard_exit_eligible"])
        for item in safety_cases
    )
    return {
        "provider": "GOOGLE_GEMINI",
        "model": settings.NEWS_AI_CLASSIFIER_MODEL,
        "evaluation_version": "financial-news-controlled-v1",
        "cases": count,
        "event_type_accuracy": event_correct / count,
        "impact_accuracy": impact_correct / count,
        "severity_reasonableness": severity_reasonable / count,
        "structured_output_failures": failures,
        "unknown_results": unknowns,
        "average_latency_seconds": sum(latencies) / count,
        "unsupported_exit_required_count": unsupported_exits,
        "supported_hard_exit_count": supported_exits,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(evaluate(args.fixture)), indent=2))


if __name__ == "__main__":
    main()
