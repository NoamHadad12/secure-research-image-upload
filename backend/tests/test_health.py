from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app(Settings(frontend_origin="http://frontend.test")))


def test_health_returns_stable_success_response() -> None:
    response = make_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_only_the_configured_frontend_origin() -> None:
    client = make_client()
    request_headers = {"Access-Control-Request-Method": "GET"}

    allowed_response = client.options(
        "/health",
        headers={"Origin": "http://frontend.test", **request_headers},
    )
    denied_response = client.options(
        "/health",
        headers={"Origin": "http://untrusted.test", **request_headers},
    )

    assert allowed_response.status_code == 200
    assert allowed_response.headers["access-control-allow-origin"] == "http://frontend.test"
    assert denied_response.status_code == 400
    assert "access-control-allow-origin" not in denied_response.headers


def test_not_found_uses_a_generic_consistent_error_shape() -> None:
    response = make_client().get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Resource not found"}
    }
