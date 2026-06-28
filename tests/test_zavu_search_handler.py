import pytest

import zavu_handlers
from services.people_search import PeopleSearchResult


class FakePeopleSearch:
    def __init__(self, results=None):
        self.results = results or [
            PeopleSearchResult(
                nombre="Maria Perez",
                cedula="12345678",
                fuente="AcopioVE",
            )
        ]

    async def buscar(self, query):
        return self.results

    def formatear_resultado(self, result):
        return f"*{result.nombre}*\nFuente: {result.fuente}"


def make_event(text, chat_id="123"):
    return {
        "type": "message.inbound",
        "data": {
            "messageType": "text",
            "text": text,
            "telegramChatId": chat_id,
            "from": chat_id,
            "content": {},
        },
    }


def make_results(total):
    return [
        PeopleSearchResult(
            nombre=f"Persona {i}",
            cedula=str(10000000 + i),
            fuente="AcopioVE",
        )
        for i in range(1, total + 1)
    ]


@pytest.fixture(autouse=True)
def clear_search_state():
    zavu_handlers._search_results_state.clear()
    yield
    zavu_handlers._search_results_state.clear()


@pytest.mark.asyncio
async def test_realizar_busqueda_uses_people_search(monkeypatch):
    messages = []

    async def fake_send_text(chat_id, text):
        messages.append((chat_id, text))

    monkeypatch.setattr(zavu_handlers, "people_search", FakePeopleSearch())
    monkeypatch.setattr(zavu_handlers, "send_text_async", fake_send_text)

    await zavu_handlers._realizar_busqueda("123", "Maria")

    assert messages[0] == ("123", "Buscando...")
    assert "Resultados para Maria" in messages[1][1]
    assert "AcopioVE" in messages[1][1]


@pytest.mark.asyncio
async def test_realizar_busqueda_stores_remaining_results(monkeypatch):
    messages = []

    async def fake_send_text(chat_id, text):
        messages.append((chat_id, text))

    monkeypatch.setattr(zavu_handlers, "people_search", FakePeopleSearch(make_results(7)))
    monkeypatch.setattr(zavu_handlers, "send_text_async", fake_send_text)

    await zavu_handlers._realizar_busqueda("123", "Maria")

    assert "Mostre 5 de 7 resultados" in messages[1][1]
    assert "Escribe *1* para ver 2 mas" in messages[1][1]
    assert zavu_handlers._search_results_state["123"]["next_index"] == 5


@pytest.mark.asyncio
async def test_search_more_shows_next_page(monkeypatch):
    messages = []
    zavu_handlers._search_results_state["123"] = {
        "query": "Maria",
        "results": make_results(7),
        "next_index": 5,
    }

    async def fake_send_text(chat_id, text):
        messages.append((chat_id, text))

    monkeypatch.setattr(zavu_handlers, "send_text_async", fake_send_text)

    await zavu_handlers.handle_search_more(make_event("1"))

    assert "6. *Persona 6*" in messages[0][1]
    assert "7. *Persona 7*" in messages[0][1]
    assert "Mostre 7 de 7 resultados" in messages[0][1]
    assert zavu_handlers._search_results_state["123"]["next_index"] == 7


@pytest.mark.asyncio
async def test_search_new_clears_state_and_prompts(monkeypatch):
    messages = []
    zavu_handlers._search_results_state["123"] = {
        "query": "Maria",
        "results": make_results(7),
        "next_index": 5,
    }

    async def fake_send_text(chat_id, text):
        messages.append((chat_id, text))

    monkeypatch.setattr(zavu_handlers, "send_text_async", fake_send_text)

    await zavu_handlers.handle_search_new(make_event("2"))

    assert "123" not in zavu_handlers._search_results_state
    assert "nombre o cedula" in messages[0][1]


@pytest.mark.asyncio
async def test_search_menu_clears_state_and_shows_menu(monkeypatch):
    messages = []
    zavu_handlers._search_results_state["123"] = {
        "query": "Maria",
        "results": make_results(7),
        "next_index": 5,
    }

    async def fake_send_text(chat_id, text):
        messages.append((chat_id, text))

    monkeypatch.setattr(zavu_handlers, "send_text_async", fake_send_text)

    await zavu_handlers.handle_search_menu(make_event("3"))

    assert "123" not in zavu_handlers._search_results_state
    assert "BuscaChat" in messages[0][1]


def test_search_results_route_has_priority_for_numeric_menu():
    zavu_handlers._search_results_state["123"] = {
        "query": "Maria",
        "results": make_results(7),
        "next_index": 5,
    }

    assert zavu_handlers.get_search_results_route("123", make_event("1")) == "search:more"
    assert zavu_handlers.get_search_results_route("123", make_event("2")) == "search:new"
    assert zavu_handlers.get_search_results_route("123", make_event("3")) == "search:menu"


@pytest.mark.asyncio
async def test_start_clears_search_state(monkeypatch):
    messages = []
    zavu_handlers._search_results_state["123"] = {
        "query": "Maria",
        "results": make_results(7),
        "next_index": 5,
    }

    async def fake_send_text(chat_id, text):
        messages.append((chat_id, text))

    monkeypatch.setattr(zavu_handlers, "send_text_async", fake_send_text)

    await zavu_handlers.handle_start(make_event("/start"))

    assert "123" not in zavu_handlers._search_results_state
    assert "BuscaChat" in messages[0][1]
