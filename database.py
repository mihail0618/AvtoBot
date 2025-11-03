# database.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.connect()
        self.init_tables()
    
    def connect(self):
        """Подключение к PostgreSQL на Render"""
        try:
            # Для Render PostgreSQL
            database_url = os.getenv('DATABASE_URL')
            
            if database_url:
                # Render использует формат postgresql://user:pass@host:port/db
                self.conn = psycopg2.connect(database_url, sslmode='require')
            else:
                # Локальная разработка - SQLite
                import sqlite3
                self.conn = sqlite3.connect('auto_inspect.db', check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
            
            logger.info("✅ Database connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise
    
    def init_tables(self):
        """Инициализация таблиц"""
        try:
            cursor = self.conn.cursor()
            
            # Таблица объявлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS car_ads (
                    id VARCHAR(255) PRIMARY KEY,
                    source_platform VARCHAR(50) NOT NULL,
                    url TEXT NOT NULL,
                    title VARCHAR(500),
                    price INTEGER,
                    year INTEGER,
                    mileage INTEGER,
                    region VARCHAR(100),
                    city VARCHAR(100),
                    image_urls JSONB,
                    overall_score FLOAT,
                    paint_analysis JSONB,
                    wheel_analysis JSONB,
                    interior_analysis JSONB,
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Таблица анализов пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_analyses (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    original_url TEXT,
                    analysis_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Индексы для производительности
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_car_ads_title ON car_ads(title);
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_car_ads_region_price ON car_ads(region, price);
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_car_ads_active ON car_ads(is_active, parsed_at);
            ''')
            
            self.conn.commit()
            logger.info("✅ Database tables initialized")
            
        except Exception as e:
            logger.error(f"❌ Table initialization failed: {e}")
            self.conn.rollback()
    
    def save_car_ad(self, ad_data):
        """Сохранение или обновление объявления"""
        try:
            cursor = self.conn.cursor()
            
            # Проверяем существование записи
            cursor.execute('SELECT id FROM car_ads WHERE id = %s', (ad_data['id'],))
            exists = cursor.fetchone()
            
            if exists:
                # Обновляем существующую запись
                query = '''
                    UPDATE car_ads SET 
                    title = %s, price = %s, year = %s, mileage = %s,
                    region = %s, city = %s, image_urls = %s,
                    overall_score = %s, paint_analysis = %s,
                    wheel_analysis = %s, interior_analysis = %s,
                    last_updated = CURRENT_TIMESTAMP, is_active = %s
                    WHERE id = %s
                '''
                cursor.execute(query, (
                    ad_data.get('title'),
                    ad_data.get('price'),
                    ad_data.get('year'),
                    ad_data.get('mileage'),
                    ad_data.get('region'),
                    ad_data.get('city'),
                    json.dumps(ad_data.get('image_urls', [])),
                    ad_data.get('overall_score'),
                    json.dumps(ad_data.get('paint_analysis', {})),
                    json.dumps(ad_data.get('wheel_analysis', {})),
                    json.dumps(ad_data.get('interior_analysis', {})),
                    ad_data.get('is_active', True),
                    ad_data['id']
                ))
            else:
                # Вставляем новую запись
                query = '''
                    INSERT INTO car_ads 
                    (id, source_platform, url, title, price, year, mileage, 
                     region, city, image_urls, overall_score, paint_analysis,
                     wheel_analysis, interior_analysis, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''
                cursor.execute(query, (
                    ad_data['id'],
                    ad_data['source_platform'],
                    ad_data['url'],
                    ad_data.get('title'),
                    ad_data.get('price'),
                    ad_data.get('year'),
                    ad_data.get('mileage'),
                    ad_data.get('region'),
                    ad_data.get('city'),
                    json.dumps(ad_data.get('image_urls', [])),
                    ad_data.get('overall_score'),
                    json.dumps(ad_data.get('paint_analysis', {})),
                    json.dumps(ad_data.get('wheel_analysis', {})),
                    json.dumps(ad_data.get('interior_analysis', {})),
                    ad_data.get('is_active', True)
                ))
            
            self.conn.commit()
            logger.info(f"✅ Saved car ad: {ad_data['id']}")
            
        except Exception as e:
            logger.error(f"❌ Error saving car ad: {e}")
            self.conn.rollback()
    
    def find_similar_ads(self, original_ad, limit=5):
        """Поиск похожих объявлений"""
        try:
            cursor = self.conn.cursor()
            
            # Извлекаем модель из названия
            model = self._extract_model(original_ad['title'])
            year = original_ad.get('year', 0)
            price = original_ad.get('price', 0)
            
            query = '''
                SELECT * FROM car_ads 
                WHERE title ILIKE %s 
                AND year BETWEEN %s AND %s
                AND price BETWEEN %s AND %s
                AND id != %s
                AND is_active = true
                ORDER BY overall_score DESC NULLS LAST,
                         ABS(price - %s) ASC
                LIMIT %s
            '''
            
            cursor.execute(query, (
                f'%{model}%',
                year - 2, year + 2,
                price * 0.7, price * 1.3,
                original_ad['id'],
                price,
                limit
            ))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"❌ Error finding similar ads: {e}")
            return []
    
    def _extract_model(self, title):
        """Извлечение модели автомобиля из названия"""
        if not title:
            return ""
        
        # Простая логика извлечения модели
        models = ['golf', 'passat', 'polo', 'jetta', 'tiguan', 'touran']
        title_lower = title.lower()
        
        for model in models:
            if model in title_lower:
                return model
        
        return title.split()[1] if len(title.split()) > 1 else ""

    def save_user_analysis(self, user_id, original_url, analysis_data):
        """Сохранение анализа пользователя"""
        try:
            cursor = self.conn.cursor()
            
            query = '''
                INSERT INTO user_analyses (user_id, original_url, analysis_data)
                VALUES (%s, %s, %s)
            '''
            
            cursor.execute(query, (
                user_id,
                original_url,
                json.dumps(analysis_data)
            ))
            
            self.conn.commit()
            logger.info(f"✅ Saved analysis for user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Error saving user analysis: {e}")
            self.conn.rollback()