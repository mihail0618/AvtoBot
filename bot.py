# bot.py - МАКСИМАЛЬНО УПРОЩЕННАЯ ВЕРСИЯ
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleAvitoParser:
    def parse_ad(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Базовый парсинг
            title = self.extract_title(soup)
            price = self.extract_price(soup)
            images = self.extract_images(soup)
            
            return {
                'title': title,
                'price': price,
                'images': images,
                'year': self.extract_year(title),
                'mileage': self.extract_mileage(soup),
                'region': self.extract_region(url)
            }
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None
    
    def extract_title(self, soup):
        try:
            # Несколько способов найти заголовок
            selectors = [
                'h1[data-marker="item-view/title"]',
                'h1.title-info-title',
                'h1'
            ]
            
            for selector in selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    return title_elem.text.strip()
            
            return "Неизвестная модель"
        except:
            return "Неизвестная модель"
    
    def extract_price(self, soup):
        try:
            # Несколько способов найти цену
            selectors = [
                'meta[itemprop="price"]',
                'span[data-marker="item-view/item-price"]',
                '.js-item-price'
            ]
            
            for selector in selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    if price_elem.get('content'):
                        return int(price_elem['content'])
                    price_text = price_elem.text.strip()
                    numbers = re.findall(r'\d+', price_text.replace(' ', ''))
                    if numbers:
                        return int(''.join(numbers))
            
            return 0
        except:
            return 0
    
    def extract_images(self, soup):
        try:
            images = []
            # Ищем изображения в галерее
            img_elems = soup.find_all('img', {'data-src': True})
            for img in img_elems[:5]:  # Первые 5 фото
                src = img.get('data-src') or img.get('src')
                if src and 'http' in src:
                    images.append(src)
            return images
        except:
            return []
    
    def extract_year(self, title):
        try:
            # Ищем год в заголовке
            year_match = re.search(r'(19|20)\d{2}', title)
            return int(year_match.group()) if year_match else 2020
        except:
            return 2020
    
    def extract_mileage(self, soup):
        try:
            # Ищем пробег
            mileage_elems = soup.find_all(text=re.compile(r'пробег', re.IGNORECASE))
            for elem in mileage_elems:
                parent = elem.parent
                if parent:
                    text = parent.text
                    numbers = re.findall(r'\d+', text.replace(' ', ''))
                    if numbers:
                        return int(''.join(numbers))
            return 0
        except:
            return 0
    
    def extract_region(self, url):
        try:
            # Извлекаем регион из URL
            match = re.search(r'avito\.ru/([^/]+)', url)
            return match.group(1) if match else "Неизвестно"
        except:
            return "Неизвестно"

class SimpleAnalyzer:
    def analyze_ad(self, ad_data):
        """Простой анализ объявления"""
        if not ad_data:
            return {"error": "Нет данных для анализа"}
        
        analysis = {
            'image_analysis': self.analyze_images(ad_data.get('images', [])),
            'price_analysis': self.analyze_price(ad_data.get('price', 0)),
            'general_recommendations': []
        }
        
        # Генерация рекомендаций
        if analysis['image_analysis']['image_count'] == 0:
            analysis['general_recommendations'].append("❌ Нет фотографий - запросите у продавца")
        elif analysis['image_analysis']['image_count'] < 3:
            analysis['general_recommendations'].append("⚠️ Мало фотографий для полной оценки")
        
        if analysis['price_analysis'] == 'suspicious':
            analysis['general_recommendations'].append("💰 Цена подозрительно низкая - будьте осторожны")
        
        return analysis
    
    def analyze_images(self, images):
        return {
            'image_count': len(images),
            'has_car_photos': len(images) > 0,
            'photo_quality': 'good' if len(images) >= 3 else 'poor'
        }
    
    def analyze_price(self, price):
        if price == 0:
            return 'unknown'
        elif price < 100000:
            return 'suspicious'
        elif price < 500000:
            return 'low'
        elif price < 1000000:
            return 'medium'
        else:
            return 'high'

class AutoInspectBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.parser = SimpleAvitoParser()
        self.analyzer = SimpleAnalyzer()
        
        self.setup_handlers()
        logger.info("✅ Bot initialized successfully")
    
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
        markup.add('ℹ️ Помощь')
        
        welcome_text = """
🚗 *AutoInspect Bot*

Простой помощник для анализа объявлений с Авито.

*Как использовать:*
1. Отправьте ссылку на объявление с Авито
2. Получите базовый анализ
3. Проверьте рекомендации

*Пример ссылки:*
`https://www.avito.ru/moskva/avtomobili/volkswagen_golf_2018...`

Нажмите кнопку ниже чтобы начать! 👇
        """
        
        self.bot.send_message(
            message.chat.id,
            welcome_text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def handle_avito_url(self, message):
        chat_id = message.chat.id
        url = message.text
        
        # Отправляем статус
        status_msg = self.bot.send_message(
            chat_id,
            "🔍 *Начинаю анализ объявления...*",
            parse_mode='Markdown'
        )
        
        try:
            # Шаг 1: Парсинг
            self.update_status(chat_id, status_msg.message_id, "📦 Получаю данные...")
            ad_data = self.parser.parse_ad(url)
            
            if not ad_data:
                raise Exception("Не удалось получить данные объявления")
            
            # Шаг 2: Анализ
            self.update_status(chat_id, status_msg.message_id, "📊 Анализирую...")
            analysis = self.analyzer.analyze_ad(ad_data)
            
            # Шаг 3: Формирование отчета
            self.update_status(chat_id, status_msg.message_id, "📝 Формирую отчет...")
            report = self.generate_report(ad_data, analysis)
            
            # Отправляем результат
            self.bot.edit_message_text(
                report,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Analysis completed for {url}")
            
        except Exception as e:
            error_msg = f"❌ *Ошибка анализа:* {str(e)}"
            self.bot.edit_message_text(
                error_msg,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            logger.error(f"❌ Analysis failed: {e}")
    
    def update_status(self, chat_id, message_id, text):
        """Обновление статуса анализа"""
        try:
            self.bot.edit_message_text(
                f"🔍 *Анализ объявления:*\n{text}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
        except:
            pass  # Игнорируем ошибки редактирования
    
    def generate_report(self, ad_data, analysis):
        """Генерация простого отчета"""
        
        # Эмодзи для качества фото
        photo_emoji = "✅" if analysis['image_analysis']['photo_quality'] == 'good' else "⚠️"
        
        # Эмодзи для цены
        price_emoji = {
            'suspicious': '🚨',
            'low': '💰', 
            'medium': '💵',
            'high': '💎',
            'unknown': '❓'
        }.get(analysis['price_analysis'], '💵')
        
        report = f"""
🚗 *{ad_data['title']}*

{price_emoji} *Цена:* {ad_data['price']:,} руб.
📅 *Год:* {ad_data['year']}
🏁 *Пробег:* {ad_data['mileage']:,} км
📍 *Регион:* {ad_data['region']}

📊 *Анализ фотографий:*
{photo_emoji} Количество фото: {analysis['image_analysis']['image_count']}
{photo_emoji} Качество: {analysis['image_analysis']['photo_quality']}

💡 *Рекомендации:*
"""
        
        # Добавляем рекомендации
        for rec in analysis['general_recommendations']:
            report += f"• {rec}\n"
        
        if not analysis['general_recommendations']:
            report += "• ✅ Объявление выглядит нормально\n"
        
        report += "\n🔍 *Всегда осматривайте автомобиль лично!*"
        
        return report
    
    def handle_text(self, message):
        chat_id = message.chat.id
        
        if message.text == '🔍 Анализировать объявление':
            self.bot.send_message(
                chat_id,
                "Отправьте ссылку на объявление с Авито\n\n*Пример:*\n`https://www.avito.ru/moskva/avtomobili/...`",
                parse_mode='Markdown'
            )
        elif message.text == 'ℹ️ Помощь':
            self.bot.send_message(
                chat_id,
                "🤖 *AutoInspect Bot - Помощь*\n\n"
                "Я помогаю анализировать объявления с Авито:\n\n"
                "1. Отправьте ссылку на объявление\n"
                "2. Я проверю основные параметры\n"
                "3. Вы получите рекомендации\n\n"
                "*Что я проверяю:*\n"
                "• Наличие и количество фотографий\n"
                "• Цену автомобиля\n"
                "• Основные параметры\n\n"
                "Отправьте ссылку чтобы начать! 🚀",
                parse_mode='Markdown'
            )
        else:
            self.bot.send_message(
                chat_id,
                "Отправьте ссылку на объявление с Авито или используйте кнопки ниже 👇"
            )
    
    def run(self):
        logger.info("🚀 Starting AutoInspect Bot...")
        try:
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"❌ Bot crashed: {e}")
            raise

# Запуск бота
if __name__ == "__main__":
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("❌ BOT_TOKEN not found!")
        exit(1)
    
    bot = AutoInspectBot(token)
    bot.run()
