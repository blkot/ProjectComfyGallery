from httpx import ASGITransport, AsyncClient

from comfy_gallery_api.main import app


async def test_liveness_does_not_require_external_services() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "comfy-gallery-api",
        "version": "0.1.0-rc.5",
        "checks": {},
    }
    assert response.headers["X-Request-ID"]


async def test_framework_errors_use_the_stable_envelope() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        invalid = await client.post("/api/v1/auth/login", json={})
        missing = await client.get("/not-a-route")

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert invalid.json()["error"]["request_id"]
    issues = invalid.json()["error"]["details"]["issues"]
    assert {issue["path"] for issue in issues} == {"body.password", "body.username"}
    assert all("input" not in issue for issue in issues)

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "HTTP_404"
    assert missing.json()["error"]["request_id"]
