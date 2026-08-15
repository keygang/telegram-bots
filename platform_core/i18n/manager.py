import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": "English 🇬🇧",
    "ru": "Русский 🇷🇺",
}

DEFAULT_LANGUAGE = "en"


class I18nManager:
    """
    Internationalization (i18n) Manager for loading JSON translations,
    resolving language codes, providing fallbacks, and interpolating strings.
    """

    def __init__(self, locales_dir: Optional[Path] = None):
        if locales_dir is None:
            locales_dir = Path(__file__).parent / "locales"
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.supported_languages = SUPPORTED_LANGUAGES.copy()
        self.default_language = DEFAULT_LANGUAGE
        self.load_translations()

    def load_translations(self) -> None:
        """Loads all JSON translation files from locales directory."""
        self.translations.clear()
        if not self.locales_dir.exists():
            logger.warning(f"Locales directory does not exist: {self.locales_dir}")
            return

        for file_path in self.locales_dir.glob("*.json"):
            lang_code = file_path.stem.lower()
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.translations[lang_code] = data
                    logger.info(f"Loaded {len(data)} translation keys for locale '{lang_code}'")
            except Exception as e:
                logger.error(f"Failed to load translation file {file_path}: {e}")

    def normalize_language_code(self, lang_code: Optional[str]) -> str:
        """
        Normalizes Telegram language codes (e.g. 'ru-RU' -> 'ru', 'es-MX' -> 'es').
        Returns default_language if not supported.
        """
        if not lang_code:
            return self.default_language

        code = lang_code.strip().lower().split("-")[0].split("_")[0]
        if code in self.translations:
            return code
        return self.default_language

    def get(self, key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
        """
        Retrieves a translated string by key for the given language.
        Falls back to default_language ('en') if translation is missing.
        """
        target_lang = self.normalize_language_code(lang)
        text = None

        # 1. Try target language
        if target_lang in self.translations and key in self.translations[target_lang]:
            text = self.translations[target_lang][key]

        # 2. Fallback to default language
        if text is None and self.default_language in self.translations and key in self.translations[self.default_language]:
            text = self.translations[self.default_language][key]

        # 3. Ultimate fallback: return key
        if text is None:
            text = key

        # Interpolate formatting parameters if provided
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(f"Formatting error for i18n key '{key}' with kwargs {kwargs}: {e}")
                return text

        return text

    def t(self, key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
        """Alias for get()"""
        return self.get(key, lang=lang, **kwargs)


# Global instance
i18n = I18nManager()
