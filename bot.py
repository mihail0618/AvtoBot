# bot.py - МАКСИМАЛЬНО ПРОСТОЙ
import os
import telebot
from telebot import types
import logging
import requests
from bs4 import BeautifulSoup
import re
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleAvitoBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
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
        markup.add('ℹ️ Помощь')
        
        welcome_text = """
🚗 *AutoInspect Bot*

Простой помощник для анализа объявлений с Авито.

*Отправьте ссылку на объявление с Авито* и я проанализирую его!

Пример ссылки:
`https://www.avito.ru/moskva/avtomobili/...`
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
        
        try:
            # Статус анализа
            status_msg = self.bot.send_message(chat_id, "🔍 *Анализирую объявление...*", parse_mode='Markdown')
            
            # Парсим данные
            ad_data = self.parse_simple_avito(url)
            
            if not ad_data:
                raise Exception("Не удалось получить данные")
            
            # Формируем отчет
            report = self.generate_simple_report(ad_data)
            
            # Отправляем результат
            self.bot.edit_message_text(
                report,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")
    
    def parse_simple_avito(self, url):
        """Простой парсинг Авито"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Заголовок
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.text.strip() if title_elem else "Неизвестно"
            
            # Цена
            price = 0
            price_elem = soup.find('meta', itemprop='price')
            if price_elem and price_elem.get('content'):
                price = int(price_elem['content'])
            else:
                # Альтернативный поиск цены
                price_text = soup.get_text()
                price_match = re.search(r'"price":\s*"(\d+)"', price_text)
                if price_match:
                    price = int(price_match.group(1))
            
            # Фотографии
            images = []
            img_elems = soup.find_all('img', {'data-src': True})
            for img in img_elems[:5]:
                src = img.get('data-src')
                if src and 'http' in src:
                    images.append(src)
            
            # Год из заголовка
            year_match = re.search(r'(19|20)\d{2}', title)
            year = int(year_match.group()) if year_match else 2020
            
            # Регион из URL
            region_match = re.search(r'avito\.ru/([^/]+)', url)
            region = region_match.group(1) if region_match else "Неизвестно"
            
            return {
                'title': title,
                'price': price,
                'year': year,
                'region': region,
                'image_count': len(images),
                'url': url
            }
            
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None
    
    def generate_simple_report(self, ad_data):
        """Генерация простого отчета"""
        
        # Анализ цены
        price_analysis = "нормальная"
        if ad_data['price'] == 0:
            price_analysis = "не указана"
        elif ad_data['price'] < 100000:
            price_analysis = "🚨 подозрительно низкая"
        elif ad_data['price'] > 5000000:
            price_analysis = "💎 высокая"
        
        # Анализ фото
        photo_analysis = "✅ достаточно" if ad_data['image_count'] >= 3 else "⚠️ мало"
        
        report = f"""
🚗 *{ad_data['title']}*

💰 *Цена:* {ad_data['price']:,} руб. ({price_analysis})
📅 *Год:* {ad_data['year']}
📍 *Регион:* {ad_data['region']}
📸 *Фотографии:* {ad_data['image_count']} ({photo_analysis})

💡 *Рекомендации:*
{self.get_recommendations(ad_data)}

🔍 *Всегда проверяйте:*
• Автомобиль лично
• Документы
• Историю обслуживания
• Тест-драйв
        """
        
        return report
    
    def get_recommendations(self, ad_data):
        """Генерация рекомендаций"""
        recommendations = []
        
        if ad_data['image_count'] == 0:
            recommendations.append("❌ Нет фото - запросите у продавца")
        elif ad_data['image_count'] < 3:
            recommendations.append("⚠️ Мало фото для полной оценки")
        
        if ad_data['price'] == 0:
            recommendations.append("💰 Цена не указана - уточните")
        elif ad_data['price'] < 100000:
            recommendations.append("🚨 Цена подозрительно низкая")
        
        if not recommendations:
            recommendations.append("✅ Объявление выглядит нормально")
        
        return "\n".join([f"• {rec}" for rec in recommendations])
    
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
                "🤖 *AutoInspect Bot*\n\n"
                "Я помогаю анализировать объявления с Авито.\n\n"
                "*Что я делаю:*\n"
                "• Проверяю основные параметры\n"
                "• Анализирую цену\n"
                "• Проверяю наличие фото\n"
                "• Даю рекомендации\n\n"
                "Просто отправьте ссылку на объявление! 🚀",
                parse_mode='Markdown'
            )
        else:
            self.bot.send_message(
                chat_id,
                "Используйте кнопки ниже или отправьте ссылку на объявление с Авито 👇"
            )
    
    def run(self):
        """Запуск бота"""
        logger.info("🚀 Starting bot...")
        try:
            self.bot.infinity_polling()
        except Exception as e:
            logger.error(f"Bot error: {e}")

# Запуск
if __name__ == "__main__":
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("❌ BOT_TOKEN not found!")
        exit(1)
    
    bot = SimpleAvitoBot(token)
    bot.run()
