# -----------------------------------------------------------------------------
# tests/backend/integration/test_discovery_endpoints.py
#
# AI-DISC-002 / AI-DISC-003 — Partner discovery endpoint integration tests.
#
# Covers:
#   - POST /admin/discovery/candidates with a JSON array inserts records and
#     returns results sorted by potential_score descending.
#   - Each returned record has id, candidate_name, potential_score, score_factors,
#     status="new", and geographic_data populated.
#   - POST with an empty candidates array returns 201 with an empty list.
#   - PATCH /admin/discovery/candidates/{id} with status=invited succeeds.
#   - PATCH with status=dismissed succeeds.
#   - PATCH on a nonexistent candidate returns 404.
#   - Non-admin (partner role) receives 403 on both endpoints.
#
# PartnerDiscovery uses sentence_transformers which is not installed in the
# test environment (it's in requirements-ml.txt). The service degrades
# gracefully — potential_score = 0.0 and score_factors still contains the
# default factor structure. Tests assert on structure, not exact scores.
# -----------------------------------------------------------------------------

import uuid

from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CANDIDATES = [
    {
        "business_name": "Acme Fitness",
        "category": "health",
        "description": "Online fitness coaching and nutrition plans",
        "city": "Austin",
        "country": "US",
    },
    {
        "business_name": "TechGadgets Hub",
        "category": "technology",
        "description": "Consumer electronics and smart home devices",
        "city": "San Francisco",
        "country": "US",
    },
]


async def _admin_headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.referrai", "password": "x"},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _partner_headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "partner@test.referrai", "password": "x"},
    )
    assert resp.status_code == 200, f"Partner login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# POST /admin/discovery/candidates
# ---------------------------------------------------------------------------

async def test_score_candidates_returns_201_with_records(
    client: AsyncClient, seed: dict
) -> None:
    """POST with sample candidates returns 201 and one record per candidate."""
    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/admin/discovery/candidates",
        json={"candidates": _SAMPLE_CANDIDATES},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body) == len(_SAMPLE_CANDIDATES)


async def test_score_candidates_records_have_expected_fields(
    client: AsyncClient, seed: dict
) -> None:
    """Each returned record has id, candidate_name, potential_score, status, score_factors."""
    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/admin/discovery/candidates",
        json={"candidates": [_SAMPLE_CANDIDATES[0]]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    record = resp.json()[0]
    assert record["candidate_name"] == "Acme Fitness"
    assert record["status"] == "new"
    assert "potential_score" in record
    assert "score_factors" in record
    assert "id" in record
    assert record["geographic_data"]["city"] == "Austin"
    assert record["geographic_data"]["country"] == "US"


async def test_score_candidates_returns_score_factors_dict(
    client: AsyncClient, seed: dict
) -> None:
    """score_factors contains the three sub-score keys regardless of model availability."""
    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/admin/discovery/candidates",
        json={"candidates": [_SAMPLE_CANDIDATES[0]]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    factors = resp.json()[0]["score_factors"]
    assert factors is not None
    assert "similarity" in factors
    assert "category_match" in factors
    assert "geographic" in factors


async def test_score_candidates_sorted_by_score_descending(
    client: AsyncClient, seed: dict
) -> None:
    """When multiple candidates are submitted the results are sorted score desc."""
    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/admin/discovery/candidates",
        json={"candidates": _SAMPLE_CANDIDATES},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    scores = [r["potential_score"] for r in resp.json() if r["potential_score"] is not None]
    assert scores == sorted(scores, reverse=True)


async def test_score_candidates_empty_array_returns_empty_list(
    client: AsyncClient, seed: dict
) -> None:
    """POST with an empty candidates array returns 201 with an empty list."""
    headers = await _admin_headers(client)
    resp = await client.post(
        "/api/v1/admin/discovery/candidates",
        json={"candidates": []},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json() == []


# ---------------------------------------------------------------------------
# PATCH /admin/discovery/candidates/{id}
# ---------------------------------------------------------------------------

async def _post_one_candidate(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/admin/discovery/candidates",
        json={"candidates": [_SAMPLE_CANDIDATES[0]]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()[0]["id"]


async def test_patch_candidate_invited(client: AsyncClient, seed: dict) -> None:
    """PATCH with status=invited transitions the record to invited."""
    headers = await _admin_headers(client)
    cid = await _post_one_candidate(client, headers)
    resp = await client.patch(
        f"/api/v1/admin/discovery/candidates/{cid}",
        json={"status": "invited"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "invited"


async def test_patch_candidate_dismissed(client: AsyncClient, seed: dict) -> None:
    """PATCH with status=dismissed transitions the record to dismissed."""
    headers = await _admin_headers(client)
    cid = await _post_one_candidate(client, headers)
    resp = await client.patch(
        f"/api/v1/admin/discovery/candidates/{cid}",
        json={"status": "dismissed"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "dismissed"


async def test_patch_nonexistent_candidate_returns_404(
    client: AsyncClient, seed: dict
) -> None:
    """PATCH on an ID that does not exist returns 404."""
    headers = await _admin_headers(client)
    resp = await client.patch(
        f"/api/v1/admin/discovery/candidates/{uuid.uuid4()}",
        json={"status": "invited"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# RBAC — partner role must be rejected on both endpoints
# ---------------------------------------------------------------------------

async def test_score_candidates_partner_gets_403(
    client: AsyncClient, seed: dict
) -> None:
    """Non-admin (partner role) receives 403 on POST /admin/discovery/candidates."""
    headers = await _partner_headers(client)
    resp = await client.post(
        "/api/v1/admin/discovery/candidates",
        json={"candidates": [_SAMPLE_CANDIDATES[0]]},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


async def test_patch_candidate_partner_gets_403(
    client: AsyncClient, seed: dict
) -> None:
    """Non-admin (partner role) receives 403 on PATCH /admin/discovery/candidates/{id}."""
    headers = await _partner_headers(client)
    resp = await client.patch(
        f"/api/v1/admin/discovery/candidates/{uuid.uuid4()}",
        json={"status": "invited"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
