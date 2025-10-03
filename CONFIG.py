import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_TOKEN   = os.getenv("API_TOKEN")
    DB_HOST     = os.getenv("DB_HOST", "localhost")
    DB_USER     = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
    DB_NAME     = os.getenv("DB_NAME", "freelance_bot")
    DB_PORT     = int(os.getenv("DB_PORT", 3306))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @staticmethod
    def loglevel_numeric() -> int:
        return getattr(logging, str(Config.LOG_LEVEL).upper(), logging.INFO)