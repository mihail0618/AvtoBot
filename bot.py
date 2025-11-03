# bot.py - УПРОЩЕННАЯ ВЕРСИЯ
import os
import telebot
from telebot import types
import logging
import requests
from bs4 import BeautifulSoup
import re
import json
import sqlite3
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('auto_inspect.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()
    
    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS car_ads (
                id TEXT PRIMARY KEY,
                source_platform TEXT,
                url TEXT,
                title TEXT,
                price INTEGER,
                year INTEGER,
                mileage INTEGER,
                region TEXT,
                image_urls TEXT,
                parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

class SimpleParser:
    def parse_avito_ad(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Простой парсинг через регулярные выражения
            title = self.extract_title(soup)
            price = self.extract_price(soup)
            images = self.extract_images(soup)
            
            return {
                'id': f"avito_{hash(url) % 1000000}",
                'source_platform': 'avito',
                'url': url,
                'title': title,
                'price': price,
                'year': self.extract_year(title),
                'mileage': self.extract_mileage(soup),
                'region': self.extract_region(url),
                'image_urls': json.dumps(images)
            }
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None
    
    def extract_title(self, soup):
        title_elem = soup.find('h1')
        return title_elem.text.strip() if title_elem else "Неизвестно"
    
    def extract_price(self, soup):
        price_elem = soup.find('meta', itemprop='price')
        if price_elem:
            return int(price_elem['content'])
        return 0

class SimpleAnalyzer:
    def analyze_images(self, image_urls):
        """Упрощенный анализ изображений"""
        if not image_urls:
            return {'error': 'Нет изображений'}
        
        return {
            'image_count': len(image_urls),
            'has_car_photos': len(image_urls) > 0,
            'photo_quality': 'good' if len(image_urls) >= 3 else 'poor',
            'recommendations': self.generate_recommendations(len(image_urls))
        }
    
    def generate_recommendations(self, image_count):
        if image_count == 0:
            return ["Запросите фото автомобиля"]
        elif image_count < 3:
            return ["Мало фотографий для полного анализа"]
        else:
            return ["Фото выглядят нормально"]

class AutoInspectBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.db = SimpleDatabase()
        self.parser = SimpleParser()
        self.analyzer = SimpleAnalyzer()
        
        self.setup_handlers()
        logger.info("✅ Bot initialized")
    
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start_handler(message):
            self.handle_start(message)
        
        @self.bot.message_handler(regexp=r'https?://(www\.)?avito\.ru/.*')
        def url_handler(message):
            self.handle_avito_url(message)
        
        @self.bot.message_handler(content_types=['text'])
        def text_handler(message):
            self.handle_text(message)
    
    def handle_start(self, message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add('🔍 Анализировать объявление')
        
        self.bot.send_message(
            message.chat.id,
            "🚗 *AutoInspect Bot*\n\nОтправьте ссылку на объявление с Авито для анализа!",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def handle_avito_url(self, message):
        chat_id = message.chat.id
        url = message.text
        
        status_msg = self.bot.send_message(chat_id, "🔍 *Анализирую объявление...*", parse_mode='Markdown')
        
        try:
            # Парсинг
            ad_data = self.parser.parse_avito_ad(url)
            if not ad_data:
                raise Exception("Не удалось распарсить объявление")
            
            # Простой анализ
            image_analysis = self.analyzer.analyze_images(json.loads(ad_data['image_urls']))
            
            # Формируем отчет
            report = self.generate_simple_report(ad_data, image_analysis)
            
            # Сохраняем в БД
            self.save_ad(ad_data)
            
            # Отправляем результат
            self.bot.edit_message_text(
                report,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.bot.edit_message_text(
                f"❌ Ошибка: {str(e)}",
                chat_id,
                status_msg.message_id
            )
    
    def generate_simple_report(self, ad_data, analysis):
        return f"""
🚗 *{ad_data['title']}*

💰 *Цена:* {ad_data['price']:,} руб.
📅 *Год:* {ad_data['year']}
📍 *Регион:* {ad_data['region']}

📊 *Анализ фотографий:*
• Количество фото: {analysis['image_count']}
• Качество: {analysis['photo_quality']}
• Рекомендации: {', '.join(analysis['recommendations'])}

💡 *Совет:* Всегда осматривайте автомобиль лично!
        """
    
    def save_ad(self, ad_data):
        cursor = self.db.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO car_ads 
            (id, source_platform, url, title, price, year, mileage, region, image_urls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ad_data['id'], ad_data['source_platform'], ad_data['url'],
            ad_data['title'], ad_data['price'], ad_data['year'],
            ad_data['mileage'], ad_data['region'], ad_data['image_urls']
        ))
        self.db.conn.commit()
    
    def handle_text(self, message):
        if message.text == '🔍 Анализировать объявление':
            self.bot.send_message(
                message.chat.id,
                "Отправьте ссылку на объявление с Авито"
            )
        else:
            self.bot.send_message(
                message.chat.id,
                "Отправьте ссылку на объявление с Авито или используйте кнопки ниже"
            )
    
    def run(self):
        logger.info("🚀 Starting bot...")
        self.bot.infinity_polling()

# Точка входа
if __name__ == "__main__":
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("❌ BOT_TOKEN not found in environment variables")
        exit(1)
    
    bot = AutoInspectBot(token)
    bot.run()
