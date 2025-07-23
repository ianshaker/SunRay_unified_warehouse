"""
Модуль для работы с данными Inter (Gamma)
Основан на логике из SunRay_Gamma
"""
import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем абсолютный путь к файлу каталога
script_dir = os.path.dirname(os.path.abspath(__file__))
CATALOG_FILE = os.path.join(script_dir, "catalog.json")

# Список разрешенных типов штор для завода Inter
ALLOWED_TYPES_INTER = [
    "Ткани рулонные",
    "Лента алюминиевая", 
    "Пластик 89 мм",
    "Алюминий 89 мм",
    "Дерево",
    "Ткани плиссе",
    "Ткани Комбо",
    "Ткани вертикальные 89 мм",
    "Ткани римские"
]

# Словари для отображения названий (из config.py SunRay_Gamma)
FABRIC_TYPE_DISPLAY_NAMES = {
    'рулонные ткани': 'Ткани рулонные',
    'комбо ткани': 'Ткани Комбо',
    'вертикальные ткани': 'Ткани вертикальные 89 мм',
    'римские шторы': 'Ткани римские',
    'лента алюминиевая': 'Лента алюминиевая',
    'пластик 89 мм': 'Пластик 89 мм',
    'дерево': 'Дерево',
    'ткани плиссе': 'Ткани плиссе'
}

CATEGORY_DISPLAY_NAMES = FABRIC_TYPE_DISPLAY_NAMES

FABRIC_CATEGORIES = {
    'Рулонные ткани': {
        'emoji': '🎞️',
        'description': 'Ткани для рулонных штор'
    },
    'Вертикальные ткани': {
        'emoji': '📏',
        'description': 'Ткани для вертикальных жалюзи'
    },
    'Римские ткани': {
        'emoji': '🏛️',
        'description': 'Ткани для римских штор'
    },
    'Комбо ткани': {
        'emoji': '🔄',
        'description': 'Комбинированные ткани'
    }
}

# Глобальные переменные для хранения данных
_catalog_data = None
_category_map = {}  # {short_id: category_name}
_fabric_map = {}    # {short_id: (category_name, fabric_name)}
_item_map = {}      # {short_id: (category_name, fabric_name, item_index, item)}

def load_catalog() -> Dict[str, Any]:
    """Загружает каталог из JSON файла"""
    global _catalog_data
    
    if _catalog_data is not None:
        return _catalog_data
    
    try:
        with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Проверяем новый формат с метаданными
            if 'catalog' in data and 'metadata' in data:
                catalog = data['catalog']
                logger.info(f"Каталог Inter загружен от {data['metadata'].get('updated_at', 'неизвестно')}")
                logger.info(f"Категорий: {data['metadata'].get('total_categories', 0)}, "
                          f"товаров: {data['metadata'].get('total_items', 0)}")
                
                # Преобразуем словарь в список категорий для единообразия
                if isinstance(catalog, dict):
                    categories_list = []
                    for main_category, subcategories in catalog.items():
                        for subcategory_name, items in subcategories.items():
                            category_data = {
                                'name': subcategory_name,
                                'section': 'Да',
                                'items': items,
                                'main_category': main_category
                            }
                            categories_list.append(category_data)
                    _catalog_data = categories_list
                    _create_mappings()
                    return categories_list
                else:
                    _catalog_data = catalog
                    _create_mappings()
                    return catalog
            else:
                # Старый формат без метаданных
                logger.warning("Загружен каталог в старом формате")
                _catalog_data = data
                _create_mappings()
                return data
                    
    except FileNotFoundError:
        logger.error(f"Файл каталога {CATALOG_FILE} не найден")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки каталога: {e}")
        return {}

def _create_mappings():
    """Создает маппинг коротких ID для категорий, полотен и товаров"""
    global _category_map, _fabric_map, _item_map
    
    _category_map.clear()
    _fabric_map.clear()
    _item_map.clear()
    
    catalog = _catalog_data
    if isinstance(catalog, list):
        # Новая структура - список категорий
        visible_cat_idx = 0  # Счетчик для видимых категорий
        for category in catalog:
            category_name = category.get('name', 'Без названия')
            section = category.get('section', 'Нет')
            items = category.get('items', [])
            
            # Создаем маппинг только для категорий с section='Да' и товарами
            # И только для разрешенных типов Inter
            if len(items) > 0 and section == 'Да' and category_name.strip() in ALLOWED_TYPES_INTER:
                cat_id = f"c{visible_cat_idx}"
                _category_map[cat_id] = category_name
                
                # Группируем товары по названию полотна
                fabric_groups = {}
                for item in items:
                    item_name = item.get('name', '')
                    if '`' in item_name:
                        fabric_part = item_name.split('`')[1]
                        if fabric_part.endswith('`'):
                            fabric_part = fabric_part[:-1]
                        words = fabric_part.split()
                        if len(words) >= 2:
                            fabric_name = words[0]
                        else:
                            fabric_name = fabric_part
                    else:
                        fabric_name = item_name
                    
                    if fabric_name not in fabric_groups:
                        fabric_groups[fabric_name] = []
                    fabric_groups[fabric_name].append(item)
                
                # Создаем ID для полотен
                for fab_idx, (fabric_name, fabric_items) in enumerate(fabric_groups.items()):
                    fab_id = f"f{visible_cat_idx}_{fab_idx}"
                    _fabric_map[fab_id] = (category_name, fabric_name)
                    
                    # Создаем ID для товаров
                    for item_idx, item in enumerate(fabric_items):
                        item_id = f"i{visible_cat_idx}_{fab_idx}_{item_idx}"
                        _item_map[item_id] = (category_name, fabric_name, item_idx, item)
                
                visible_cat_idx += 1  # Увеличиваем счетчик только для видимых категорий

def get_fabric_types() -> List[str]:
    """Возвращает список типов тканей (основных категорий)"""
    catalog = load_catalog()
    
    if isinstance(catalog, list):
        # Новая структура - список категорий
        visible_categories = []
        for category in catalog:
            category_name = category.get('name', 'Без названия')
            section = category.get('section', 'Нет')
            items = category.get('items', [])
            
            # Показываем только категории с section='Да' и с товарами
            if len(items) > 0 and section == 'Да':
                # Фильтруем по разрешенным типам для Inter
                if category_name.strip() in ALLOWED_TYPES_INTER:
                    visible_categories.append(category_name)
        
        return visible_categories
    else:
        # Старая структура - словарь
        all_categories = list(catalog.keys())
        # Фильтруем по разрешенным типам для Inter
        filtered_categories = [cat for cat in all_categories if cat.strip() in ALLOWED_TYPES_INTER]
        return filtered_categories

def get_fabric_categories(fabric_type: str) -> List[str]:
    """Возвращает список подкатегорий для указанного типа ткани"""
    # В новой структуре fabric_type уже является подкатегорией
    # Возвращаем список полотен как "категории"
    fabric_groups = get_fabric_groups(fabric_type)
    return list(fabric_groups.keys())

def get_fabric_groups(fabric_type: str) -> Dict[str, List[Dict]]:
    """Группирует ткани по названиям полотен для указанного типа"""
    catalog = load_catalog()
    
    if isinstance(catalog, list):
        # Новая структура - список категорий
        category = next((cat for cat in catalog if cat.get('name') == fabric_type), None)
        if category:
            items = category.get('items', [])
            
            # Группируем товары по названию полотна
            fabric_groups = {}
            for item in items:
                item_name = item.get('name', '')
                if '`' in item_name:
                    fabric_part = item_name.split('`')[1]
                    if fabric_part.endswith('`'):
                        fabric_part = fabric_part[:-1]
                    words = fabric_part.split()
                    if len(words) >= 2:
                        fabric_name = words[0]
                    else:
                        fabric_name = fabric_part
                else:
                    fabric_name = item_name
                
                if fabric_name not in fabric_groups:
                    fabric_groups[fabric_name] = []
                fabric_groups[fabric_name].append(item)
            
            return fabric_groups
    
    return {}

def get_fabric_colors(fabric_type: str, fabric_category: str, fabric_name: str) -> List[Dict]:
    """Возвращает список цветов для указанной ткани"""
    # В новой логике fabric_category не используется, fabric_name уже содержит нужную группу
    fabric_groups = get_fabric_groups(fabric_type)
    return fabric_groups.get(fabric_name, [])

def extract_color_from_name(fabric_name: str) -> str:
    """Извлекает цвет из названия ткани"""
    if '`' in fabric_name:
        fabric_part = fabric_name.split('`')[1]
        if fabric_part.endswith('`'):
            fabric_part = fabric_part[:-1]
        words = fabric_part.split()
        if len(words) >= 2:
            # Возвращаем все слова кроме первого как цвет
            return ' '.join(words[1:])
        else:
            return fabric_part
    return fabric_name

def get_availability_status(item: Dict) -> str:
    """Определяет статус наличия ткани"""
    availability_text = item.get('availability_text', 'Неизвестно')
    
    if availability_text == "Отсутствует":
        return "❌ Нет в наличии"
    elif availability_text == "Ограниченное количество":
        return "⚠️ Ограниченно"
    elif availability_text in ["Есть в наличии", "В наличии"]:
        return "✅ В наличии"
    else:
        return "❓ Статус неизвестен"

async def get_fabric_info(fabric_type: str, fabric_category: str, fabric_name: str, color: str) -> Optional[Dict]:
    """Получает информацию о конкретной ткани"""
    try:
        colors_data = get_fabric_colors(fabric_type, fabric_category, fabric_name)
        
        # Ищем ткань с указанным цветом
        for item in colors_data:
            item_color = extract_color_from_name(item.get('name', ''))
            if item_color.lower() == color.lower():
                return {
                    'name': item.get('name', ''),
                    'status': get_availability_status(item),
                    'availability_text': item.get('availability_text', 'Информация недоступна'),
                    'image_url': item.get('image', ''),
                    'fabric_type': fabric_type,
                    'id': item.get('id', '')
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о ткани: {e}")
        return None

def get_display_name(key: str, display_dict: Dict[str, str]) -> str:
    """Возвращает отображаемое название или исходное, если не найдено"""
    return display_dict.get(key.lower(), key)

def get_category_emoji(fabric_type: str) -> str:
    """Возвращает эмодзи для категории"""
    return FABRIC_CATEGORIES.get(fabric_type, {}).get('emoji', '📋')

def get_category_map() -> Dict[str, str]:
    """Возвращает маппинг категорий"""
    return _category_map.copy()

def get_fabric_map() -> Dict[str, Tuple[str, str]]:
    """Возвращает маппинг полотен"""
    return _fabric_map.copy()

def get_item_map() -> Dict[str, Tuple[str, str, int, Dict]]:
    """Возвращает маппинг товаров"""
    return _item_map.copy()
