# BuscaChat - Telegram 🤖

Bot de Telegram para reunificación familiar tras el terremoto en Venezuela (Mw 7.2 + 7.5, 24 junio 2026, epicentro Yaracuy).

Parte del hackathon **Build 4 Venezuela**.

[![Tests](https://img.shields.io/badge/tests-17%2F17%20passing-brightgreen)](https://github.com/gfurion/Buscachat-Telegram)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🚀 Funcionalidades

| Comando / Acción | Descripción |
|---|---|
| `/start` | Menú principal con 3 opciones |
| `/buscar [nombre o cédula]` | Buscar personas vía API externa |
| **Enviar foto** | Búsqueda por reconocimiento facial (InsightFace/ArcFace) |
| **Registrar desaparecido** | Flujo guiado: nombre → cédula → ubicación → foto → confirmar |
| **Registrar encontrado** | Mismo flujo, tipo ENCONTRADO |

## 🧱 Stack

- **Python 3.11+**
- **python-telegram-bot** v22+ — framework del bot
- **aiohttp** — cliente HTTP asíncrono
- **SQLite** — base de datos local (MVP)
- **InsightFace / ArcFace** — reconocimiento facial (facerec.py de Venezuela Juntos)
- **Railway** — hosting (webhook)
- **pytest + pytest-asyncio** — 17 tests

## 📁 Estructura del proyecto

```
buscachat-telegram/
├── main.py                    # Entry point: webhook o polling
├── config.py                  # Settings con validación (12 vars de entorno)
├── Dockerfile                 # Deploy Railway
├── railway.toml               # Config Railway
├── handlers/
│   ├── start.py               # /start, menú inline, ayuda
│   ├── buscar.py              # /buscar + foto directa + texto libre
│   ├── reportar.py            # ConversationHandler 5 pasos
│   └── errores.py             # Error handler global
├── services/
│   ├── database.py            # SQLite: personas, reportes, embeddings
│   ├── found_people_api.py    # Cliente HTTP → found-people-ve-bot
│   ├── face_matching.py       # Wrapper facerec.py
│   └── normalizer.py          # Normalización de texto
├── models/
│   └── persona.py             # Persona, Reporte, TipoReporte
├── keyboards/
│   └── teclados.py            # Menús inline de Telegram
├── lib/
│   └── facerec.py             # ArcFace standalone (Venezuela Juntos)
└── tests/                     # 17 tests
    ├── test_database.py
    ├── test_found_people_api.py
    ├── test_face_matching.py
    ├── test_start.py
    ├── test_buscar.py
    └── test_reportar.py
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

| API | Función | Estado |
|---|---|---|
| [found-people-ve-bot](https://github.com/edwinvrgs/found-people-ve-bot) | Búsqueda por nombre/cédula | ✅ Producción |
| [Venezuela Juntos](https://github.com/OnBeIt/Venezuela_Juntos_v2) | Reconocimiento facial ArcFace | ✅ Funcionando |

## 🚂 Deploy en Railway

1. Conectá tu repo de GitHub a [Railway](https://railway.app)
2. Railway detecta automáticamente `Dockerfile` y `railway.toml`
3. Configurá las variables de entorno desde `.env.example`
4. El webhook se configura solo al arrancar (`PUBLIC_BASE_URL`)

## 📋 Estado del proyecto

| Issue | Descripción | Estado |
|---|---|---|
| BUS-21 | Telegram Bot core | ✅ |
| BUS-22 | Flujo búsqueda por texto | ✅ |
| BUS-23 | Flujo búsqueda por foto | ✅ |
| BUS-24 | Flujo reportar desaparecido | ✅ |
| BUS-25 | Flujo reportar encontrado | ✅ |
| BUS-26 | DB con embeddings | ✅ |
| BUS-27 | Deploy Railway | ⏳ Configuración pendiente |
| BUS-28 | Tests | ✅ 17/17 |

---

Build 4 Venezuela · [Dashboard](https://aeterna.red/build4venezuela/) · [Discord](https://build4venezuela.com/discord)
