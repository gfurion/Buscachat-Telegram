import unicodedata
import re


def normalizar_texto(texto: str) -> str:
    """Normaliza texto: lowercase, quita acentos, espacios extra."""
    if not texto:
        return ""

    texto = texto.lower().strip()

    nfkd = unicodedata.normalize('NFKD', texto)
    sin_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))

    sin_acentos = re.sub(r'[^\w\s]', '', sin_acentos)
    sin_acentos = re.sub(r'\s+', ' ', sin_acentos).strip()

    return sin_acentos


def escape_md(text: str) -> str:
    """Escapa caracteres especiales de MarkdownV1 en texto del usuario."""
    if not text:
        return text
    return text.replace("\\", "\\\\").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
