# FILE: database/db_config.py (FINAL, CLEANED & CORRECTED VERSION)

import os
from dotenv import load_dotenv

def _load_env():
    """
    Helper function to load the .env file from the project root.
    It's designed to be run once when the module is imported.
    """
    project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    dotenv_path = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path):
        # override=True ensures that .env values are always preferred over system variables.
        load_dotenv(dotenv_path=dotenv_path, override=True)
    else:
        # This helps in debugging if the .env file is missing.
        print(f"Warning: .env file not found at {dotenv_path}")

# Load environment variables as soon as this module is imported.
_load_env()


def get_database_url() -> str:
    """
    Returns the ASYNCHRONOUS database URL for the main application (using aiomysql).
    """
    # Using 'DB_PASSWORD' to match your .env file
    db_vars = {
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASS": os.getenv("DB_PASSWORD"), 
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_NAME": os.getenv("DB_NAME")
    }

    missing_vars = [key for key, value in db_vars.items() if value is None]
    if missing_vars:
        raise ValueError(f"Database env variables not set for application: {', '.join(missing_vars)}")
        
    return f"mysql+aiomysql://{db_vars['DB_USER']}:{db_vars['DB_PASS']}@{db_vars['DB_HOST']}/{db_vars['DB_NAME']}"


def get_sync_database_url() -> str:
    """
    Returns the SYNCHRONOUS database URL for Alembic (using pymysql).
    """
    # Using 'DB_PASSWORD' to match your .env file
    db_vars = {
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASS": os.getenv("DB_PASSWORD"),
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_NAME": os.getenv("DB_NAME")
    }

    missing_vars = [key for key, value in db_vars.items() if value is None]
    if missing_vars:
        raise ValueError(f"Database env variables not set for Alembic: {', '.join(missing_vars)}")
        
    return f"mysql+pymysql://{db_vars['DB_USER']}:{db_vars['DB_PASS']}@{db_vars['DB_HOST']}/{db_vars['DB_NAME']}"