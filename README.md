# BuscaChat - Telegram 🤖

Bot de Telegram para reunificación familiar tras el terremoto en Venezuela (Mw 7.2 + 7.5, 24 junio 2026, epicentro Yaracuy).

Parte del hackathon **Build 4 Venezuela**.

[![Tests](https://img.shields.io/badge/tests-84%2F84%20passing-brightgreen)](https://github.com/gfurion/Buscachat-Telegram)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Deploy](https://img.shields.io/badge/deploy-Railway-8B5CF6)](https://buscachat-telegram-production.up.railway.app/health)
[![Zavu](https://img.shields.io/badge/platform-Zavu-6366F1)](https://zavu.dev)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🚀 Funcionalidades

| Comando / Acción | Descripción |
|---|---|
| `/start` | Menú principal con 5 opciones |
| `1` o `/buscar [nombre]` | Buscar personas por nombre o cédula (API externa: 35K registros) |
| `2` o `/registrar desaparecido\|encontrado` | Flujo guiado paso a paso (state machine 5 pasos) |
| `3` o `/refugios [ciudad]` | Centros de ayuda y refugios por ciudad (AcopioVE) |
| `4` o `/emergencia` | Teléfonos de emergencia (AcopioVE) |
| `5` o `/ayuda` | Instrucciones de uso |
| **Enviar foto** | Guarda la URL de la foto en el registro (reconocimiento facial no activo) |
| **HMAC** | Webhook signature verification (bypass activo — Telegram channel secret solo en dashboard Zavu) |

## 🧱 Stack

- **Python 3.11+**
- **FastAPI + uvicorn** — webhook server
- **Zavu** — plataforma de mensajería multi-canal (Telegram webhook)
- **python-telegram-bot** v22+ — handlers originales (conservados, no activos)
- **aiohttp** — cliente HTTP asíncrono
- **SQLite** — base de datos local (MVP)
- **InsightFace / ArcFace** — reconocimiento facial (facerec.py de Venezuela Juntos)
- **Railway** — hosting (webhook FastAPI)
- **pytest + pytest-asyncio** — 84 tests

## 📁 Estructura del proyecto

```
buscachat-telegram/
├── zavu_webhook.py            # FastAPI app + webhook endpoint (activo)
├── zavu_router.py             # Message dispatcher (texto, comandos, menú, fotos)
├── zavu_handlers.py           # Handlers Zavu: start, buscar, ayuda, registrar, fotos
├── zavu_client.py             # Zavudev SDK wrapper (send_text)
├── zavu_state.py              # State machine reportar (nombre→cédula→ubicación→foto→confirmar)
├── main.py                    # Entry point original (python-telegram-bot polling)
├── config.py                  # Settings con validación (30+ vars de entorno)
├── Dockerfile                 # Deploy Railway (CMD uvicorn)
├── services/
│   ├── database.py            # SQLite: personas, embeddings
│   ├── found_people_api.py    # Cliente HTTP → found-people-ve-bot (35K registros)
│   ├── acopiove_api.py        # Cliente HTTP → AcopioVE (refugios, telefonos)
│   ├── reportavnzla_api.py    # Cliente HTTP → ReportaVNZLA (personas estructuradas)
│   ├── face_matching.py       # Wrapper facerec.py (no activo en prod)
│   └── normalizer.py          # Normalización de texto
├── models/
│   └── persona.py             # Persona, TipoReporte
├── lib/
│   └── facerec.py             # ArcFace standalone (Venezuela Juntos, no activo)
└── tests/                     # 84 tests
    ├── test_zavu.py           # 11 tests del router Zavu
    ├── test_zavu_state.py     # 25 tests del state machine
    ├── test_zavu_handlers.py  # 14 tests de handlers Zavu
    ├── test_zavu_webhook.py   # 10 tests de webhook (HMAC, routing)
    ├── test_database.py       # 4 tests DB
    ├── test_found_people_api.py
    ├── test_acopiove.py       # 4 tests AcopioVE
    ├── test_reportavnzla.py   # 6 tests ReportaVNZLA
    └── test_face_matching.py  # 3 tests face matching
```

## 🔧 Setup local

```bash
# 1. Clonar
git clone https://github.com/gfurion/Buscachat-Telegram.git
cd Buscachat-Telegram

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

# 6. Arrancar el bot (modo polling local)
python main.py
```

## 🌐 APIs integradas

| API | Función | Registros | Estado |
|---|---|---|---|
| [found-people-ve-bot](https://github.com/edwinvrgs/found-people-ve-bot) | Búsqueda por nombre/cédula | 35K | ✅ Producción |
| [ReportaVNZLA](https://reportavnzla.com/desarrolladores) | Búsqueda estructurada (nombre, apellido, cédula, edad, ubicación) | 15K+ | ✅ Producción |
| [AcopioVE](https://acopiove.org/docs/api) | Refugios, teléfonos de emergencia | 575 puntos | ✅ Producción |
| [venezuelatebusca.com](https://venezuelatebusca.com) | Registro de desaparecidos | 37K | 🔒 API privada |
| [SOS Venezuela](https://sosvenezuela2026.com) | Personas desaparecidas/localizadas | — | 🔜 Vía AcopioVE

## 🚂 Deploy en Railway

1. Conectá tu repo a [Railway](https://railway.app)
2. Railway detecta automáticamente `Dockerfile` (CMD `uvicorn zavu_webhook:app`)
3. Configurá las variables de entorno desde `.env.example`
4. El webhook de Zavu apunta a `https://buscachat-telegram-production.up.railway.app/webhook`

### Variables de entorno clave

| Variable | Descripción |
|---|---|
| `ZAVU_API_KEY` | API key de Zavu |
| `ZAVU_SENDER_ID` | ID del sender (Bot de Telegram) |
| `ZAVU_WEBHOOK_SECRET` | Secret para firma HMAC-SHA256 |
| `TELEGRAM_BOT_TOKEN` | Token de @BotFather |
| `FOUND_PEOPLE_API_URL` | API externa de búsqueda |

## 📋 Estado del proyecto

| Issue | Descripción | Estado |
|---|---|---|
| BUS-21 | Telegram Bot core | ✅ |
| BUS-22 | Flujo búsqueda por texto | ✅ |
| BUS-23 | Flujo búsqueda por foto | ✅ |
| BUS-24 | Flujo reportar desaparecido | ✅ |
| BUS-25 | Flujo reportar encontrado | ✅ |
| BUS-26 | DB con embeddings | ✅ |
| BUS-27 | Deploy Railway | ✅ Producción |
| BUS-28 | Tests | ✅ 84/84 |
| BUS-29 | Integración Zavu (webhook, menú, handlers, state machine) | ✅ |
| — | AcopioVE (refugios, emergencia) | ✅ |
| — | ReportaVNZLA (búsqueda estructurada) | ✅ |
| — | HMAC signature verification | ⚠️ Bypass |
| 🔜 | Reconocimiento facial (FR-API ReportaVNZLA) | Pendiente API key |
| 🔜 | Búsqueda en DB local | Pendiente |

## 🔄 Flujo Zavu

```
Usuario Telegram → Telegram API → Zavu → Railway (/webhook) → FastAPI → router → handler → Zavu API → Telegram
```

- Webhook recibe `X-Zavu-Signature: t=<ts>,v1=<hmac>` — HMAC en bypass (secret del canal Telegram solo en dashboard)
- Router clasifica: comandos, menú numérico (1-5), texto libre, imágenes
- State machine maneja flujo reportar con 5 pasos (en memoria, TTL implícito vía /start o /cancel)
- Búsqueda combinada: ReportaVNZLA (datos estructurados) + found-people-ve-bot (fallback)
- Fotos se guardan como URL en SQLite — sin procesamiento facial

### Menú principal
```
🔍 1. Buscar persona — por nombre o cédula
📝 2. Registrar persona — desaparecida o encontrada
🏠 3. Refugios cercanos — centros de ayuda
📞 4. Teléfonos de emergencia
🆘 5. Ayuda — cómo funciona el bot
```

---

Build 4 Venezuela · [Dashboard](https://aeterna.red/build4venezuela/) · [Discord](https://build4venezuela.com/discord) · [Bot](https://t.me/BuscaChatVzla_bot)
