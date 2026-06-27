from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def menu_principal() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("1. Buscar persona", callback_data="buscar")],
        [InlineKeyboardButton("2. Registrar persona", callback_data="menu:registrar")],
        [InlineKeyboardButton("3. Ayuda", callback_data="ayuda")],
    ]
    return InlineKeyboardMarkup(keyboard)


def menu_registrar() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Desaparecido", callback_data="reportar:desaparecido")],
        [InlineKeyboardButton("Encontrado", callback_data="reportar:encontrado")],
        [InlineKeyboardButton("Volver", callback_data="menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirmar_teclado() -> ReplyKeyboardMarkup:
    keyboard = [["Confirmar", "Cancelar"]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


def resultado_teclado() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Buscar otra vez", callback_data="buscar"),
            InlineKeyboardButton("Menu principal", callback_data="menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
