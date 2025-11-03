# bot.py
import os
import telebot
from telebot import types
import logging
from datetime import datetime
import asyncio
import threading
import time

from config import Config
from database import DatabaseManager
from parsers import ParserManager
from analytics import ImageAnalyzer, PriceComparator

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class AutoInspectBot:
    def __init__(self):
        # Инициализация компонентов
        self.db = DatabaseManager()
        self.parser_manager = ParserManager(self.db)
        self.image_analyzer = ImageAnalyzer()
        self.price_comparator = PriceComparator(self.db)
        
        # Инициализация бота
        self.bot = telebot.TeleBot(Config.BOT_TOKEN)
        
        # Запуск фоновых задач
        self.setup_background_tasks()
        
        # Регистрация обработчиков
        self.setup_handlers()
        
        logger.info("✅ AutoInspect Bot initialized")
    
    def setup_background_tasks(self):
        """Запуск фоновых задач"""
        if Config.IS_RENDER:
            # На Render запускаем в отдельном потоке
            parsing_thread = threading.Thread(target=self.background_parsing_loop, daemon=True)
            parsing_thread.start()
            logger.info("✅ Background parsing started")
        
        # Health check endpoint для Render
        self.setup_health_check()
    
    def background_parsing_loop(self):
        """Фоновый сбор данных"""
        while True:
            try:
                logger.info("🔄 Starting background parsing cycle")
                self.parser_manager.collect_market_data()
                logger.info("✅ Background parsing completed")
                time.sleep(3600)  # Ждем 1 час
            except Exception as e:
                logger.error(f"❌ Background parsing error: {e}")
                time.sleep(300)  # 5 минут при ошибке
    
    def setup_health_check(self):
        """Health check для Render"""
        from flask import Flask
        app = Flask(__name__)
        
        @app.route('/')
        def health_check():
            return {
                "status": "healthy",
                "service": "auto-inspect-bot",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Запускаем Flask в отдельном потоке
        if Config.IS_RENDER:
            flask_thread = threading.Thread(
                target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False),
                daemon=True
            )
            flask_thread.start()
    
    def setup_handlers(self):
        """Настройка обработчиков сообщений"""
        
        @self.bot.message_handler(commands=['start'])
        def start_handler(message):
            self.handle_start(message)
        
        @self.bot.message_handler(commands=['help'])
        def help_handler(message):
            self.handle_help(message)
        
        @self.bot.message_handler(commands=['analyze'])
        def analyze_handler(message):
            self.handle_analyze(message)
        
        @self.bot.message_handler(regexp=r'https?://(www\.)?(avito|auto|drom)\.ru/.*')
        def url_handler(message):
            self.handle_ad_url(message)
        
        @self.bot.message_handler(content_types=['text'])
        def text_handler(message):
            self.handle_text(message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            self.handle_callback(call)
    
    def handle_start(self, message):
        """Обработка команды /start"""
        chat_id = message.chat.id
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('🔍 Анализировать объявление'),
            types.KeyboardButton('📊 Мои анализы'),
            types.KeyboardButton('ℹ️ Помощь')
        )
        
        welcome_text = """
🚗 *AutoInspect Bot* 

Ваш AI-помощник для анализа автомобилей с площадок:

• 🅰️ Авито • 🅱️ Auto.ru • 🇩 Drom.ru

*Что я умею:*
🎨 Анализировать ЛКП по фотографиям
🛞 Оценивать состояние колес и шин  
💰 Сравнивать цены с рынком
🔍 Находить похожие варианты

*Как начать:*
Отправьте ссылку на объявление или нажмите кнопку ниже 👇
        """
        
        self.bot.send_message(
            chat_id,
            welcome_text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"👋 New user started: {chat_id}")
    
    def handle_ad_url(self, message):
        """Обработка ссылки на объявление"""
        chat_id = message.chat.id
        url = message.text
        
        # Отправляем статус
        status_msg = self.bot.send_message(
            chat_id,
            "🔍 *Начинаю анализ объявления...*",
            parse_mode='Markdown'
        )
        
        try:
            # Парсинг объявления
            self.update_status(chat_id, status_msg.message_id, "📦 Скачиваю данные...")
            ad_data = self.parser_manager.parse_single_ad(url)
            
            if not ad_data:
                raise Exception("Не удалось получить данные объявления")
            
            # Анализ изображений
            self.update_status(chat_id, status_msg.message_id, "🖼️ Анализирую фотографии...")
            image_analysis = self.image_analyzer.analyze_car_photos(ad_data.get('image_urls', []))
            
            # Сравнение цен
            self.update_status(chat_id, status_msg.message_id, "💰 Сравниваю с рынком...")
            price_analysis = self.price_comparator.compare_with_market(ad_data)
            
            # Сохраняем анализ
            self.db.save_car_ad({**ad_data, **image_analysis})
            
            # Формируем отчет
            self.update_status(chat_id, status_msg.message_id, "📊 Формирую отчет...")
            report = self.generate_report(ad_data, image_analysis, price_analysis)
            
            # Отправляем результат
            self.send_analysis_result(chat_id, status_msg.message_id, report, ad_data)
            
            logger.info(f"✅ Analysis completed for {url}")
            
        except Exception as e:
            error_msg = f"❌ Ошибка анализа: {str(e)}"
            self.bot.edit_message_text(
                error_msg,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            logger.error(f"❌ Analysis failed for {url}: {e}")
    
    def update_status(self, chat_id, message_id, text):
        """Обновление статуса анализа"""
        try:
            self.bot.edit_message_text(
                f"🔍 *Анализ объявления:*\n{text}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Could not update status: {e}")
    
    def generate_report(self, ad_data, image_analysis, price_analysis):
        """Генерация отчета"""
        overall_score = self.calculate_overall_score(image_analysis, price_analysis)
        
        report = f"""
🚗 *{ad_data.get('title', 'Неизвестно')}*

💰 *Цена:* {ad_data.get('price', 0):,} руб.
📅 *Год:* {ad_data.get('year', 'Неизвестно')}
🏁 *Пробег:* {ad_data.get('mileage', 0):,} км
📍 *Регион:* {ad_data.get('region', 'Неизвестно')}

⭐ *ОБЩАЯ ОЦЕНКА:* {overall_score}/100

🎨 *Лакокрасочное покрытие:*
• Равномерность: {image_analysis.get('paint_analysis', {}).get('color_uniformity', 0):.1f}%
• Царапины: {image_analysis.get('paint_analysis', {}).get('scratches_count', 0)} шт.
• Вмятины: {image_analysis.get('paint_analysis', {}).get('dents_count', 0)} шт.

💰 *Анализ цены:*
• {self.get_price_recommendation(price_analysis)}

💡 *Рекомендации:*
{self.get_recommendations(image_analysis, price_analysis)}
        """
        
        return report
    
    def calculate_overall_score(self, image_analysis, price_analysis):
        """Расчет общего скора"""
        paint_score = image_analysis.get('paint_analysis', {}).get('color_uniformity', 0) * 0.7
        price_score = 100 if price_analysis.get('recommendation') in ['excellent', 'good'] else 60
        
        return min(100, (paint_score + price_score) / 2)
    
    def get_price_recommendation(self, price_analysis):
        """Текст рекомендации по цене"""
        recommendation = price_analysis.get('recommendation', 'unknown')
        
        recommendations = {
            'excellent': '✅ Отличная цена! Рекомендуем к покупке',
            'good': '👍 Хорошая цена, можно торговаться',
            'fair': '⚠️ Среднерыночная цена',
            'high': '❌ Завышенная цена, торг обязателен',
            'overpriced': '🚨 Сильно завышена, ищите другие варианты'
        }
        
        return recommendations.get(recommendation, 'Не удалось оценить цену')
    
    def send_analysis_result(self, chat_id, message_id, report, ad_data):
        """Отправка результатов с кнопками действий"""
        # Обновляем сообщение с отчетом
        self.bot.edit_message_text(
            report,
            chat_id,
            message_id,
            parse_mode='Markdown'
        )
        
        # Создаем инлайн-кнопки
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "🔍 Найти похожие", 
                callback_data=f"find_similar:{ad_data['id']}"
            ),
            types.InlineKeyboardButton(
                "💰 Детали цены", 
                callback_data=f"price_details:{ad_data['id']}"
            )
        )
        
        self.bot.send_message(
            chat_id,
            "🎯 *Выберите действие:*",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def handle_callback(self, call):
        """Обработка инлайн-кнопок"""
        chat_id = call.message.chat.id
        data = call.data
        
        try:
            if data.startswith('find_similar:'):
                ad_id = data.split(':')[1]
                self.show_similar_ads(chat_id, ad_id)
            
            elif data.startswith('price_details:'):
                ad_id = data.split(':')[1]
                self.show_price_details(chat_id, ad_id)
            
            # Подтверждаем обработку callback
            self.bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"❌ Callback handling error: {e}")
            self.bot.answer_callback_query(call.id, "❌ Произошла ошибка")
    
    def show_similar_ads(self, chat_id, ad_id):
        """Показать похожие объявления"""
        try:
            # Получаем оригинальное объявление
            original_ad = self.get_ad_by_id(ad_id)
            if not original_ad:
                raise Exception("Объявление не найдено")
            
            # Ищем похожие
            similar_ads = self.db.find_similar_ads(original_ad, limit=3)
            
            if not similar_ads:
                self.bot.send_message(chat_id, "🔍 Похожих объявлений не найдено")
                return
            
            message = "🚗 *Найдены похожие варианты:*\n\n"
            
            for i, ad in enumerate(similar_ads, 1):
                message += f"*{i}. {ad['title']}*\n"
                message += f"💰 {ad['price']:,} руб.\n"
                message += f"📅 {ad['year']} г. | 🏁 {ad.get('mileage', 0):,} км\n"
                message += f"📍 {ad.get('region', 'Неизвестно')}\n"
                message += f"⭐ Оценка: {ad.get('overall_score', 'N/A')}\n"
                message += f"🔗 [Открыть]({ad['url']})\n\n"
            
            self.bot.send_message(
                chat_id,
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except Exception as e:
            self.bot.send_message(chat_id, f"❌ Ошибка поиска: {str(e)}")
    
    def get_ad_by_id(self, ad_id):
        """Получение объявления по ID"""
        # Заглушка - в реальности запрос к БД
        return {"id": ad_id, "title": "Test Car", "price": 1000000, "year": 2020}
    
    def run(self):
        """Запуск бота"""
        logger.info("🚀 Starting AutoInspect Bot...")
        
        try:
            # Проверяем конфигурацию
            Config.validate_config()
            
            # Запускаем бота
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
            
        except Exception as e:
            logger.error(f"❌ Bot startup failed: {e}")
            raise

# Точка входа
if __name__ == "__main__":
    bot = AutoInspectBot()
    bot.run()