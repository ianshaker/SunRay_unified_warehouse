# amiga_data.py
"""
Данные и логика для работы с заводом Amiga
"""

import json
import logging
import os
import aiohttp
import ssl
import certifi
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Основные категории штор с их ID
CATEGORIES = {
    "Рулонные шторы": "rulon.json",
    "Рулонные шторы Зебра": "zebra.json", 
    "Шторы плиссе": "plisse.json",
    # "Шторы гофре": "gofre.json",  # Отключено по запросу
    "Горизонтальные алюминиевые": "horizontal_aluminum.json",
    "Горизонтальные деревянные": "horizontal_wood.json",
    "Вертикальные": "vertical.json",
    # "Бриз вертикальные": "breeze_vertical.json",  # Отключено по запросу
    # "Рулонные шторы Мираж": "mirage.json",  # Отключено по запросу
    "Портьеры и римские шторы": "curtains_roman.json"
}

# ID категорий для API
CATEGORY_IDS = {
    "Рулонные шторы": 1,
    "Рулонные шторы Зебра": 6,
    "Шторы плиссе": 15,
    # "Шторы гофре": 19,  # Отключено по запросу
    "Горизонтальные алюминиевые": 28,
    "Горизонтальные деревянные": 38,
    "Вертикальные": 43,
    # "Бриз вертикальные": 47,  # Отключено по запросу
    # "Рулонные шторы Мираж": 11,  # Отключено по запросу
    "Портьеры и римские шторы": 360
}

# ID моделей плиссе для API-запросов
PLISSE_MODEL_IDS = {
    "MIDI": 56,
    "MAXI": 113,
    "MINI": 53,
    "RUS": 223
}

# ID моделей гофре для API-запросов
GOFRE_MODEL_IDS = {
    "MIDI": 86,
    "MAXI": 230,
    "RUS": 224
}

def normalize_material_name(name: str) -> str:
    """Нормализует название материала для сравнения"""
    if not name:
        return ""
    
    # Приводим к нижнему регистру и убираем лишние пробелы
    normalized = name.lower().strip()
    
    # Убираем слово "зебра" если оно есть в начале
    if normalized.startswith("зебра "):
        normalized = normalized[6:]
    
    # Убираем слово "полоса" если оно есть в начале
    if normalized.startswith("полоса "):
        normalized = normalized[7:]
    
    return normalized

def get_availability_status(availability: int) -> str:
    """Возвращает статус наличия по числовому коду"""
    status_map = {
        2: "🟢 В наличии",
        1: "🟡 Мало",
        0: "🔴 Нет в наличии"
    }
    return status_map.get(availability, "❓ Неизвестно")

def make_absolute_url(image_url: str) -> str:
    """Преобразует относительный URL в абсолютный"""
    if not image_url:
        return None
    
    if image_url.startswith('http'):
        return image_url
    
    # Убираем начальный слеш если есть
    if image_url.startswith('/'):
        image_url = image_url[1:]
    
    return f"https://customizer.amigo.ru/{image_url}"

def load_json_data(filename: str) -> Optional[Dict]:
    """Загружает данные из JSON файла"""
    try:
        # Получаем абсолютный путь к директории скрипта
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(script_dir, "amiga_data", filename)
        if not os.path.exists(filepath):
            logger.warning(f"Файл {filepath} не найден")
            return None
            
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Ошибка загрузки {filename}: {e}")
        return None

def load_plisse_data(model: str) -> Optional[Dict]:
    """Загружает данные плиссе для конкретной модели"""
    try:
        # Получаем абсолютный путь к директории скрипта
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(script_dir, "amiga_data", "plisse", f"{model}.json")
        if not os.path.exists(filepath):
            logger.warning(f"Файл плиссе {filepath} не найден")
            return None
            
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)
            # Возвращаем полную структуру данных
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки плиссе {model}: {e}")
        return None

def load_gofre_data(model: str) -> Optional[Dict]:
    """Загружает данные гофре для конкретной модели"""
    try:
        # Получаем абсолютный путь к директории скрипта
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(script_dir, "amiga_data", "gofre", f"{model}.json")
        if not os.path.exists(filepath):
            logger.warning(f"Файл гофре {filepath} не найден")
            return None
            
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)
            # Возвращаем полную структуру данных
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки гофре {model}: {e}")
        return None

def get_all_plisse_models() -> List[str]:
    """Возвращает список всех доступных моделей плиссе"""
    return ["MIDI", "MAXI", "MINI", "RUS"]

def get_all_gofre_models() -> List[str]:
    """Возвращает список всех доступных моделей гофре"""
    return ["MIDI", "MAXI", "RUS"]

async def make_api_request(category: str, fabric: str, variant: str, model_id: int = None) -> Optional[Dict]:
    """Выполняет API запрос к серверу Amiga"""
    logger.info(f"API запрос: category={category}, fabric={fabric}, variant={variant}")
    
    try:
        if model_id is None:
            model_id = CATEGORY_IDS.get(category, 1)
        
        url = f"https://customizer.amigo.ru/api/models/{model_id}/materials"
        logger.info(f"API URL: {url} (model_id={model_id})")

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"API ответ получен, количество материалов: {len(data)}")
                    
                    if not data:
                        logger.warning(f"API ответ пустой! URL: {url}")
                        return None

                    # Ищем совпадение по названию
                    search_name = f"{fabric} {variant}".strip().lower()
                    search_name_norm = normalize_material_name(search_name)
                    logger.info(f"Ищем совпадение: {search_name}")

                    # Точное совпадение
                    result = next(
                        (item for item in data if normalize_material_name(item.get("material", {}).get("name", "")) == search_name_norm),
                        None
                    )

                    if result:
                        logger.info(f"Найдено точное совпадение: {result['material']['name']}")
                        return result
                    else:
                        # Частичное совпадение по варианту
                        variant_norm = normalize_material_name(variant)
                        fabric_norm = normalize_material_name(fabric)
                        
                        partial = next(
                            (item for item in data if variant_norm in normalize_material_name(item.get("material", {}).get("name", ""))),
                            None
                        )
                        
                        if not partial:
                            # Пробуем по ткани
                            partial = next(
                                (item for item in data if fabric_norm in normalize_material_name(item.get("material", {}).get("name", ""))),
                                None
                            )
                        
                        if partial:
                            logger.warning(f"Найдено частичное совпадение: {partial['material']['name']}")
                            return partial
                        
                        logger.warning("Материал не найден в API")
                        return None
                else:
                    logger.error(f"API ошибка: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Ошибка API запроса: {e}")
        return None
