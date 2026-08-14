import pytest
from fastapi.testclient import TestClient
from platform_core.server import app, BOT_INSTANCES
from platform_core.modules.builder import ModularBotBuilder, ModularBot
from aiogram import Bot, Dispatcher


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
