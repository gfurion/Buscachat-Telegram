import pytest
import hmac
import hashlib
import json
import time

from fastapi.testclient import TestClient

from config import Config


@pytest.fixture
def client():
    from zavu_webhook import app
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestHMAC:
    def make_signature(self, body: dict, secret: str = None) -> str:
        if secret is None:
            secret = Config.ZAVU_WEBHOOK_SECRET
        payload = json.dumps(body)
        ts = str(int(time.time()))
        sig = hmac.new(
            secret.encode(),
            f"{ts}.{payload}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={sig}"

    def test_missing_signature_processed(self, client):
        payload = {
            "id": "test_no_sig",
            "type": "message.inbound",
            "data": {
                "messageType": "text",
                "text": "/start",
                "channel": "telegram",
                "telegramChatId": "123",
            },
        }
        resp = client.post("/webhook", json=payload)
        # Debug mode processes even with invalid signature
        assert resp.status_code == 200

    def test_valid_signature_processed(self, client):
        payload = {
            "id": "test_valid",
            "type": "message.inbound",
            "data": {
                "messageType": "text",
                "text": "/start",
                "channel": "telegram",
                "telegramChatId": "123",
            },
        }
        sig = self.make_signature(payload)
        resp = client.post(
            "/webhook",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Zavu-Signature": sig,
            },
        )
        assert resp.status_code == 200

    def test_invalid_signature_processed_debug(self, client):
        payload = {
            "id": "test_bad",
            "type": "message.inbound",
            "data": {
                "messageType": "text",
                "text": "/start",
                "channel": "telegram",
                "telegramChatId": "123",
            },
        }
        sig = self.make_signature(payload, secret="wrong_secret_key")
        resp = client.post(
            "/webhook",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Zavu-Signature": sig,
            },
        )
        # Debug mode: all webhooks processed
        assert resp.status_code == 200


class TestRouting:
    def make_event(self, **kwargs) -> dict:
        data = {
            "messageType": kwargs.get("message_type", "text"),
            "text": kwargs.get("text", ""),
            "channel": "telegram",
            "telegramChatId": "123",
        }
        if "button_id" in kwargs:
            data["content"] = {"interactiveReply": {"id": kwargs["button_id"]}}
        return {
            "id": f"test_{int(time.time())}",
            "type": "message.inbound",
            "data": data,
        }

    def request(self, client, event: dict) -> dict:
        sig_header = ""
        if Config.ZAVU_WEBHOOK_SECRET:
            payload = json.dumps(event)
            ts = str(int(time.time()))
            sig = hmac.new(
                Config.ZAVU_WEBHOOK_SECRET.encode(),
                f"{ts}.{payload}".encode(),
                hashlib.sha256,
            ).hexdigest()
            sig_header = f"t={ts},v1={sig}"

        return client.post(
            "/webhook",
            data=json.dumps(event),
            headers={
                "Content-Type": "application/json",
                "X-Zavu-Signature": sig_header,
            },
        )

    def test_start_routing(self, client):
        event = self.make_event(text="/start")
        resp = self.request(client, event)
        assert resp.status_code == 200

    def test_buscar_routing(self, client):
        event = self.make_event(text="/buscar Maria")
        resp = self.request(client, event)
        assert resp.status_code == 200

    def test_registrar_routing(self, client):
        event = self.make_event(text="/registrar desaparecido")
        resp = self.request(client, event)
        assert resp.status_code == 200

    def test_emergencia_routing(self, client):
        event = self.make_event(text="/emergencia")
        resp = self.request(client, event)
        assert resp.status_code == 200

    def test_refugios_routing(self, client):
        event = self.make_event(text="/refugios")
        resp = self.request(client, event)
        assert resp.status_code == 200

    def test_image_routing(self, client):
        event = self.make_event(message_type="image")
        resp = self.request(client, event)
        assert resp.status_code == 200

    def test_unhandled_event_type_ignored(self, client):
        event = {
            "id": f"unk_{int(time.time())}",
            "type": "other.event",
            "data": {},
        }
        resp = self.request(client, event)
        assert resp.json()["status"] == "ignored"

    def test_duplicate_event_ignored(self, client):
        event = self.make_event(text="/start")
        event["id"] = "duplicate_test_id"
        resp1 = self.request(client, event)
        assert resp1.status_code == 200 and resp1.json()["status"] == "ok"
        resp2 = self.request(client, event)
        assert resp2.status_code == 200 and resp2.json()["status"] == "duplicate"
