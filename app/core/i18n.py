import json
from pathlib import Path
from typing import Dict, Any

class I18n:
    def __init__(self):
        self.translations = {}
        self.load_translations()
    
    def load_translations(self):
        locales_dir = Path("app/locales")
        for lang_dir in locales_dir.iterdir():
            if lang_dir.is_dir():
                lang_code = lang_dir.name
                translations_file = lang_dir / "translations.json"
                if translations_file.exists():
                    with open(translations_file, 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
    
    def get_text(self, key: str, lang: str = "en", **kwargs) -> str:
        if lang not in self.translations:
            lang = "en"
        
        keys = key.split(".")
        text = self.translations.get(lang, {})
        
        for k in keys:
            if isinstance(text, dict) and k in text:
                text = text[k]
            else:
                return key
        
        if isinstance(text, str) and kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        
        return text if isinstance(text, str) else key

i18n = I18n()