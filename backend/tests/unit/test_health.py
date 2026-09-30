from unittest.mock import AsyncMock, patch


@patch("app.api.routes.health._check_db", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_rabbitmq", new_callable=AsyncMock, return_value="ok")
async def test_health_all_ok(mock_rmq, mock_redis, mock_db, client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["dependencies"]["database"] == "ok"
    assert data["dependencies"]["redis"] == "ok"
    assert data["dependencies"]["rabbitmq"] == "ok"


@patch("app.api.routes.health._check_db", new_callable=AsyncMock, return_value="unavailable")
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_rabbitmq", new_callable=AsyncMock, return_value="ok")
async def test_health_db_down_returns_503(mock_rmq, mock_redis, mock_db, client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["dependencies"]["database"] == "unavailable"


@patch("app.api.routes.health._check_db", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_rabbitmq", new_callable=AsyncMock, return_value="ok")
async def test_readiness_returns_same_as_health(mock_rmq, mock_redis, mock_db, client):
    response = await client.get("/api/v1/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
