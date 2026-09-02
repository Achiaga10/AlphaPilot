import json
from pathlib import Path

from alphapilot.news.models import NewsEventType
from alphapilot.news.policy import hard_event_confirmation, source_confidence

FIXTURE = Path(__file__).parent / "fixtures" / "financial_news_exit_safety_v1.json"


def test_exit_safety_fixture_is_frozen_complete_and_has_no_unsupported_confirmation() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(cases) == 30
    assert all(
        {"event_type", "impact", "severity", "eligible_for_hard_exit_evidence"} <= case.keys()
        for case in cases
    )
    unsupported = []
    supported = []
    for case in cases:
        confirmed = hard_event_confirmation(
            event_type=NewsEventType(case["event_type"]),
            headline=case["headline"],
            summary=case["summary"],
            source=source_confidence(case["source"], company_name="Controlled Test Company"),
        )
        if confirmed and not case["eligible_for_hard_exit_evidence"]:
            unsupported.append(case["id"])
        if confirmed and case["eligible_for_hard_exit_evidence"]:
            supported.append(case["id"])
    assert unsupported == []
    assert len(supported) == 6
