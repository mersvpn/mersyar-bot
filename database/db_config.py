import os

class DatabaseConfig:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")

    @staticmethod
    def is_configured() -> bool:
        return all([
            DatabaseConfig.DB_USER,
            DatabaseConfig.DB_PASSWORD,
            DatabaseConfig.DB_NAME
        ])

db_config = DatabaseConfig()