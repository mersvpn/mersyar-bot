# FILE: shared/translator.py (FINAL BULLETPROOF VERSION)

import json
import os
import logging

LOGGER = logging.getLogger(__name__)

class Translator:
    def __init__(self):
        # The translations dictionary is now considered a cache.
        self._translations_cache = {}
        # A flag to prevent recursive reloading in case of persistent failure.
        self._is_reloading = False

    def load_language(self, lang_code="fa"):
        """
        Loads all .json language files from disk into the cache.
        This function now serves as the single source of truth for loading.
        """
        LOGGER.info(f"--- [Translator] Loading/Reloading language '{lang_code}' ---")
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lang_dir = os.path.join(project_root, 'strings', lang_code)
        
        if not os.path.isdir(lang_dir):
            LOGGER.error(f"[Translator] FATAL: Language directory not found at: {lang_dir}")
            return # Don't raise an error, just fail gracefully.

        # Create a temporary dictionary to hold new translations
        new_translations = {}
        json_files = [f for f in os.listdir(lang_dir) if f.endswith('.json')]

        for file_name in json_files:
            file_path = os.path.join(lang_dir, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Merge into the temporary dictionary
                    new_translations.update(data)
            except Exception as e:
                LOGGER.error(f"[Translator] Failed to load '{file_name}': {e}")
        
        # Atomically replace the old cache with the new one
        self._translations_cache = new_translations
        LOGGER.info(f"--- [Translator] Language '{lang_code}' loaded with {len(self._translations_cache)} keys. ---")


    def get(self, key, **kwargs):
        """
        Retrieves a translation string. If the key is not found, it automatically
        triggers a reload from disk and tries one more time before failing.
        This is a "self-healing" mechanism.
        """
        try:
            # First attempt: Try to get the key from the current cache
            return self._get_from_dict(self._translations_cache, key, **kwargs)
        except KeyError:
            # If it fails, and we are not already in a reload loop
            if not self._is_reloading:
                LOGGER.warning(f"[Translator] Key '{key}' not found. Triggering automatic reload.")
                self._is_reloading = True
                self.load_language("fa") # Force reload from disk
                self._is_reloading = False
                
                try:
                    # Second attempt: Try again with the newly loaded cache
                    return self._get_from_dict(self._translations_cache, key, **kwargs)
                except KeyError:
                    # If it still fails, then the key truly doesn't exist.
                    LOGGER.error(f"[Translator] Key '{key}' not found even after reload.")
                    return key
            else:
                # This prevents an infinite loop if load_language itself needs a translation
                return key

    def _get_from_dict(self, dictionary, key, **kwargs):
        """Helper function to navigate the dictionary."""
        keys = key.split('.')
        value = dictionary
        for k in keys:
            value = value[k] # This will raise KeyError if not found
        
        if kwargs:
            return value.format(**kwargs)
        return value

# --- SINGLETON INSTANCE AND ALIAS ---

translator = Translator()
_ = translator.get

def init_translator():
    """Initializes the translator at startup."""
    translator.load_language("fa")