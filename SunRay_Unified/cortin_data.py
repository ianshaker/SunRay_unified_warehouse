import json
import aiohttp
import ssl
import certifi
import asyncio
from typing import Dict, List, Optional
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import re

# Загружаем данные Cortin
def load_cortin_data():
    """Загружает данные о шторах и материалах Cortin"""
    try:
        with open("cortin_data/shutters.json", "r", encoding="utf-8") as f:
            shutters = json.load(f)
        
        with open("cortin_data/grouped_materials.json", "r", encoding="utf-8") as f:
            materials = json.load(f)
            
        return shutters, materials
    except Exception as e:
        print(f"Ошибка загрузки данных Cortin: {e}")
        return [], []

SHUTTERS, MATERIALS = load_cortin_data()

# ID категорий "День и ночь" для API запросов
# Используются все 4 ID одновременно, как в Amiga
CORTIN_DAY_NIGHT_CATEGORY_IDS = [
    "categoryId_for_proyom",      # День и ночь для проёма
    "categoryId_for_stvorka",     # День и ночь для створки  
    "categoryId_for_kasset",      # День и ночь кассетные
    "categoryId_for_petli"        # День и ночь на петлях
]

# Функция для получения актуального остатка ткани по имени с сайта
async def get_fabric_stock_online(material_name: str, category: str = "Римские шторы", product_type: str = "День-Ночь") -> Dict[str, str]:
    """Получает актуальный остаток ткани с сайта Cortin
    
    Args:
        material_name: Название материала
        category: Категория изделия (по умолчанию "Римские шторы")
        product_type: Тип изделия (по умолчанию "День-Ночь")
    """

    # Формируем URL с параметрами
    base_url = "https://sale.cortin.ru/mfg/stocks/materials"
    params = {
        'category': category,
        'type': product_type,
        'material': material_name
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://sale.cortin.ru/"
    }
    cookies = {
        "PHPSESSID": "00b6aa6c21e23940417baef694331a97",
        "_identity": "c76ce45b37b4ba9599e270e8b63a19af76abd5a5f7e3cf6eb960622d247712fba%3A2%3A%7Bi%3A0%3Bs%3A9%3A%22_identity%22%3Bi%3A1%3Bs%3A18%3A%22%5B495%2Cnull%2C2592000%5D%22%3B%7D",
        "_csrf": "bff7bcc2624607ab4fa752a55325441d95928650d8be8a7b47ce73d314515c5aa%3A2%3A%7Bi%3A0%3Bs%3A5%3A%22_csrf%22%3Bi%3A1%3Bs%3A32%3A%22oP7u8WuVy686bIW9vgcReRPXuASSzgfT%22%3B%7D"
    }
    
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Делаем запрос с параметрами
            async with session.get(base_url, headers=headers, cookies=cookies, params=params, timeout=15) as resp:

                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, "html.parser")
                    
                    # Улучшенная проверка авторизации
                    # Проверяем наличие формы авторизации
                    has_login_form = soup.find("input", {"type": "password"}) is not None
                    has_auth_action = soup.find("form", {"action": lambda x: x and "/site/login" in x if x else False}) is not None
                    
                    # Проверяем заголовок страницы
                    title = soup.find("title")
                    title_text = title.get_text().lower() if title else ""
                    has_auth_title = "авторизация" in title_text and "остатки" not in title_text
                    
                    # Если есть признаки неудачной авторизации
                    if has_login_form or has_auth_action or has_auth_title:
                        return {"availability": "❓ Нет данных (требуется авторизация)"}
                    
                    # Проверяем наличие данных о материалах
                    material_count = len(soup.find_all("tr", {"data-material": True}))
                    if material_count < 100:  # Если материалов слишком мало, возможно авторизация не прошла
                        return {"availability": "❓ Нет данных (требуется авторизация)"}
                    tr = soup.find("tr", {"data-material": material_name})
                    if tr:
                        tds = tr.find_all("td")
                        if tds:
                            # Остаток в последней ячейке
                            stock_text = tds[-1].get_text(strip=True)
                            # Извлекаем число
                            match = re.search(r"([\d\.,]+)", stock_text)
                            if match:
                                stock_amount = match.group(1)
                                return {"availability": get_availability_status(stock_amount)}
                    else:
                        # Если ткань не найдена, попробуем найти по частичному совпадению
                        all_rows = soup.find_all("tr", {"data-material": True})
                        for row in all_rows:
                            row_material = row.get("data-material", "")
                            if material_name.lower() in row_material.lower() or row_material.lower() in material_name.lower():
                                tds = row.find_all("td")
                                if tds:
                                    stock_text = tds[-1].get_text(strip=True)
                                    match = re.search(r"([\d\.,]+)", stock_text)
                                    if match:
                                        stock_amount = match.group(1)
                                        return {"availability": get_availability_status(stock_amount)}
                    
                    return {"availability": get_availability_status(None)}
    except Exception as e:
        print(f"Ошибка получения остатка для {material_name}: {e}")
        return {"availability": get_availability_status(None)}

def get_availability_status(stock_amount: Optional[str]) -> str:
    """Возвращает статус наличия товара"""
    if stock_amount is None:
        return "❓ Нет данных"
    
    try:
        amount = float(stock_amount.replace(',', '.'))
        if amount > 0:
            return f"✅ В наличии: {stock_amount} м"
        else:
            return "❌ Нет в наличии"
    except:
        return "❓ Нет данных"

def make_absolute_url(image_url: Optional[str]) -> Optional[str]:
    """Преобразует относительный URL в абсолютный"""
    if not image_url:
        return None
    
    if image_url.startswith('http'):
        return image_url
    
    if image_url.startswith('/'):
        return f"https://sale.cortin.ru{image_url}"
    
    return f"https://sale.cortin.ru/{image_url}"

def get_shutter_categories() -> List[str]:
    """Возвращает список категорий штор"""
    categories = []
    for shutter in SHUTTERS:
        if shutter.get('category') and shutter['category'] not in categories:
            categories.append(shutter['category'])
    return categories

def get_shutters_by_category(category: str) -> List[Dict]:
    """Возвращает шторы по категории"""
    for shutter in SHUTTERS:
        if shutter.get('category') == category:
            return shutter.get('items', [])
    return []

def get_fabric_categories() -> List[str]:
    """Возвращает список категорий тканей"""
    return [material['fabric'] for material in MATERIALS]

def get_fabric_variants(fabric_category: str) -> List[Dict]:
    """Возвращает варианты ткани по категории"""
    for material in MATERIALS:
        if material['fabric'] == fabric_category:
            return material.get('variants', [])
    return []

def find_variant_by_id(variant_id):
    """Находит вариант полотна по ID в grouped_materials.json"""
    try:
        variant_id = int(variant_id)
        with open('cortin_data/grouped_materials.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # data это массив объектов, каждый с полями fabric и variants
        for fabric_group in data:
            variants = fabric_group.get('variants', [])
            for variant in variants:
                if variant.get('id') == variant_id:
                    return variant
        
        return None
    except Exception as e:
        print(f"Ошибка при поиске варианта по ID {variant_id}: {e}")
        return None

def find_shutter_by_id(shutter_id) -> Optional[Dict]:
    """Находит штору по ID"""
    # Преобразуем в int если это строка
    try:
        shutter_id = int(shutter_id)
    except (ValueError, TypeError):
        return None
        
    for shutter in SHUTTERS:
        for item in shutter.get('items', []):
            if item.get('id') == shutter_id:
                return item
    return None

def get_all_fabric_names() -> List[str]:
    """Возвращает список всех названий полотен из всех категорий"""
    all_fabrics = []
    for material in MATERIALS:
        for variant in material.get('variants', []):
            fabric_name = variant.get('name', '')
            if fabric_name:
                all_fabrics.append(fabric_name)
    return sorted(all_fabrics)

def get_fabric_letters() -> List[str]:
    """Получает список уникальных первых букв типов тканей (только те буквы, для которых есть типы тканей)"""
    letters = set()
    for material in MATERIALS:
        fabric_type = material.get('fabric', '')
        if fabric_type:
            first_letter = fabric_type[0].upper()
            letters.add(first_letter)
    return sorted(list(letters))

def filter_fabrics_by_letter(letter: str) -> List[str]:
    """Фильтрует полотна по первой букве"""
    all_fabrics = get_all_fabric_names()
    filtered = []
    for fabric in all_fabrics:
        if fabric and fabric[0].upper() == letter.upper():
            filtered.append(fabric)
    return sorted(filtered)

def find_fabric_by_name(fabric_name: str) -> Optional[Dict]:
    """Находит полотно по названию"""
    for material in MATERIALS:
        for variant in material.get('variants', []):
            if variant.get('name') == fabric_name:
                return variant
    return None

def get_fabric_types_by_letter(letter: str) -> List[str]:
    """Получает типы тканей, начинающиеся с указанной буквы"""
    fabric_types = set()
    for material in MATERIALS:
        fabric_type = material.get('fabric', '')
        if fabric_type and fabric_type[0].upper() == letter.upper():
            fabric_types.add(fabric_type)
    return sorted(list(fabric_types))

def get_fabrics_by_type(fabric_type: str) -> List[Dict]:
    """Получает все полотна определенного типа"""
    for material in MATERIALS:
        if material.get('fabric') == fabric_type:
            return material.get('variants', [])
    return []