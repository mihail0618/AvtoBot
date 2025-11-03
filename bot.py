# bot.py - МИНИМАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ
import os
import telebot
from telebot import types
import logging
import requests
from bs4 import BeautifulSoup
import re

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MinimalAvitoBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.setup_handlers()
        logger.info("✅ Bot initialized successfully!")
    
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def start_handler(message):
            self.handle_start(message)
        
        @self.bot.message_handler(regexp=r'https?://(www\.)?avito\.ru/.*')
        def url_handler(message):
            self.handle_avito_url(message)
        
        @self.bot.message_handler(func=lambda message: True)
        def text_handler(message):
            self.handle_text(message)
    
    def handle_start(self, message):
        chat_id = message.chat.id
        
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
            chat_id,
            welcome_text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def handle_avito_url(self, message):
        chat_id = message.chat.id
        url = message.text
        
        try:
            # Статус анализа
            status_msg = self.bot.send_message(
                chat_id, 
                "🔍 *Анализирую объявление...*", 
                parse_mode='Markdown'
            )
            
            # Парсим данные
            ad_data = self.parse_avito_ad(url)
            
            if not ad_data:
                raise Exception("Не удалось получить данные объявления")
            
            # Формируем отчет
            report = self.generate_report(ad_data)
            
            # Отправляем результат
            self.bot.edit_message_text(
                report,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Successfully analyzed: {url}")
            
        except Exception as e:
            error_msg = f"❌ *Ошибка анализа:* {str(e)}"
            try:
                self.bot.edit_message_text(
                    error_msg,
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
            except:
                self.bot.send_message(chat_id, error_msg, parse_mode='Markdown')
            
            logger.error(f"❌ Analysis failed: {e}")
    
    def parse_avito_ad(self, url):
        """Парсинг объявления с Авито"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем заголовок
            title = self.extract_title(soup)
            
            # Извлекаем цену
            price = self.extract_price(soup)
            
            # Извлекаем фотографии
            images = self.extract_images(soup)
            
            # Извлекаем год из заголовка
            year = self.extract_year(title)
            
            # Извлекаем регион из URL
            region = self.extract_region(url)
            
            return {
                'title': title,
                'price': price,
                'year': year,
                'region': region,
                'image_count': len(images),
                'images': images[:3],  # Только первые 3 фото
                'url': url
            }
            
        except Exception as e:
            logger.error(f"❌ Parsing failed: {e}")
            return None
    
    def extract_title(self, soup):
        """Извлечение заголовка"""
        try:
            # Пробуем разные селекторы
            selectors = [
                'h1[data-marker="item-view/title"]',
                'h1.title-info-title',
                'h1',
                '[data-marker="item-view/title"]'
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element and element.text.strip():
                    return element.text.strip()
            
            # Если не нашли по селекторам, ищем в мета-тегах
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                return meta_title['content']
            
            return "Неизвестная модель"
            
        except Exception as e:
            logger.error(f"Title extraction error: {e}")
            return "Неизвестная модель"
    
    def extract_price(self, soup):
        """Извлечение цены"""
        try:
            # Пробуем разные способы найти цену
            price_selectors = [
                'meta[itemprop="price"]',
                'span[data-marker="item-view/item-price"]',
                '[data-marker="item-view/item-price"]',
                '.js-item-price',
                '.price-value'
            ]
            
            for selector in price_selectors:
                element = soup.select_one(selector)
                if element:
                    # Пробуем из атрибута content
                    if element.get('content'):
                        return int(element['content'])
                    
                    # Пробуем из текста
                    price_text = element.text.strip()
                    numbers = re.findall(r'\d+', price_text.replace(' ', ''))
                    if numbers:
                        return int(''.join(numbers))
            
            # Ищем в JSON-LD
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                import json
                try:
                    data = json.loads(json_ld.string)
                    if 'offers' in data and 'price' in data['offers']:
                        return int(data['offers']['price'])
                except:
                    pass
            
            # Ищем в тексте страницы
            page_text = soup.get_text()
            price_match = re.search(r'"price":\s*"(\d+)"', page_text)
            if price_match:
                return int(price_match.group(1))
            
            return 0
            
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            return 0
    
    def extract_images(self, soup):
        """Извлечение изображений"""
        try:
            images = []
            
            # Ищем изображения в галерее
            img_selectors = [
                'img[data-src]',
                'img[src*="avito"]',
                '.gallery-img-cover img',
                '[data-marker="image-frame/image"]'
            ]
            
            for selector in img_selectors:
                img_elements = soup.select(selector)
                for img in img_elements[:10]:  # Максимум 10 фото
                    src = img.get('data-src') or img.get('src')
                    if src and src.startswith('http'):
                        images.append(src)
            
            # Удаляем дубликаты
            return list(dict.fromkeys(images))
            
        except Exception as e:
            logger.error(f"Image extraction error: {e}")
            return []
    
    def extract_year(self, title):
        """Извлечение года из заголовка"""
        try:
            year_match = re.search(r'\b(19|20)\d{2}\b', title)
            return int(year_match.group()) if year_match else 2020
        except:
            return 2020
    
    def extract_region(self, url):
        """Извлечение региона из URL"""
        try:
            match = re.search(r'avito\.ru/([^/]+)', url)
            if match:
                region = match.group(1)
                # Красивое отображение региона
                region_map = {
                    'moskva': 'Москва',
                    'sankt-peterburg': 'Санкт-Петербург',
                    'novosibirsk': 'Новосибирск',
                    'ekaterinburg': 'Екатеринбург',
                    'kazan': 'Казань'
                }
                return region_map.get(region, region.replace('-', ' ').title())
            return "Неизвестно"
        except:
            return "Неизвестно"
    
    def generate_report(self, ad_data):
        """Генерация отчета"""
        
        # Анализ цены
        price_analysis = self.analyze_price(ad_data['price'])
        
        # Анализ фотографий
        photo_analysis = self.analyze_photos(ad_data['image_count'])
        
        # Общая оценка
        overall_score = self.calculate_score(ad_data)
        
        report = f"""
🚗 *{ad_data['title']}*

💰 *Цена:* {ad_data['price']:,} руб. {price_analysis['emoji']}
📅 *Год:* {ad_data['year']}
📍 *Регион:* {ad_data['region']}
📸 *Фотографии:* {ad_data['image_count']} {photo_analysis['emoji']}

⭐ *Общая оценка:* {overall_score}/10

💡 *Рекомендации:*
{self.generate_recommendations(ad_data, price_analysis, photo_analysis)}

🔍 *Советы по осмотру:*
• Всегда осматривайте автомобиль лично
• Проверяйте документы и историю
• Обязательно сделайте тест-драйв
• Проверьте VIN через официальные сервисы
        """
        
        return report
    
    def analyze_price(self, price):
        """Анализ цены"""
        if price == 0:
            return {'emoji': '❓', 'text': 'Цена не указана'}
        elif price < 100000:
            return {'emoji': '🚨', 'text': 'Подозрительно низкая цена'}
        elif price < 300000:
            return {'emoji': '💰', 'text': 'Низкая цена'}
        elif price < 800000:
            return {'emoji': '💵', 'text': 'Средняя цена'}
        elif price < 2000000:
            return {'emoji': '💎', 'text': 'Высокая цена'}
        else:
            return {'emoji': '🏎️', 'text': 'Премиум сегмент'}
    
    def analyze_photos(self, image_count):
        """Анализ фотографий"""
        if image_count == 0:
            return {'emoji': '❌', 'text': 'Нет фотографий'}
        elif image_count < 3:
            return {'emoji': '⚠️', 'text': 'Мало фотографий'}
        elif image_count < 6:
            return {'emoji': '✅', 'text': 'Достаточно фото'}
        else:
            return {'emoji': '📸', 'text': 'Много фото'}
    
    def calculate_score(self, ad_data):
        """Расчет общей оценки"""
        score = 5  # Базовая оценка
        
        # Бонус за фото
        if ad_data['image_count'] >= 3:
            score += 2
        elif ad_data['image_count'] > 0:
            score += 1
        
        # Бонус за нормальную цену
        if 100000 <= ad_data['price'] <= 2000000:
            score += 2
        elif ad_data['price'] > 0:
            score += 1
        
        # Бонус за год (не старше 20 лет)
        current_year = 2024
        if current_year - ad_data['year'] <= 10:
            score += 1
        
        return min(10, score)
    
    def generate_recommendations(self, ad_data, price_analysis, photo_analysis):
        """Генерация рекомендаций"""
        recommendations = []
        
        # Рекомендации по фото
        if ad_data['image_count'] == 0:
            recommendations.append("• ❌ *Нет фото* - обязательно запросите у продавца")
        elif ad_data['image_count'] < 3:
            recommendations.append("• ⚠️ *Мало фото* - попросите дополнительные фотографии")
        
        # Рекомендации по цене
        if ad_data['price'] == 0:
            recommendations.append("• ❓ *Цена не указана* - уточните стоимость")
        elif ad_data['price'] < 100000:
            recommendations.append("• 🚨 *Подозрительно низкая цена* - будьте осторожны")
        
        # Общие рекомендации
        if not recommendations:
            recommendations.append("• ✅ *Объявление выглядит нормально* - можно договариваться о осмотре")
        
        return "\n".join(recommendations)
    
    def handle_text(self, message):
        chat_id = message.chat.id
        text = message.text
        
        if text == '🔍 Анализировать объявление':
            self.bot.send_message(
                chat_id,
                "Отправьте ссылку на объявление с Авито\n\n*Пример:*\n`https://www.avito.ru/moskva/avtomobili/volkswagen_golf_2018...`",
                parse_mode='Markdown'
            )
        
        elif text == 'ℹ️ Помощь':
            help_text = """
🤖 *AutoInspect Bot - Помощь*

*Как использовать:*
1. Отправьте ссылку на объявление с Авито
2. Я проанализирую основные параметры
3. Вы получите подробный отчет с рекомендациями

*Что я проверяю:*
• 📊 Основные параметры автомобиля
• 💰 Адекватность цены
• 📸 Наличие и количество фотографий
• 📍 Регион продажи

*Пример работы:*
Отправьте: `https://www.avito.ru/moskva/avtomobili/volkswagen_golf_2018...`

*Примечание:* Я только помогают с первичным анализом. Всегда проверяйте автомобиль лично!
            """
            self.bot.send_message(chat_id, help_text, parse_mode='Markdown')
        
        else:
            self.bot.send_message(
                chat_id,
                "Используйте кнопки ниже или отправьте ссылку на объявление с Авито 👇"
            )
    
    def run(self):
        """Запуск бота"""
        logger.info("🚀 Starting AutoInspect Bot...")
        try:
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"❌ Bot crashed: {e}")
            raise

# Запуск приложения
if __name__ == "__main__":
    # Получаем токен из переменных окружения
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        logger.error("❌ BOT_TOKEN environment variable is not set!")
        logger.error("Please set BOT_TOKEN in your environment variables")
        exit(1)
    
    # Создаем и запускаем бота
    bot = MinimalAvitoBot(token)
    bot.run()
