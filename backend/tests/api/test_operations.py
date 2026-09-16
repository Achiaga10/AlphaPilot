from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_operations_api_evaluate_list_detail_acknowledge_and_filters(client) -> None:
    evaluated = await client.post("/api/v1/operations/evaluate")
    assert evaluated.status_code == 200
    assert evaluated.json()["opened"] >= 1

    listed = await client.get("/api/v1/operations/incidents?severity=INFO&source=BROKER")
    assert listed.status_code == 200
    disabled = next(
        item for item in listed.json() if item["incident_type"] == "BROKER_SYNC_DISABLED"
    )
    incident_id = disabled["id"]

    detail = await client.get(f"/api/v1/operations/incidents/{incident_id}")
    assert detail.status_code == 200
    assert detail.json()["events"][0]["event_type"] == "OPENED"

    acknowledged = await client.post(
        f"/api/v1/operations/incidents/{incident_id}/acknowledge",
        json={"reason": "Expected local configuration"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"

    health = await client.get("/api/v1/operations/health")
    assert health.status_code == 200
    assert health.json()["overall_health"] == "HEALTHY"
    assert health.json()["info_count"] >= 1
    assert health.json()["startup"]["schema_compatible"] is True

    summary = await client.get("/api/v1/operations/daily-summary")
    assert summary.status_code == 200
    assert summary.json()["broker"]["status"] == "DISABLED"


@pytest.mark.asyncio
async def test_operations_api_rejects_invalid_filters_and_has_no_delete(client) -> None:
    invalid = await client.get("/api/v1/operations/incidents?severity=EMERGENCY")
    assert invalid.status_code == 422
    missing = await client.get("/api/v1/operations/incidents/10000000-0000-4000-8000-000000000099")
    assert missing.status_code == 404
    deleted = await client.delete(
        "/api/v1/operations/incidents/10000000-0000-4000-8000-000000000099"
    )
    assert deleted.status_code == 405
