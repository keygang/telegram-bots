import pytest
from aiogram import Bot, Dispatcher
from fastapi.testclient import TestClient

from platform_core.modules.builder import ModularBot
from platform_core.server import BOT_INSTANCES, app


@pytest.fixture
def client():
    # Set up mock bot instance in server memory
    bot = Bot(token="123456789:MOCK_TOKEN")
    dp = Dispatcher()
    bot_app = ModularBot(bot=bot, dp=dp, bot_id="test_server_bot", modules=[], commands=[])
    BOT_INSTANCES["test_server_bot"] = bot_app

    with TestClient(app) as test_client:
        yield test_client

    BOT_INSTANCES.pop("test_server_bot", None)


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "test_server_bot" in data["configured_bots"]


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "test_server_bot" in data["bot_ids"]


def test_webhook_nonexistent_bot(client):
    response = client.post("/webhook/unknown_bot_123", json={"update_id": 12345})
    assert response.status_code == 404


def test_webhook_secret_token_missing(client):
    response = client.post("/webhook/test_server_bot", json={"update_id": 12345})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing Telegram secret token"


def test_webhook_secret_token_invalid(client):
    response = client.post(
        "/webhook/test_server_bot",
        json={"update_id": 12345},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing Telegram secret token"


def test_webhook_polling_bot_rejected(client):
    # test_server_bot defaults to 'polling' strategy
    response = client.post(
        "/webhook/test_server_bot",
        json={"update_id": 12345},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_webhook_token_123"},
    )
    assert response.status_code == 400
    assert "configured for polling strategy" in response.json()["detail"]


def test_webhook_valid_token_webhook_strategy(client):
    BOT_INSTANCES["test_server_bot"].strategy = "webhook"
    response = client.post(
        "/webhook/test_server_bot",
        json={"update_id": 12345},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret_webhook_token_123"},
    )
    assert response.status_code == 200
