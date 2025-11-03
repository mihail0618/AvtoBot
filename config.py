# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # Render specific
    IS_RENDER = os.getenv('RENDER', 'false').lower() == 'true'
    
    # Parsing settings
    PARSING_DELAY = 1  # seconds between requests
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 10
    
    # Analytics
    MIN_IMAGES_FOR_ANALYSIS = 1
    MAX_IMAGES_TO_ANALYZE = 5
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate_config(cls):
        """Проверка обязательных переменных"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        
        if not cls.DATABASE_URL and cls.IS_RENDER:
            raise ValueError("DATABASE_URL is required on Render")
        
        return True