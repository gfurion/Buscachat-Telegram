# BuscaChat - Telegram 🤖

Bot de Telegram para reunificación familiar tras el terremoto en Venezuela (Mw 7.2 + 7.5, 24 junio 2026, epicentro Yaracuy).

Parte del hackathon **Build 4 Venezuela**.

[![Tests](https://img.shields.io/badge/tests-132%2F132%20passing-brightgreen)](https://github.com/gfurion/Buscachat-Telegram)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Deploy](https://img.shields.io/badge/deploy-Railway-8B5CF6)](https://buscachat-telegram-production.up.railway.app/health)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🚀 Funcionalidades

| Acción | Descripción |
|--------|-------------|
| Menú principal | Botones inline con 5 opciones: Buscar, Registrar, Refugios, Emergencia, Ayuda |
| `/start` | Menú principal |
| `/buscar [nombre]` | Buscar personas por nombre o cédula en 4 fuentes simultáneas |
| `/registrar` | Reportar persona desaparecida o encontrada (5 pasos guiados) |
| `/refugios [ciudad]` | Buscar refugios y centros de ayuda |
| `/emergencia` | Consultar teléfonos de emergencia |
| `/ayuda` | Instrucciones de uso y contacto |
| Paginación `1` `2` `3` | Avanzar / Nueva búsqueda / Volver al menú |

## 🧱 Stack

- **Python 3.11+** (3.14.5 local, 3.11 Dockerfile Railway)
- **FastAPI + uvicorn** — webhook server
- **python-telegram-bot 22.8** — cliente Telegram directo (webhooks)
- **httpx + aiohttp** — clientes HTTP asíncronos
- **SQLite** — base de datos (personas, embeddings, conversation_state)
- **InsightFace / ArcFace** — reconocimiento facial (facerec.py de Venezuela Juntos)
- **Railway** — hosting (webhook FastAPI)
- **pytest + pytest-asyncio** — 132 tests

## 📁 Estructura del proyecto

```
buscachat-telegram/
├── zavu_webhook.py            # FastAPI app + /webhook/telegram + /health
├── zavu_handlers.py           # Handlers: start, buscar, registrar, refugios, emergencia, ayuda
├── zavu_state.py              # State machine (5 pasos: nombre→cédula→ubicación→foto→confirmar)
├── telegram_client.py         # Wrapper python-telegram-bot (send_text, send_photo, send_menu_with_buttons, edit_message_text, edit_message_reply_markup)
├── config.py                  # Settings con validación
├── Dockerfile                 # Deploy Railway (CMD uvicorn)
├── services/
│   ├── database.py            # SQLite: personas, embeddings, conversation_state
│   ├── found_people_api.py    # Cliente HTTP → found-people-ve-bot
│   ├── acopiove_api.py        # Cliente HTTP → AcopioVE (personas, refugios, teléfonos)
│   ├── people_search.py       # Agregador 4 fuentes paralelas + dedup + paginación
│   ├── face_matching.py       # Wrapper facerec.py (ArcFace)
│   ├── reportavnzla_api.py    # Cliente HTTP → ReportaVNZLA (personas estructuradas)
│   └── normalizer.py          # Normalización de texto
├── models/
│   └── persona.py             # Persona, TipoReporte
├── lib/
│   └── facerec.py             # ArcFace standalone (Venezuela Juntos)
└── tests/                     # 132 tests
    ├── test_zavu_handlers.py  # Tests de handlers (inicio, registro, búsqueda, foto)
    ├── test_zavu_state.py     # Tests del state machine (25 tests)
    ├── test_zavu_search_handler.py # Tests de paginación
    ├── test_fase_a.py         # Tests Telegram client, webhook, persistencia
    ├── test_inline_buttons.py # Tests botones inline (36 tests)
    ├── test_people_search.py  # Tests del agregador multi-fuente
    ├── test_database.py       # Tests DB
    ├── test_found_people_api.py
    ├── test_acopiove.py       # Tests AcopioVE
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
# Editar .env → poner TELEGRAM_BOT_TOKEN de @BotFather

# 5. Correr tests
python -m pytest tests/ -v

# 6. Arrancar el bot
uvicorn zavu_webhook:app --host 0.0.0.0 --port 8443
```

## 🌐 APIs integradas

| API | Función | Datos | Estado |
|-----|---------|-------|--------|
| ReportaVNZLA | Búsqueda estructurada por nombre/cédula | 15K+ registros | ✅ Producción |
| found-people-ve-bot | Búsqueda por nombre/cédula | 35K+ registros | ✅ Producción |
| AcopioVE | Personas, refugios, teléfonos emergencia | Fuentes agregadas | ✅ Producción |
| DB local | Búsqueda en SQLite (reportes registrados) | Datos propios | ✅ Producción |
| Venezuela Juntos | Reconocimiento facial ArcFace | Código base local | ⚠️ Sin uso activo |

### Búsqueda multi-fuente

`PeopleSearchAggregator` consulta las 4 fuentes en paralelo con `asyncio.gather(return_exceptions=True)`:

1. ReportaVNZLA + found-people-ve-bot + AcopioVE + DB local simultáneamente
2. Normaliza respuestas a `PeopleSearchResult` unificado
3. Deduplica por cédula; si no hay cédula, por nombre + ubicación
4. Muestra resultados paginados de 5 en 5

Después de una búsqueda:
- `1` — siguiente página
- `2` — nueva búsqueda
- `3` — volver al menú

## 📸 Registro con foto opcional

El flujo de reportar persona tiene 5 pasos guiados:

```
1. Nombre completo
2. Cédula (o /skip)
3. Ubicación (o /skip)
4. Foto (opcional — enviar foto o /skip)
5. Confirmar (escribir "Confirmar" o "Cancelar")
```

En el paso **Foto**:
- El usuario puede enviar una foto de la persona
- Se descarga con timeout de 30s y se guarda localmente en `data/fotos/`
- Se extrae embedding facial con ArcFace (para futura búsqueda por foto)
- O puede escribir `/skip` para omitir

## 🐛 Correcciones 2026-06-30

Se corrigieron bugs que afectaban la experiencia de usuario:

| Bug | Síntoma | Causa raíz |
|-----|---------|------------|
| **Event loop cerrado** | Mensajes sin respuesta cada 2 intentos, fotos no descargaban | `asyncio.to_thread` → `asyncio.run()` cerraba el event loop; `httpx.AsyncClient` quedaba inválido |
| **Markdown injection** | Nombres con `*`, `_`, `` ` `` rompían el mensaje | Input del usuario sin escapar dentro de `*text*` en respuestas |
| **File_id filtrado** | Foto en paso incorrecto se guardaba como nombre/cédula | `text` se reemplazaba con file_id sin verificar el paso actual del FSM |
| **Registro trabado** | Usuario escribía texto y caía a búsqueda en vez de avanzar | `_registrar_waiting.pop()` consumía el flag antes de validar |
| **Ruteo foto** | Subir foto en paso FOTO no respondía | `elif message.get("photo")` atrapaba la foto antes de llegar a `photo:report` |

**Tests:** 117 → 132 (15 nuevos tests específicos para paso FOTO y ruteo de fotos).

## 🚂 Deploy en Railway

1. Conectá el repo a [Railway](https://railway.app)
2. Railway detecta automáticamente `Dockerfile` (CMD `uvicorn zavu_webhook:app`)
3. Configurá las variables de entorno:

### Variables de entorno

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `TELEGRAM_BOT_TOKEN` | Token de @BotFather | ✅ |
| `TELEGRAM_ENABLED` | `true` para activar webhook Telegram | ✅ |
| `TELEGRAM_WEBHOOK_SECRET` | Secret para verificar firmas de Telegram | Recomendado |
| `PUBLIC_BASE_URL` | URL pública de la app (para setWebhook) | ✅ |
| `FOUND_PEOPLE_API_URL` | API externa de búsqueda | ✅ |
| `PORT` | Puerto del servidor (default: 8443) | No |
| `DATA_DIR` | Directorio de datos (default: ./data) | No |
| `FACE_MATCH_THRESHOLD` | Umbral de similitud facial (default: 0.40) | No |
| `FACE_MATCH_ENABLED` | Habilitar búsqueda facial (default: true) | No |
| `LOG_LEVEL` | Nivel de log (default: INFO) | No |

### Activar / Desactivar

```
TELEGRAM_ENABLED=true   → Bot activo
TELEGRAM_ENABLED=false  → Bot desactivado (rollback instantáneo, sin redeploy)
```

## 🔄 Flujo de webhook

```
Usuario → Telegram API → Railway (/webhook/telegram) → FastAPI → handler → python-telegram-bot → Telegram
```

- Webhook verifica `X-Telegram-Bot-Api-Secret-Token`
- Router prioriza: callbacks con btn: > FSM activo > foto sin FSM > ruteo por texto
- Botones inline (btn:) se rutean directamente a HANDLER_MAP con message_id para edit-in-place
- State machine persiste a SQLite (sobrevive deploys y reinicios)
- Estado de búsqueda guarda resultados pendientes por chat_id
- Fotos se guardan localmente + file_id en DB (recuperables desde Telegram)

### Menú principal (botones inline)

```
🔍 Buscar persona      → nombre / cédula / foto
📝 Registrar persona   → desaparecido / encontrado
🏠 Refugios cercanos   → por ciudad / mapa
📞 Teléfonos emergencia → médica / policial / bomberos
🆘 Ayuda               → cómo usar / privacidad / contacto
```

Todos los sub-menús incluyen botón **🔙 Volver al menú**.

## 📋 Estado del proyecto

| Feature | Estado |
|---------|--------|
| Bot Telegram core (webhook, routing) | ✅ |
| Búsqueda por texto (4 fuentes paralelas) | ✅ |
| Búsqueda por foto | ⏳ Pendiente API key FR-API |
| Reportar desaparecido (5 pasos guiados) | ✅ |
| Reportar encontrado | ✅ |
| Foto opcional en registro | ✅ |
| Refugios y emergencia (AcopioVE) | ✅ |
| Botones inline con sub-menús | ✅ |
| Paginación de resultados | ✅ |
| DB SQLite con embeddings | ✅ |
| Deploy Railway | ✅ Producción |
| Tests | ✅ 132/132 |

### Pendiente

- Reconocimiento facial (FR-API ReportaVNZLA, requiere API key)
- Migración SQLite → PostgreSQL
- Búsqueda por foto funcional

---

**Bot en producción:** [@BuscaChatVzla_bot](https://t.me/BuscaChatVzla_bot)

Build 4 Venezuela · [Dashboard](https://aeterna.red/build4venezuela/) · [Discord](https://build4venezuela.com/discord)
