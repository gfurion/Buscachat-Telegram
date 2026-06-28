import pytest
from zavu_router import route_event


def make_event(message_type="text", text="", button_id=None, channel="telegram"):
    event = {
        "id": "evt_test_001",
        "type": "message.inbound",
        "timestamp": 1705312200000,
        "senderId": "snd_test",
        "projectId": "prj_test",
        "data": {
            "messageId": "msg_test",
            "from": "123456789",
            "to": "+15551234567",
            "channel": channel,
            "messageType": message_type,
            "text": text,
            "content": {},
        },
    }
    if button_id:
        event["data"]["content"]["interactiveReply"] = {
            "type": "button_reply",
            "id": button_id,
            "title": "Test",
        }
    return event


class TestRouter:
    def test_start_command(self):
        event = make_event(text="/start")
        assert route_event(event) == "start"

    def test_buscar_command(self):
        event = make_event(text="/buscar Maria Perez")
        assert route_event(event) == "buscar"

    def test_ayuda_command(self):
        event = make_event(text="/ayuda")
        assert route_event(event) == "ayuda"

    def test_info_command(self):
        event = make_event(text="/info")
        assert route_event(event) == "info"

    def test_free_text_valid(self):
        event = make_event(text="Maria")
        assert route_event(event) == "free_text"

    def test_free_text_too_short(self):
        event = make_event(text="M")
        assert route_event(event) is None

    def test_button_buscar(self):
        event = make_event(button_id="buscar")
        assert route_event(event) == "button:buscar"

    def test_button_menu(self):
        event = make_event(button_id="menu")
        assert route_event(event) == "button:menu"

    def test_button_ayuda(self):
        event = make_event(button_id="ayuda")
        assert route_event(event) == "button:ayuda"

    def test_button_registrar(self):
        event = make_event(button_id="menu:registrar")
        assert route_event(event) == "button:menu:registrar"

    def test_image_not_handled_yet(self):
        event = make_event(message_type="image")
        assert route_event(event) == "photo"

    def test_unknown_command(self):
        event = make_event(text="/unknown")
        assert route_event(event) is None

    def test_empty_text(self):
        event = make_event(text="")
        assert route_event(event) is None

    def test_buscar_command_no_query(self):
        event = make_event(text="/buscar")
        assert route_event(event) == "buscar"
