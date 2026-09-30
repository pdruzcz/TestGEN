from unittest.mock import AsyncMock, patch


@patch("app.api.routes.health._check_db", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_rabbitmq", new_callable=AsyncMock, return_value="ok")
async def test_request_id_middleware_generates_id(mock_rmq, mock_redis, mock_db, client):
    response = await client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@patch("app.api.routes.health._check_db", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_rabbitmq", new_callable=AsyncMock, return_value="ok")
async def test_request_id_middleware_preserves_client_id(mock_rmq, mock_redis, mock_db, client):
    custom_id = "test-request-id-12345"
    response = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": custom_id},
    )
    assert response.headers["X-Request-ID"] == custom_id


@patch("app.api.routes.health._check_db", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value="ok")
@patch("app.api.routes.health._check_rabbitmq", new_callable=AsyncMock, return_value="ok")
async def test_process_time_header_is_duration(mock_rmq, mock_redis, mock_db, client):
    response = await client.get("/api/v1/health")
    assert "X-Process-Time" in response.headers
    process_time = float(response.headers["X-Process-Time"])
    # Duration should be a small positive number (not an absolute perf_counter timestamp)
    assert 0 < process_time < 10
