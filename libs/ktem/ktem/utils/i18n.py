"""Internationalization utilities."""

from typing import Optional

# Default language
_current_language = "en"

# Available languages
LANGUAGES = {
    "en": "English",
    "ru": "Русский",
}


def get_language() -> str:
    """Get current language."""
    return _current_language


def set_language(lang: str) -> None:
    """Set current language."""
    global _current_language
    if lang in LANGUAGES:
        _current_language = lang


def get_text(section: str, key: str, **kwargs) -> str:
    """Get translated text."""
    try:
        if _current_language == "ru":
            from ktem.locales.ru import TRANSLATIONS
        else:
            from ktem.locales.en import TRANSLATIONS
        
        text = TRANSLATIONS.get(section, {}).get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text
    except Exception:
        return key


def t(section: str, key: str, **kwargs) -> str:
    """Shortcut for get_text."""
    return get_text(section, key, **kwargs)
