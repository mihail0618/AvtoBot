# bot.py - ПОЛНЫЙ КОД С АНАЛИЗОМ ЛКП
import os
import telebot
from telebot import types
import logging
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import cv2
import numpy as np
from PIL import Image
import io

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_webhook(token):
    """Сброс webhook чтобы использовать polling"""
    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Webhook reset successfully")
        else:
            logger.warning("⚠️ Could not reset webhook")
    except Exception as e:
        logger.warning(f"⚠️ Webhook reset failed: {e}")

class PaintAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_paint_from_urls(self, image_urls):
        """Анализ ЛКП по ссылкам на изображения"""
        if not image_urls:
            return {'error': 'Нет изображений для анализа', 'score': 0}
        
        analyses = []
        analyzed_count = 0
        
        for img_url in image_urls[:3]:  # Анализируем первые 3 фото
            try:
                analysis = self.analyze_single_image(img_url)
                if analysis and analysis.get('score', 0) > 0:
                    analyses.append(analysis)
                    analyzed_count += 1
                    self.logger.info(f"✅ Analyzed image {analyzed_count}")
            except Exception as e:
                self.logger.error(f"Ошибка анализа изображения: {e}")
                continue
        
        if not analyses:
            return {'error': 'Не удалось проанализировать изображения', 'score': 0}
        
        return self.aggregate_analyses(analyses, analyzed_count)
    
    def analyze_single_image(self, image_url):
        """Анализ одного изображения"""
        try:
            # Скачиваем изображение
            response = requests.get(image_url, timeout=15)
            if response.status_code != 200:
                return None
            
            # Конвертируем в numpy array
            image = Image.open(io.BytesIO(response.content))
            img_array = np.array(image)
            
            # Пропускаем маленькие изображения
            if img_array.shape[0] < 100 or img_array.shape[1] < 100:
                return None
            
            # Конвертируем в BGR для OpenCV если нужно
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                if img_array.shape[2] == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                # Если изображение grayscale, пропускаем
                return None
            
            return self.analyze_image_features(img_array)
            
        except Exception as e:
            self.logger.error(f"Image analysis error: {e}")
            return None
    
    def analyze_image_features(self, img_array):
        """Анализ характеристик изображения для оценки ЛКП"""
        try:
            # Предобработка
            processed_img = self.preprocess_image(img_array)
            
            # Анализ различных характеристик
            color_uniformity = self.analyze_color_uniformity(processed_img)
            edge_analysis = self.analyze_edges(processed_img)
            texture_analysis = self.analyze_texture(processed_img)
            brightness_analysis = self.analyze_brightness(processed_img)
            
            # Расчет общего скора
            overall_score = self.calculate_paint_score(
                color_uniformity, edge_analysis, texture_analysis, brightness_analysis
            )
            
            return {
                'score': overall_score,
                'color_uniformity': color_uniformity,
                'edge_quality': edge_analysis,
                'texture_smoothness': texture_analysis,
                'brightness_level': brightness_analysis
            }
            
        except Exception as e:
            self.logger.error(f"Feature analysis error: {e}")
            return {'score': 0}
    
    def preprocess_image(self, img_array):
        """Предобработка изображения"""
        # Увеличение резкости
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(img_array, -1, kernel)
        
        # Нормализация освещения
        lab = cv2.cvtColor(sharpened, cv2.COLOR_BGR2LAB)
        lab[:,:,0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(lab[:,:,0])
        normalized = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return normalized
    
    def analyze_color_uniformity(self, img_array):
        """Анализ равномерности цвета"""
        hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
        
        # Стандартное отклонение оттенка (меньше = равномернее)
        hue_std = np.std(hsv[:,:,0])
        saturation_std = np.std(hsv[:,:,1])
        
        # Оценка равномерности (0-100)
        uniformity_score = max(0, 100 - (hue_std * 0.5 + saturation_std * 0.2))
        
        return min(100, uniformity_score)
    
    def analyze_edges(self, img_array):
        """Анализ резкости и границ"""
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        
        # Детекция краев (больше краев = более детализированное изображение)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Оценка резкости (0-100)
        sharpness_score = min(100, edge_density * 1000)
        
        return sharpness_score
    
    def analyze_texture(self, img_array):
        """Анализ текстуры поверхности"""
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        
        # Вычисление лапласиана для оценки текстуры
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Оценка гладкости (меньше вариация = глаже поверхность)
        smoothness_score = max(0, 100 - laplacian_var * 0.1)
        
        return min(100, smoothness_score)
    
    def analyze_brightness(self, img_array):
        """Анализ яркости изображения"""
        hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
        avg_brightness = np.mean(hsv[:,:,2])
        
        # Идеальная яркость ~50-80%
        if 50 <= avg_brightness <= 80:
            brightness_score = 90
        elif 30 <= avg_brightness < 50 or 80 < avg_brightness <= 120:
            brightness_score = 70
        else:
            brightness_score = 40
        
        return brightness_score
    
    def calculate_paint_score(self, color_uniformity, edge_quality, texture_smoothness, brightness_level):
        """Расчет общего скора ЛКП"""
        weights = {
            'color_uniformity': 0.4,    # Самый важный показатель
            'edge_quality': 0.3,        # Резкость и детализация
            'texture_smoothness': 0.2,  # Гладкость поверхности
            'brightness_level': 0.1     # Качество освещения
        }
        
        total_score = (
            color_uniformity * weights['color_uniformity'] +
            edge_quality * weights['edge_quality'] +
            texture_smoothness * weights['texture_smoothness'] +
            brightness_level * weights['brightness_level']
        )
        
        return min(100, int(total_score))
    
    def aggregate_analyses(self, analyses, count):
        """Агрегация результатов анализа"""
        if not analyses:
            return {'score': 0, 'message': 'Нет данных для анализа'}
        
        total_score = sum(analysis['score'] for analysis in analyses)
        avg_score = total_score / len(analyses)
        
        # Определяем качество ЛКП по среднему скору
        if avg_score >= 80:
            condition = "отличное"
            emoji = "🎨"
        elif avg_score >= 60:
            condition = "хорошее" 
            emoji = "✅"
        elif avg_score >= 40:
            condition = "удовлетворительное"
            emoji = "⚠️"
        else:
            condition = "требует внимания"
            emoji = "🔧"
        
        return {
            'score': int(avg_score),
            'condition': condition,
            'emoji': emoji,
            'analyzed_images': count,
            'message': f"Проанализировано {count} изображений"
        }

class SimpleAvitoBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.paint_analyzer = PaintAnalyzer()
        self.setup_handlers()
        logger.info("✅ Bot initialized successfully!")
    
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def start_handler(message):
            self.handle_start(message)
        
        @self.bot.message_handler(regexp=r'https?://(www\.)?avito\.ru/.*')
        def avito_url_handler(message):
            self.handle_avito_url(message)
        
        @self.bot.message_handler(regexp=r'https?://(www\.)?drom\.ru/.*')
        def drom_url_handler(message):
            self.handle_drom_url(message)
        
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

Ваш помощник для анализа объявлений с:
• 🅰️ Авито
• 🇩 Drom.ru

*Что я анализирую:*
• 📊 Основные параметры авто
• 💰 Адекватность цены  
• 🎨 Состояние ЛКП по фото
• 📸 Качество фотографий

*Как использовать:*
Просто отправьте ссылку на объявление!

Нажмите кнопку ниже чтобы начать! 👇
        """
        
        self.bot.send_message(
            chat_id,
            welcome_text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    def handle_avito_url(self, message):
        """Обработка ссылок с Авито"""
        chat_id = message.chat.id
        url = message.text
        
        logger.info(f"🔗 Received Avito URL: {url}")
        
        try:
            status_msg = self.bot.send_message(
                chat_id, 
                "🔍 *Анализирую объявление с Авито...*", 
                parse_mode='Markdown'
            )
            
            self.bot.edit_message_text(
                "📦 *Получаю данные...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            ad_data = self.parse_avito_ad(url)
            
            if not ad_data:
                raise Exception("Не удалось получить данные объявления")
            
            self.bot.edit_message_text(
                "📊 *Анализирую параметры...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            analysis = self.analyze_ad(ad_data)
            
            self.bot.edit_message_text(
                "🎨 *Анализирую ЛКП по фото...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            # Анализ ЛКП
            paint_analysis = self.paint_analyzer.analyze_paint_from_urls(ad_data['images'])
            analysis['paint_analysis'] = paint_analysis
            
            self.bot.edit_message_text(
                "📝 *Формирую отчет...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            report = self.generate_report(ad_data, analysis)
            
            self.bot.edit_message_text(
                report,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Avito analysis completed: {url}")
            
        except Exception as e:
            logger.error(f"❌ Avito analysis failed: {e}")
            error_msg = f"❌ *Ошибка анализа Авито:* {str(e)}"
            try:
                self.bot.edit_message_text(
                    error_msg,
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
            except:
                self.bot.send_message(chat_id, error_msg, parse_mode='Markdown')
    
    def handle_drom_url(self, message):
        """Обработка ссылок с Drom.ru"""
        chat_id = message.chat.id
        url = message.text
        
        logger.info(f"🔗 Received Drom URL: {url}")
        
        try:
            status_msg = self.bot.send_message(
                chat_id, 
                "🔍 *Анализирую объявление с Drom...*", 
                parse_mode='Markdown'
            )
            
            self.bot.edit_message_text(
                "📦 *Получаю данные...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            ad_data = self.parse_drom_ad(url)
            
            if not ad_data:
                raise Exception("Не удалось получить данные объявления")
            
            self.bot.edit_message_text(
                "📊 *Анализирую параметры...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            analysis = self.analyze_ad(ad_data)
            
            self.bot.edit_message_text(
                "🎨 *Анализирую ЛКП по фото...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            # Анализ ЛКП
            paint_analysis = self.paint_analyzer.analyze_paint_from_urls(ad_data['images'])
            analysis['paint_analysis'] = paint_analysis
            
            self.bot.edit_message_text(
                "📝 *Формирую отчет...*",
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            report = self.generate_report(ad_data, analysis)
            
            self.bot.edit_message_text(
                report,
                chat_id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Drom analysis completed: {url}")
            
        except Exception as e:
            logger.error(f"❌ Drom analysis failed: {e}")
            error_msg = f"❌ *Ошибка анализа Drom:* {str(e)}"
            try:
                self.bot.edit_message_text(
                    error_msg,
                    chat_id,
                    status_msg.message_id,
                    parse_mode='Markdown'
                )
            except:
                self.bot.send_message(chat_id, error_msg, parse_mode='Markdown')
    
    def parse_avito_ad(self, url):
        """Парсинг объявления с Авито"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Заголовок
            title = self.extract_avito_title(soup)
            # Цена
            price = self.extract_avito_price(soup, response.text)
            # Фотографии
            images = self.extract_avito_images(soup)
            # Год
            year = self.extract_year(title)
            # Регион
            region = self.extract_avito_region(url)
            
            return {
                'title': title,
                'price': price,
                'year': year,
                'region': region,
                'image_count': len(images),
                'images': images,
                'url': url,
                'source': 'avito'
            }
            
        except Exception as e:
            logger.error(f"❌ Avito parsing failed: {e}")
            return None
    
    def parse_drom_ad(self, url):
        """Парсинг объявления с Drom.ru"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Заголовок
            title = self.extract_drom_title(soup)
            # Цена
            price = self.extract_drom_price(soup, response.text)
            # Фотографии
            images = self.extract_drom_images(soup)
            # Год
            year = self.extract_drom_year(soup, title)
            # Регион
            region = self.extract_drom_region(soup)
            
            return {
                'title': title,
                'price': price,
                'year': year,
                'region': region,
                'image_count': len(images),
                'images': images,
                'url': url,
                'source': 'drom'
            }
            
        except Exception as e:
            logger.error(f"❌ Drom parsing failed: {e}")
            return None
    
    def extract_avito_title(self, soup):
        """Извлечение заголовка с Авито"""
        try:
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
            
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                return meta_title['content']
            
            page_title = soup.find('title')
            if page_title:
                return page_title.get_text(strip=True)
            
            return "Неизвестная модель"
            
        except Exception as e:
            logger.error(f"Avito title error: {e}")
            return "Неизвестная модель"
    
    def extract_drom_title(self, soup):
        """Извлечение заголовка с Drom"""
        try:
            selectors = [
                'h1[class*="title"]',
                '.css-1tjirrw',
                'h1',
                '[data-ftid="component_ad_title"]'
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element and element.get_text(strip=True):
                    return element.get_text(strip=True)
            
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                return meta_title['content']
            
            page_title = soup.find('title')
            if page_title:
                return page_title.get_text(strip=True)
            
            return "Неизвестная модель"
            
        except Exception as e:
            logger.error(f"Drom title error: {e}")
            return "Неизвестная модель"
    
    def extract_avito_price(self, soup, page_text):
        """Извлечение цены с Авито"""
        try:
            price_selectors = [
                'meta[itemprop="price"]',
                'span[data-marker="item-view/item-price"]',
                '[data-marker="item-view/item-price"]',
                '.js-item-price',
                '.price-value',
            ]
            
            for selector in price_selectors:
                element = soup.select_one(selector)
                if element:
                    if element.get('content'):
                        price_str = element['content']
                        if price_str.isdigit():
                            return int(price_str)
                    
                    price_text = element.get_text(strip=True)
                    numbers = re.findall(r'\d+', price_text.replace(' ', ''))
                    if numbers:
                        return int(''.join(numbers))
            
            # Поиск в JSON-LD
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    if 'offers' in data and 'price' in data['offers']:
                        return int(data['offers']['price'])
                except:
                    pass
            
            # Поиск в тексте страницы
            price_patterns = [
                r'"price":\s*"(\d+)"',
                r'"price":\s*(\d+)',
                r'itemprop="price".*?content="(\d+)"',
            ]
            
            for pattern in price_patterns:
                matches = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                if matches:
                    price_str = matches.group(1).replace(' ', '')
                    if price_str.isdigit():
                        return int(price_str)
            
            return 0
            
        except Exception as e:
            logger.error(f"Avito price error: {e}")
            return 0
    
    def extract_drom_price(self, soup, page_text):
        """Извлечение цены с Drom"""
        try:
            price_selectors = [
                '[data-ftid="component_price"]',
                '.css-1dv8a3k',
                '.css-1v9f1fg',
                '[class*="price"]'
            ]
            
            for selector in price_selectors:
                element = soup.select_one(selector)
                if element:
                    price_text = element.get_text(strip=True)
                    numbers = re.findall(r'\d+', price_text.replace(' ', ''))
                    if numbers:
                        return int(''.join(numbers))
            
            # Поиск в тексте страницы
            price_patterns = [
                r'"price":\s*"(\d+)"',
                r'"price":\s*(\d+)',
                r'цена.*?(\d[\d\s]*)\s*₽',
            ]
            
            for pattern in price_patterns:
                matches = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                if matches:
                    price_str = matches.group(1).replace(' ', '')
                    if price_str.isdigit():
                        return int(price_str)
            
            return 0
            
        except Exception as e:
            logger.error(f"Drom price error: {e}")
            return 0
    
    def extract_avito_images(self, soup):
        """Извлечение изображений с Авито"""
        try:
            images = []
            
            img_selectors = [
                'img[data-src]',
                'img[src*="avito"]',
                '.gallery-img-cover img',
                '[data-marker="image-frame/image"]',
            ]
            
            for selector in img_selectors:
                img_elements = soup.select(selector)
                for img in img_elements[:10]:
                    src = img.get('data-src') or img.get('src')
                    if src and src.startswith('http'):
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
            logger.error(f"Avito images error: {e}")
            return []
    
    def extract_drom_images(self, soup):
        """Извлечение изображений с Drom"""
        try:
            images = []
            
            img_selectors = [
                'img[src*="drom"]',
                '.css-1bm2a1l img',
                '.b-album__item img',
                '[data-ftid="component_gallery_image"]'
            ]
            
            for selector in img_selectors:
                img_elements = soup.select(selector)
                for img in img_elements[:10]:
                    src = img.get('src')
                    if src and src.startswith('http'):
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
            logger.error(f"Drom images error: {e}")
            return []
    
    def extract_year(self, title):
        """Извлечение года из заголовка"""
        try:
            year_match = re.search(r'\b(19|20)\d{2}\b', title)
            return int(year_match.group()) if year_match else 2020
        except:
            return 2020
    
    def extract_drom_year(self, soup, title):
        """Извлечение года с Drom"""
        try:
            # Сначала пробуем из заголовка
            year_match = re.search(r'\b(19|20)\d{2}\b', title)
            if year_match:
                return int(year_match.group())
            
            # Ищем в характеристиках
            year_selectors = [
                '[data-ftid="component_inline-param"]',
                '.css-1ei9tni',
                '[class*="year"]'
            ]
            
            for selector in year_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text()
                    year_match = re.search(r'\b(19|20)\d{2}\b', text)
                    if year_match:
                        return int(year_match.group())
            
            return 2020
            
        except:
            return 2020
    
    def extract_avito_region(self, url):
        """Извлечение региона из URL Авито"""
        try:
            match = re.search(r'avito\.ru/([^/]+)', url)
            if match:
                region = match.group(1)
                region_map = {
                    'moskva': 'Москва',
                    'sankt-peterburg': 'Санкт-Петербург',
                    'spb': 'Санкт-Петербург',
                    'novosibirsk': 'Новосибирск',
                    'ekaterinburg': 'Екатеринбург',
                    'kazan': 'Казань',
                }
                return region_map.get(region, region.replace('-', ' ').title())
            return "Неизвестно"
        except:
            return "Неизвестно"
    
    def extract_drom_region(self, soup):
        """Извлечение региона с Drom"""
        try:
            region_selectors = [
                '[data-ftid="component_seller_location"]',
                '.css-1l12n0z',
                '[class*="location"]'
            ]
            
            for selector in region_selectors:
                element = soup.select_one(selector)
                if element:
                    region_text = element.get_text(strip=True)
                    if region_text:
                        return region_text
            
            return "Неизвестно"
        except:
            return "Неизвестно"
    
    def analyze_ad(self, ad_data):
        """Анализ объявления"""
        analysis = {
            'price_analysis': self.analyze_price(ad_data['price']),
            'photo_analysis': self.analyze_photos(ad_data['image_count']),
            'year_analysis': self.analyze_year(ad_data['year']),
            'recommendations': []
        }
        
        recommendations = self.generate_recommendations(ad_data, analysis)
        analysis['recommendations'] = recommendations
        
        analysis['overall_score'] = self.calculate_overall_score(ad_data, analysis)
        
        return analysis
    
    def analyze_price(self, price):
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
        if image_count == 0:
            return {'emoji': '❌', 'text': 'Нет фото', 'score': 1}
        elif image_count < 3:
            return {'emoji': '⚠️', 'text': 'Мало фото', 'score': 5}
        elif image_count < 6:
            return {'emoji': '✅', 'text': 'Достаточно', 'score': 8}
        else:
            return {'emoji': '📸', 'text': 'Много фото', 'score': 9}
    
    def analyze_year(self, year):
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
        scores = [
            analysis['price_analysis']['score'],
            analysis['photo_analysis']['score'],
            analysis['year_analysis']['score']
        ]
        
        return round(sum(scores) / len(scores))
    
    def generate_recommendations(self, ad_data, analysis):
        recommendations = []
        
        if ad_data['image_count'] == 0:
            recommendations.append("❌ *Нет фотографий* - обязательно запросите у продавца")
        elif ad_data['image_count'] < 3:
            recommendations.append("⚠️ *Мало фотографий* - попросите дополнительные фото")
        
        if ad_data['price'] == 0:
            recommendations.append("❓ *Цена не указана* - уточните стоимость")
        elif ad_data['price'] < 100000:
            recommendations.append("🚨 *Подозрительно низкая цена* - будьте осторожны")
        
        if 2024 - ad_data['year'] > 15:
            recommendations.append("🕰️ *Автомобиль старше 15 лет* - проверьте техническое состояние")
        
        if not recommendations:
            recommendations.append("✅ *Объявление выглядит нормально* - можно договариваться о осмотре")
        
        return recommendations
    
    def generate_report(self, ad_data, analysis):
        source_emoji = "🅰️" if ad_data['source'] == 'avito' else "🇩"
        paint_analysis = analysis.get('paint_analysis', {})
        
        report = f"""
{source_emoji} *{ad_data['title']}*

💰 *Цена:* {ad_data['price']:,} руб. {analysis['price_analysis']['emoji']}
📅 *Год:* {ad_data['year']} {analysis['year_analysis']['emoji']}
📍 *Регион:* {ad_data['region']}
📸 *Фотографии:* {ad_data['image_count']} {analysis['photo_analysis']['emoji']}

⭐ *Общая оценка:* {analysis['overall_score']}/10

🎨 *Анализ ЛКП:* {paint_analysis.get('score', 0)}/100 {paint_analysis.get('emoji', '❓')}
• Состояние: {paint_analysis.get('condition', 'не определено')}
• {paint_analysis.get('message', 'Анализ не выполнен')}

📊 *Детальный анализ:*
• Цена: {analysis['price_analysis']['text']}
• Фото: {analysis['photo_analysis']['text']}
• Возраст: {analysis['year_analysis']['text']}

💡 *Рекомендации:*
"""
        
        for rec in analysis['recommendations']:
            report += f"• {rec}\n"
        
        # Добавляем рекомендации по ЛКП
        paint_score = paint_analysis.get('score', 0)
        if paint_score > 0:
            if paint_score < 40:
                report += "• 🎨 *Состояние ЛКП плохое* - возможны царапины и дефекты\n"
            elif paint_score < 70:
                report += "• 🎨 *Состояние ЛКП среднее* - рекомендуется осмотр\n"
            else:
                report += "• 🎨 *Состояние ЛКП хорошее* - по фото выглядит отлично\n"
        
        report += f"""
🔍 *Советы по осмотру:*
• Всегда осматривайте автомобиль лично
• Проверяйте документы и VIN
• Сделайте тест-драйв
• Проверьте историю через онлайн-сервисы
• Особое внимание уделите состоянию кузова

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
                "Отправьте ссылку на объявление:\n\n*Авито:*\n`https://www.avito.ru/...`\n\n*Drom:*\n`https://auto.drom.ru/...`",
                parse_mode='Markdown'
            )
        
        elif text == 'ℹ️ Помощь':
            help_text = """
🤖 *AutoInspect Bot - Помощь*

*Поддерживаемые площадки:*
• 🅰️ Авито (avito.ru)
• 🇩 Drom.ru (auto.drom.ru)

*Что я анализирую:*
• 📊 Основные параметры автомобиля
• 💰 Адекватность цены
• 🎨 Состояние ЛКП по фотографиям (компьютерное зрение)
• 📸 Наличие и качество фотографий
• 📅 Год выпуска и возраст автомобиля

*Как использовать:*
1. Отправьте ссылку на объявление
2. Я проанализирую все параметры
3. Вы получите подробный отчет с оценкой ЛКП

*Примеры ссылок:*
`https://www.avito.ru/moskva/avtomobili/...`
`https://auto.drom.ru/volkswagen/golf/...`

*Примечание:* Анализ ЛКП выполняется автоматически по фотографиям. Всегда проверяйте автомобиль лично!
            """
            self.bot.send_message(chat_id, help_text, parse_mode='Markdown')
        
        else:
            self.bot.send_message(
                chat_id,
                "Используйте кнопки ниже или отправьте ссылку на объявление с Авито или Drom 👇"
            )
    
    def run(self):
        """Запуск бота с обработкой ошибок"""
        logger.info("🚀 Starting AutoInspect Bot...")
        
        max_retries = 3
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Attempt {attempt + 1} to start bot...")
                self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
                break
            except Exception as e:
                logger.error(f"❌ Bot crashed on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"🕐 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("❌ All retry attempts failed. Bot stopped.")
                    raise

# Запуск приложения
if __name__ == "__main__":
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        logger.error("❌ BOT_TOKEN environment variable is not set!")
        exit(1)
    
    # Сброс webhook перед запуском
    reset_webhook(token)
    
    # Небольшая задержка для гарантии сброса webhook
    time.sleep(2)
    
    # Создаем и запускаем бота
    bot = SimpleAvitoBot(token)
    bot.run()
