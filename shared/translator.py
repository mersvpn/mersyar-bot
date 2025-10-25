# FILE: shared/translator.py (FINAL VERSION with Backward Compatibility)

import json
import os
import logging

LOGGER = logging.getLogger(__name__)

class Translator:
    def __init__(self):
        self._translations_cache = {}
        self._is_reloading = False

    def load_language(self, lang_code="fa"):
        """
        Loads all .json language files from disk into the cache.
        Each file is loaded under its own namespace (the filename).
        """
        LOGGER.info(f"--- [Translator] Loading/Reloading language '{lang_code}' ---")
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lang_dir = os.path.join(project_root, 'strings', lang_code)
        
        if not os.path.isdir(lang_dir):
            LOGGER.error(f"[Translator] FATAL: Language directory not found at: {lang_dir}")
            return

        new_translations = {}
        json_files = [f for f in os.listdir(lang_dir) if f.endswith('.json')]

        for file_name in json_files:
            file_path = os.path.join(lang_dir, file_name)
            namespace = os.path.splitext(file_name)[0]
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    new_translations[namespace] = data
            except Exception as e:
                LOGGER.error(f"[Translator] Failed to load '{file_name}' into namespace '{namespace}': {e}")
        
        self._translations_cache = new_translations
        total_keys = sum(len(v) for v in self._translations_cache.values() if isinstance(v, dict))
        LOGGER.info(f"--- [Translator] Language '{lang_code}' loaded with {len(self._translations_cache)} namespaces and {total_keys} total keys. ---")

    def get(self, key, **kwargs):
        """
        Retrieves a translation string with backward compatibility.
        1. Tries the modern, namespaced key (e.g., 'marzban.marzban_display.title').
        2. If not found, it tries a legacy, non-namespaced key by searching
           through all top-level namespaces (e.g., 'marzban_display.title').
        3. If still not found, it triggers a reload and tries both methods again.
        """
        # --- Attempt 1: Try the modern, fully qualified key first ---
        try:
            return self._get_from_dict(self._translations_cache, key, **kwargs)
        except KeyError:
            pass  # Key not found, proceed to legacy check

        # --- Attempt 2: Try legacy (non-namespaced) key ---
        if '.' in key:
            try:
                for namespace in self._translations_cache.values():
                    if isinstance(namespace, dict):
                        try:
                            return self._get_from_dict(namespace, key, **kwargs)
                        except KeyError:
                            continue # Not in this namespace, try next
            except (KeyError, TypeError):
                 pass

        # --- If both attempts fail, trigger a reload and try everything again ---
        if not self._is_reloading:
            LOGGER.warning(f"[Translator] Key '{key}' not found. Triggering automatic reload.")
            self._is_reloading = True
            self.load_language("fa")
            self._is_reloading = False
            
            # --- Attempt 3: Retry modern key after reload ---
            try:
                return self._get_from_dict(self._translations_cache, key, **kwargs)
            except KeyError:
                pass

            # --- Attempt 4: Retry legacy key after reload ---
            if '.' in key:
                try:
                    for namespace in self._translations_cache.values():
                        if isinstance(namespace, dict):
                            try:
                                return self._get_from_dict(namespace, key, **kwargs)
                            except KeyError:
                                continue
                except (KeyError, TypeError):
                    pass
        
        LOGGER.error(f"[Translator] Key '{key}' not found even after reload and legacy check.")
        return key

    def _get_from_dict(self, dictionary, key, **kwargs):
        """Helper function to navigate the dictionary."""
        keys = key.split('.')
        value = dictionary
        for k in keys:
            value = value[k]
        
        if kwargs:
            return value.format(**kwargs)
        return value

# --- SINGLETON INSTANCE AND ALIAS ---

translator = Translator()
get = translator.get
_ = translator.get

def init_translator():
    """Initializes the translator at startup."""
    translator.load_language("fa")