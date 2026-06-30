# BuscaChat - Telegram 🤖

Bot de Telegram para reunificación familiar tras el terremoto en Venezuela (Mw 7.2 + 7.5, 24 junio 2026, epicentro Yaracuy).

Parte del hackathon **Build 4 Venezuela**.

[![Tests](https://img.shields.io/badge/tests-117%2F117%20passing-brightgreen)](https://github.com/gfurion/Buscachat-Telegram)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Deploy](https://img.shields.io/badge/deploy-Railway-8B5CF6)](https://buscachat-telegram-production.up.railway.app/health)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🚀 Funcionalidades

| Comando / Acción | Descripción |
|---|---|
| `/start` | Menú principal con botones inline (5 opciones: Buscar, Registrar, Refugios, Emergencia, Ayuda) |
| `1` o `/buscar [nombre]` | Buscar personas por nombre o cédula en fuentes agregadas |
| `1` después de buscar | Ver la siguiente página de resultados pendientes |
| `2` después de buscar | Hacer otra búsqueda |
| `3` después de buscar | Volver al menú principal |
| `2` o `/registrar desaparecido\|encontrado` | Flujo guiado paso a paso (state machine) |
| `3` o `/refugios [ciudad]` | Buscar refugios y centros de ayuda |
| `4` o `/emergencia` | Consultar teléfonos de emergencia |
| `5` o `/ayuda` | Instrucciones de uso |

## 🧱 Stack

- **Python 3.11+**
- **FastAPI + uvicorn** — webhook server
- **python-telegram-bot** — cliente Telegram directo (webhooks)
- **aiohttp** — cliente HTTP asíncrono
- **SQLite** — base de datos local (MVP)
- **InsightFace / ArcFace** — reconocimiento facial (facerec.py de Venezuela Juntos)
- **Railway** — hosting (webhook FastAPI)
- **pytest + pytest-asyncio** — 117 tests

## 📁 Estructura del proyecto

```
buscachat-telegram/
├── zavu_webhook.py            # FastAPI app + /webhook/telegram + /health
├── zavu_handlers.py           # Handlers: start, buscar, ayuda, registrar, fotos
├── zavu_state.py              # State machine reportar (nombre→cédula→ubicación→confirmar)
├── telegram_client.py         # Wrapper python-telegram-bot (send_text, send_photo, send_menu_with_buttons, edit_message_text)
├── config.py                  # Settings con validación
├── Dockerfile                 # Deploy Railway (CMD uvicorn)
├── services/
│   ├── database.py            # SQLite: personas, reportes, embeddings, conversation_state
│   ├── found_people_api.py    # Cliente HTTP → found-people-ve-bot
│   ├── acopiove_api.py        # Cliente HTTP → AcopioVE (personas, refugios, teléfonos)
│   ├── people_search.py       # Agregador: búsqueda paralela, normalización, deduplicación
│   ├── face_matching.py       # Wrapper facerec.py (ArcFace)
│   ├── reportavnzla_api.py    # Cliente HTTP → ReportaVNZLA (personas estructuradas)
│   └── normalizer.py          # Normalización de texto
├── models/
│   └── persona.py             # Persona, TipoReporte
├── lib/
│   └── facerec.py             # ArcFace standalone (Venezuela Juntos)
└── tests/                     # 117 tests
    ├── test_zavu_handlers.py  # Tests de handlers
    ├── test_zavu_state.py     # Tests del state machine
    ├── test_zavu_search_handler.py
    ├── test_fase_a.py         # Tests Telegram client, webhook, persistencia
    ├── test_people_search.py
    ├── test_database.py       # Tests DB
    ├── test_found_people_api.py
    ├── test_acopiove.py       # Tests AcopioVE
    ├── test_inline_buttons.py # Tests botones inline
    ├── test_reportavnzla.py   # Tests ReportaVNZLA
    └── test_face_matching.py  # Tests face matching
```

## 🔧 Setup local

```bash
# 1. Clonar
git clone https://github.com/gfurion/Buscachat-Telegram.git
cd Buscachat-Telegram/buscachat-telegram

# 2. Entorno virtual
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env → poner TELEGRAM_BOT_TOKEN=tu_token_de_@BotFather

# 5. Correr tests
python -m pytest tests/ -v

# 6. Arrancar el bot
uvicorn zavu_webhook:app --host 0.0.0.0 --port 8443
```

## 🌐 APIs integradas

| API | Función | Datos | Estado |
|---|---|---|---|
| [ReportaVNZLA](https://reportavnzla.com/desarrolladores) | Búsqueda estructurada por nombre/cédula | 15K+ registros | ✅ Producción |
| [found-people-ve-bot](https://github.com/edwinvrgs/found-people-ve-bot) | Búsqueda por nombre/cédula | 35K+ registros agregados | ✅ Producción |
| [AcopioVE](https://acopiove.org) | Personas, refugios y teléfonos de emergencia | Fuentes agregadas + ayuda | ✅ Producción |
| [Venezuela Juntos](https://github.com/OnBeIt/Venezuela_Juntos_v2) | Reconocimiento facial ArcFace | Código base local | ⚠️ Desactivado |

### Búsqueda por texto

La búsqueda por nombre/cédula usa `PeopleSearchAggregator`:

1. Consulta en paralelo ReportaVNZLA, `found-people-ve-bot` y AcopioVE con `asyncio.gather(..., return_exceptions=True)`.
2. Normaliza las respuestas a `PeopleSearchResult`.
3. Deduplica por cédula cuando existe; si no, por nombre + ubicación.
4. Muestra resultados paginados de 5 en 5.

Después de una búsqueda, el usuario puede escribir:

- `1` — ver la siguiente página de resultados
- `2` — hacer otra búsqueda
- `3` — volver al menú principal

## 🚂 Deploy en Railway

1. Conectá tu repo a [Railway](https://railway.app)
2. Railway detecta automáticamente `Dockerfile` (CMD `uvicorn zavu_webhook:app`)
3. Configurá las variables de entorno:

### Variables de entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token de @BotFather | ✅ |
| `TELEGRAM_ENABLED` | `true` para activar webhook Telegram | ✅ |
| `TELEGRAM_WEBHOOK_SECRET` | Secret para verificar firmas de Telegram | Recomendado |
| `PUBLIC_BASE_URL` | URL pública de tu app (para setWebhook) | ✅ |
| `FOUND_PEOPLE_API_URL` | API externa de búsqueda | ✅ |
| `PORT` | Puerto del servidor (default: 8443) | No |
| `DATA_DIR` | Directorio de datos (default: ./data) | No |
| `FACE_MATCH_THRESHOLD` | Umbral de similitud facial (default: 0.40) | No |
| `FACE_MATCH_ENABLED` | Habilitar búsqueda facial (default: true) | No |
| `LOG_LEVEL` | Nivel de log (default: INFO) | No |

### Activar

```
TELEGRAM_ENABLED=true
PUBLIC_BASE_URL=https://tu-app.up.railway.app
```

### Rollback

```
TELEGRAM_ENABLED=false
```

Instantáneo, sin redeploy.

## 🔄 Flujo

```
Usuario Telegram → Telegram Bot API → Railway (/webhook/telegram) → FastAPI → handler → python-telegram-bot → Telegram
```

- Webhook recibe updates de Telegram con `X-Telegram-Bot-Api-Secret-Token`
- Router clasifica: comandos, menú numérico (1-5), botones inline (btn:), texto libre, imágenes
- Botones inline (btn:) se rutean directamente a HANDLER_MAP con message_id para edit-in-place
- State machine maneja flujo reportar con 4 pasos (nombre→cedula→ubicacion→confirmar)
- Estado temporal de búsqueda guarda resultados pendientes por `chat_id` para paginar con opciones `1`, `2` y `3`
- Búsqueda combinada: ReportaVNZLA + found-people-ve-bot + AcopioVE vía `PeopleSearchAggregator`
- Fotos se guardan como URL en SQLite — búsqueda por foto desactivada temporalmente

### Menú principal (botones inline)
```
🔍 1. Buscar persona → sub-menú: nombre, cédula, foto
📝 2. Registrar persona → sub-menú: desaparecida, encontrada
🏠 3. Refugios cercanos → sub-menú: por ciudad, mapa
📞 4. Teléfonos de emergencia → sub-menú: médica, policial, bomberos
🆘 5. Ayuda → sub-menú: cómo usar, privacidad, contacto
```

## 📋 Estado del proyecto

| Issue | Descripción | Estado |
|---|---|---|
| BUS-21 | Telegram Bot core | ✅ |
| BUS-22 | Flujo búsqueda por texto | ✅ |
| BUS-23 | Flujo búsqueda por foto | ⚠️ Desactivado temporalmente |
| BUS-24 | Flujo reportar desaparecido | ✅ |
| BUS-25 | Flujo reportar encontrado | ✅ |
| BUS-26 | DB con embeddings | ✅ |
| BUS-27 | Deploy Railway | ✅ Producción |
| BUS-28 | Tests | ✅ 117/117 |
| — | Búsqueda multi-fuente con normalización/deduplicación | ✅ |
| — | Paginación de resultados por chat_id | ✅ |
| — | AcopioVE (refugios, emergencia) | ✅ |
| — | ReportaVNZLA (búsqueda estructurada) | ✅ |
| — | FSM persistente a SQLite | ✅ |
| — | Migración Zavu → Telegram directo | ✅ |
| — | Botones inline nativos | ✅ |
| 🔜 | Reconocimiento facial (FR-API ReportaVNZLA) | Pendiente API key |

---

Build 4 Venezuela · [Dashboard](https://aeterna.red/build4venezuela/) · [Discord](https://build4venezuela.com/discord) · [Bot](https://t.me/BuscaChatVzla_bot)
