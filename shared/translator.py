import json
import os
import logging

LOGGER = logging.getLogger(__name__)

class Translator:
    def __init__(self):
        self._translations = {}

    def load_language(self, lang_code="fa"):
        """
        Loads all .json language files from a language-specific directory 
        (e.g., strings/fa/) and merges them.
        """
        LOGGER.info(f"--- [Translator] Loading language '{lang_code}' ---")
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lang_dir = os.path.join(project_root, 'strings', lang_code)
        
        LOGGER.info(f"[Translator] Searching for JSON files in: {lang_dir}")

        if not os.path.isdir(lang_dir):
            LOGGER.error(f"[Translator] FATAL: Language directory not found at: {lang_dir}")
            raise RuntimeError(f"Language directory not found: {lang_dir}")

        # Reset translations before loading new ones
        self._translations = {}
        
        # Find all .json files in the directory
        json_files = [f for f in os.listdir(lang_dir) if f.endswith('.json')]
        
        if not json_files:
            LOGGER.warning(f"[Translator] No .json files found in {lang_dir}.")
            return

        for file_name in json_files:
            file_path = os.path.join(lang_dir, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Merge the loaded data into the main dictionary
                    self._translations.update(data)
                    LOGGER.info(f"[Translator] Successfully loaded and merged '{file_name}'.")
            except json.JSONDecodeError as e:
                LOGGER.error(f"[Translator] Error decoding JSON from '{file_name}': {e}")
                # Optionally, re-raise to stop the bot if a translation file is broken
                # raise RuntimeError(f"Error in {file_name}: {e}")
            except Exception as e:
                LOGGER.error(f"[Translator] An unexpected error occurred while reading '{file_name}': {e}")

        key_count = len(self._translations)
        LOGGER.info(f"--- [Translator] Language '{lang_code}' loaded successfully with {key_count} top-level keys. ---")


    def get(self, key, **kwargs):
        """
        Retrieves a translation string by its key and formats it with given arguments.
        """
        keys = key.split('.')
        value = self._translations
        try:
            for k in keys:
                value = value[k]
            
            if kwargs:
                return value.format(**kwargs)
            return value
        except KeyError:
            LOGGER.warning(f"[Translator] Translation key '{key}' not found.")
            return key

# Create a single global instance
translator = Translator()

# Define a simple alias
_ = translator.get

# This function is called once at startup from bot.py
def init_translator():
    # The language code 'fa' now refers to the 'strings/fa/' directory
    translator.load_language("fa")