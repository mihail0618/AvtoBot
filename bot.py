# bot.py - ВЕРСИЯ БЕЗ LXML
import os
import telebot
from telebot import types
import logging
import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleAvitoBot:
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
            self.bot.edit_message_text(
                "📦 *Получаю данные...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            ad_data = self.parse_avito_ad(url)
            
            if not ad_data:
                raise Exception("Не удалось получить данные объявления")
            
            # Анализируем
            self.bot.edit_message_text(
                "📊 *Анализирую...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            analysis = self.analyze_ad(ad_data)
            
            # Формируем отчет
            self.bot.edit_message_text(
                "📝 *Формирую отчет...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            report = self.generate_report(ad_data, analysis)
            
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
        """Парсинг объявления с Авито без lxml"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Используем встроенный html.parser вместо lxml
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем основные данные
            title = self.extract_title(soup)
            price = self.extract_price(soup, response.text)
            images = self.extract_images(soup)
            year = self.extract_year(title)
            region = self.extract_region(url)
            mileage = self.extract_mileage(soup, response.text)
            
            return {
                'title': title,
                'price': price,
                'year': year,
                'region': region,
                'mileage': mileage,
                'image_count': len(images),
                'images': images[:5],  # Только первые 5 фото
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
                '.title-info-title-text',
                '[data-marker="item-view/title"]'
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element and element.get_text(strip=True):
                    return element.get_text(strip=True)
            
            # Если не нашли по селекторам, ищем в мета-тегах
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                return meta_title['content']
            
            # Ищем в title страницы
            page_title = soup.find('title')
            if page_title:
                return page_title.get_text(strip=True)
            
            return "Неизвестная модель"
            
        except Exception as e:
            logger.error(f"Title extraction error: {e}")
            return "Неизвестная модель"
    
    def extract_price(self, soup, page_text):
        """Извлечение цены"""
        try:
            # Пробуем разные способы найти цену
            price_selectors = [
                'meta[itemprop="price"]',
                'span[data-marker="item-view/item-price"]',
                '[data-marker="item-view/item-price"]',
                '.js-item-price',
                '.price-value',
                '.style-item-price-text-_w822'
            ]
            
            for selector in price_selectors:
                element = soup.select_one(selector)
                if element:
                    # Пробуем из атрибута content
                    if element.get('content'):
                        price_str = element['content']
                        if price_str.isdigit():
                            return int(price_str)
                    
                    # Пробуем из текста
                    price_text = element.get_text(strip=True)
                    numbers = re.findall(r'\d+', price_text.replace(' ', ''))
                    if numbers:
                        return int(''.join(numbers))
            
            # Ищем в JSON-LD
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    if 'offers' in data and 'price' in data['offers']:
                        return int(data['offers']['price'])
                except:
                    pass
            
            # Ищем в тексте страницы с регулярными выражениями
            price_patterns = [
                r'"price":\s*"(\d+)"',
                r'"price":\s*(\d+)',
                r'itemprop="price".*?content="(\d+)"',
                r'data-marker="item-view/item-price".*?>.*?(\d[\d\s]*)\s*₽'
            ]
            
            for pattern in price_patterns:
                matches = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                if matches:
                    price_str = matches.group(1).replace(' ', '')
                    if price_str.isdigit():
                        return int(price_str)
            
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
                '[data-marker="image-frame/image"]',
                '.photo-slider-image-img'
            ]
            
            for selector in img_selectors:
                img_elements = soup.select(selector)
                for img in img_elements[:10]:  # Максимум 10 фото
                    src = img.get('data-src') or img.get('src')
                    if src and src.startswith('http'):
                        # Нормализуем URL
                        if src.startswith('//'):
                            src = 'https:' + src
                        images.append(src)
            
            # Удаляем дубликаты
            unique_images = []
            for img in images:
                if img not in unique_images:
                    unique_images.append(img)
            
            return unique_images
            
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
                    'spb': 'Санкт-Петербург',
                    'novosibirsk': 'Новосибирск',
                    'ekaterinburg': 'Екатеринбург',
                    'kazan': 'Казань',
                    'nizhniy_novgorod': 'Нижний Новгород',
                    'chelyabinsk': 'Челябинск',
                    'omsk': 'Омск',
                    'samara': 'Самара',
                    'rostov-na-donu': 'Ростов-на-Дону',
                    'ufa': 'Уфа',
                    'krasnoyarsk': 'Красноярск',
                    'voronezh': 'Воронеж',
                    'perm': 'Пермь',
                    'volgograd': 'Волгоград'
                }
                return region_map.get(region, region.replace('-', ' ').title())
            return "Неизвестно"
        except:
            return "Неизвестно"
    
    def extract_mileage(self, soup, page_text):
        """Извлечение пробега"""
        try:
            # Ищем пробег в тексте
            mileage_patterns = [
                r'пробег[^\d]*(\d[\d\s]*)\s*км',
                r'(\d[\d\s]*)\s*км[^.]*пробег',
                r'пробег</span>.*?<span[^>]*>.*?(\d[\d\s]*)\s*км',
                r'"mileage".*?"value".*?"(\d+)"'
            ]
            
            for pattern in mileage_patterns:
                matches = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                if matches:
                    mileage_str = matches.group(1).replace(' ', '')
                    if mileage_str.isdigit():
                        return int(mileage_str)
            
            return 0
            
        except Exception as e:
            logger.error(f"Mileage extraction error: {e}")
            return 0
    
    def analyze_ad(self, ad_data):
        """Анализ объявления"""
        analysis = {
            'price_analysis': self.analyze_price(ad_data['price']),
            'photo_analysis': self.analyze_photos(ad_data['image_count']),
            'mileage_analysis': self.analyze_mileage(ad_data['mileage'], ad_data['year']),
            'year_analysis': self.analyze_year(ad_data['year']),
            'recommendations': []
        }
        
        # Генерация рекомендаций
        recommendations = self.generate_recommendations(ad_data, analysis)
        analysis['recommendations'] = recommendations
        
        # Общая оценка
        analysis['overall_score'] = self.calculate_overall_score(ad_data, analysis)
        
        return analysis
    
    def analyze_price(self, price):
        """Анализ цены"""
        if price == 0:
            return {'emoji': '❓', 'text': 'Цена не указана', 'score': 3}
        elif price < 100000:
            return {'emoji': '🚨', 'text': 'Подозрительно низкая', 'score': 1}
        elif price < 300000:
            return {'emoji': '💰', 'text': 'Низкая', 'score': 7}
        elif price < 800000:
            return {'emoji': '💵', 'text': 'Средняя', 'score': 8}
        elif price < 2000000:
            return {'emoji': '💎', 'text': 'Высокая', 'score': 6}
        else:
            return {'emoji': '🏎️', 'text': 'Премиум', 'score': 5}
    
    def analyze_photos(self, image_count):
        """Анализ фотографий"""
        if image_count == 0:
            return {'emoji': '❌', 'text': 'Нет фото', 'score': 1}
        elif image_count < 3:
            return {'emoji': '⚠️', 'text': 'Мало фото', 'score': 5}
        elif image_count < 6:
            return {'emoji': '✅', 'text': 'Достаточно', 'score': 8}
        else:
            return {'emoji': '📸', 'text': 'Много фото', 'score': 9}
    
    def analyze_mileage(self, mileage, year):
        """Анализ пробега"""
        if mileage == 0:
            return {'emoji': '❓', 'text': 'Не указан', 'score': 5}
        
        car_age = 2024 - year
        if car_age <= 0:
            car_age = 1
        
        avg_mileage_per_year = mileage / car_age
        
        if avg_mileage_per_year < 10000:
            return {'emoji': '👍', 'text': 'Низкий пробег', 'score': 9}
        elif avg_mileage_per_year < 20000:
            return {'emoji': '✅', 'text': 'Нормальный пробег', 'score': 7}
        elif avg_mileage_per_year < 30000:
            return {'emoji': '⚠️', 'text': 'Высокий пробег', 'score': 4}
        else:
            return {'emoji': '🚨', 'text': 'Очень высокий пробег', 'score': 2}
    
    def analyze_year(self, year):
        """Анализ года выпуска"""
        car_age = 2024 - year
        
        if car_age <= 3:
            return {'emoji': '🆕', 'text': 'Новый', 'score': 9}
        elif car_age <= 7:
            return {'emoji': '✅', 'text': 'Средний возраст', 'score': 7}
        elif car_age <= 12:
            return {'emoji': '⚠️', 'text': 'Старый', 'score': 5}
        else:
            return {'emoji': '🚗', 'text': 'Ветеран', 'score': 3}
    
    def calculate_overall_score(self, ad_data, analysis):
        """Расчет общей оценки"""
        scores = [
            analysis['price_analysis']['score'],
            analysis['photo_analysis']['score'],
            analysis['mileage_analysis']['score'],
            analysis['year_analysis']['score']
        ]
        
        return round(sum(scores) / len(scores))
    
    def generate_recommendations(self, ad_data, analysis):
        """Генерация рекомендаций"""
        recommendations = []
        
        # Рекомендации по фото
        if ad_data['image_count'] == 0:
            recommendations.append("❌ *Нет фотографий* - обязательно запросите у продавца")
        elif ad_data['image_count'] < 3:
            recommendations.append("⚠️ *Мало фотографий* - попросите дополнительные фото")
        
        # Рекомендации по цене
        if ad_data['price'] == 0:
            recommendations.append("❓ *Цена не указана* - уточните стоимость")
        elif ad_data['price'] < 100000:
            recommendations.append("🚨 *Подозрительно низкая цена* - будьте осторожны, возможны скрытые дефекты")
        
        # Рекомендации по пробегу
        if ad_data['mileage'] > 0:
            car_age = 2024 - ad_data['year']
            if car_age > 0:
                avg_mileage = ad_data['mileage'] / car_age
                if avg_mileage > 30000:
                    recommendations.append("⚠️ *Очень высокий пробег* - проверьте состояние двигателя и ходовой")
        
        # Рекомендации по году
        if 2024 - ad_data['year'] > 15:
            recommendations.append("🕰️ *Автомобиль старше 15 лет* - проверьте техническое состояние")
        
        if not recommendations:
            recommendations.append("✅ *Объявление выглядит нормально* - можно договариваться о осмотре")
        
        return recommendations
    
    def generate_report(self, ad_data, analysis):
        """Генерация отчета"""
        
        report = f"""
🚗 *{ad_data['title']}*

💰 *Цена:* {ad_data['price']:,} руб. {analysis['price_analysis']['emoji']}
📅 *Год:* {ad_data['year']} {analysis['year_analysis']['emoji']}
🏁 *Пробег:* {ad_data['mileage']:,} км {analysis['mileage_analysis']['emoji']}
📍 *Регион:* {ad_data['region']}
📸 *Фотографии:* {ad_data['image_count']} {analysis['photo_analysis']['emoji']}

⭐ *Общая оценка:* {analysis['overall_score']}/10

📊 *Детальный анализ:*
• Цена: {analysis['price_analysis']['text']}
• Фото: {analysis['photo_analysis']['text']}
• Пробег: {analysis['mileage_analysis']['text']}
• Возраст: {analysis['year_analysis']['text']}

💡 *Рекомендации:*
"""
        
        # Добавляем рекомендации
        for rec in analysis['recommendations']:
            report += f"• {rec}\n"
        
        report += f"""
🔍 *Советы по осмотру:*
• Всегда осматривайте автомобиль лично
• Проверяйте документы и VIN
• Сделайте тест-драйв
• Проверьте историю через онлайн-сервисы
• Осмотрите кузов на предмет ржавчины и вмятин

🎯 *Следующие шаги:*
Свяжитесь с продавцом и договоритесь о осмотре!
        """
        
        return report
    
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
• 🏁 Пробег и его соответствие возрасту
• 📅 Год выпуска и возраст автомобиля
• 📍 Регион продажи

*Пример работы:*
Отправьте: `https://www.avito.ru/moskva/avtomobili/volkswagen_golf_2018...`

*Примечание:* Я только помогаю с первичным анализом. Всегда проверяйте автомобиль лично!
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
    bot = SimpleAvitoBot(token)
    bot.run()
