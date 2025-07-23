import asyncio
import json
import logging
import os
import aiohttp
import ssl
import certifi
import re
from typing import Dict, List, Optional
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from urllib.parse import urlencode
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "https://customizer.amigo.ru")

if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в файле .env")
    print("📝 Инструкция:")
    print("1. Откройте файл .env")
    print("2. Замените 'your_bot_token_here' на реальный токен от @BotFather")
    print("3. Сохраните файл и запустите бота снова")
    exit(1)

if BOT_TOKEN == "your_bot_token_here":
    print("❌ Ошибка: Необходимо настроить токен бота")
    print("📝 Инструкция:")
    print("1. Получите токен у @BotFather в Telegram")
    print("2. Откройте файл .env")
    print("3. Замените 'your_bot_token_here' на ваш токен")
    print("4. Сохраните файл и запустите бота снова")
    exit(1)

# Состояния FSM
class MainStates(StatesGroup):
    welcome_screen = State()
    choosing_factory = State()

class AmigaStates(StatesGroup):
    choosing_category = State()
    choosing_gofre_model = State()
    choosing_letter = State()
    choosing_fabric = State()
    choosing_variant = State()
    final_selection = State()

class CortinStates(StatesGroup):
    choosing_letter = State()
    choosing_fabric_type = State()
    choosing_fabric = State()
    final_selection = State()

class InterStates(StatesGroup):
    choosing_fabric_type = State()
    choosing_letter = State()
    choosing_fabric_name = State()
    choosing_color = State()
    final_selection = State()

try:
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
except Exception as e:
    print(f"❌ Ошибка инициализации бота: {e}")
    print("📝 Проверьте правильность токена в файле .env")
    exit(1)

# Константы для пагинации
ITEMS_PER_PAGE = 10

# Множество для отслеживания пользователей, которые уже видели приветствие
seen_users = set()

# Импорт данных Amigo
from amiga_data import CATEGORIES, CATEGORY_IDS, PLISSE_MODEL_IDS

# Импорт данных Cortin
from cortin_data import SHUTTERS, MATERIALS

# Импорт данных Inter
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import inter_data

def create_welcome_keyboard():
    """Создает клавиатуру экрана приветствия"""
    keyboard = [
        [InlineKeyboardButton(text="🚀 Начать", callback_data="start_bot")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_factory_keyboard():
    """Создает клавиатуру выбора завода"""
    keyboard = [
        [InlineKeyboardButton(text="🏭 Amigo", callback_data="factory_amiga")],
        [InlineKeyboardButton(text="🏭 Cortin", callback_data="factory_cortin")],
        [InlineKeyboardButton(text="🏭 Inter", callback_data="factory_inter")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_cortin_fabric_types_keyboard(fabric_types: List[str]):
    """Создает клавиатуру с типами тканей Cortin для выбранной буквы"""
    keyboard = []
    
    # Добавляем кнопки типов тканей
    for i, fabric_type in enumerate(fabric_types):
        keyboard.append([InlineKeyboardButton(
            text=fabric_type,
            callback_data=f"cortin_fabric_type_{i}"
        )])
    
    # Кнопки возврата
    keyboard.append([
        InlineKeyboardButton(text="🔙 К выбору буквы", callback_data="cortin_back_to_letters"),
    ])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_cortin_fabric_by_type_keyboard(fabrics: List[Dict], page: int = 0):
    """Создает клавиатуру с полотнами Cortin определенного типа (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabrics[start_idx:end_idx]
    
    # Добавляем кнопки полотен
    for i, fabric in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        fabric_name = fabric.get('name', 'Без названия')
        keyboard.append([InlineKeyboardButton(
            text=fabric_name,
            callback_data=f"cortin_fabric_final_{fabric.get('id', 0)}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    total_pages = (len(fabrics) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"cortin_fabric_type_page_{page - 1}"
        ))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"cortin_fabric_type_page_{page + 1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопки возврата
    keyboard.append([
        InlineKeyboardButton(text="🔙 К выбору типа ткани", callback_data="cortin_back_to_fabric_types"),
    ])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_categories_keyboard():
    """Создает клавиатуру с категориями штор Amigo"""
    keyboard = []
    categories_list = list(CATEGORIES.keys())
    
    # Группируем по 2 кнопки в строке
    for i in range(0, len(categories_list), 2):
        row = []
        for j in range(i, min(i + 2, len(categories_list))):
            category = categories_list[j]
            # Сокращаем длинные названия для кнопок
            short_name = get_short_category_name(category)
            row.append(InlineKeyboardButton(
                text=short_name,
                callback_data=f"amiga_cat_{j}"
            ))
        keyboard.append(row)
    
    # Кнопка возврата к выбору завода
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору завода",
        callback_data="back_to_factory"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_short_category_name(category: str) -> str:
    """Получает сокращенное название категории для кнопки"""
    short_names = {
        "Рулонные шторы": "Рулонные шторы",
        "Рулонные шторы Зебра": "Зебра",
        "Шторы плиссе": "Плиссе", 
        # "Шторы гофре": "Гофре",  # Отключено по запросу
        "Горизонтальные алюминиевые": "Гориз. алюмин.",
        "Горизонтальные деревянные": "Гориз. деревян.",
        "Вертикальные": "Вертикальные",
        # "Бриз вертикальные": "Бриз вертикальные",  # Отключено по запросу
        # "Рулонные шторы Мираж": "Мираж",  # Отключено по запросу
        "Портьеры и римские шторы": "Портьеры/римские"
    }
    return short_names.get(category, category)

def create_fabric_keyboard(fabrics: List[str], page: int = 0):
    """Создает клавиатуру с полотнами (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabrics[start_idx:end_idx]
    
    # Добавляем кнопки полотен
    for i, fabric in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=fabric,
            callback_data=f"amiga_fabric_{fabric_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"amiga_fabric_page_{page-1}"
        ))
    
    if end_idx < len(fabrics):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее", 
            callback_data=f"amiga_fabric_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к категориям
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору категории",
        callback_data="amiga_back_to_categories"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_variants_keyboard(variants: List[str], page: int = 0):
    """Создает клавиатуру с вариантами полотна (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_variants = variants[start_idx:end_idx]
    
    # Добавляем кнопки вариантов
    for i, variant in enumerate(page_variants):
        variant_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=variant,
            callback_data=f"amiga_variant_{variant_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"amiga_variant_page_{page-1}"
        ))
    
    if end_idx < len(variants):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"amiga_variant_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к полотнам
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору полотна",
        callback_data="amiga_back_to_fabrics"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_final_keyboard():
    """Создает финальную клавиатуру для Amigo"""
    keyboard = [
        [InlineKeyboardButton(text="🔙 К выбору варианта", callback_data="amiga_back_to_variants")],
        [InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_gofre_model_keyboard():
    """Создает клавиатуру выбора модели гофре"""
    keyboard = [
        [InlineKeyboardButton(text="MAXI", callback_data="gofre_model_MAXI")],
        [InlineKeyboardButton(text="MIDI", callback_data="gofre_model_MIDI")],
        [InlineKeyboardButton(text="RUS", callback_data="gofre_model_RUS")],
        [InlineKeyboardButton(text="🔙 К выбору категории", callback_data="amiga_back_to_categories")],
        [InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_gofre_fabric_keyboard(fabrics: List[str], page: int = 0):
    """Создает клавиатуру с полотнами гофре (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabrics[start_idx:end_idx]
    
    # Добавляем кнопки полотен
    for i, fabric in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=fabric,
            callback_data=f"amiga_fabric_{fabric_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"amiga_fabric_page_{page-1}"
        ))
    
    if end_idx < len(fabrics):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее", 
            callback_data=f"amiga_fabric_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к выбору модели гофре
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору модели",
        callback_data="amiga_back_to_gofre_models"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Функции для создания клавиатур Cortin
def create_cortin_letters_keyboard():
    """Создает клавиатуру с буквами алфавита для Cortin"""
    from cortin_data import get_fabric_letters
    letters = get_fabric_letters()
    
    keyboard = []
    
    # Группируем буквы по 5 в строке для компактности
    for i in range(0, len(letters), 5):
        row = []
        for j in range(i, min(i + 5, len(letters))):
            letter = letters[j]
            row.append(InlineKeyboardButton(
                text=letter,
                callback_data=f"cortin_letter_{letter}"
            ))
        keyboard.append(row)
    
    # Кнопка возврата к выбору завода
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору завода",
        callback_data="back_to_factory"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_cortin_fabric_by_letter_keyboard(fabrics: List[str], page: int = 0):
    """Создает клавиатуру с полотнами Cortin на определенную букву (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabrics[start_idx:end_idx]
    
    # Добавляем кнопки полотен
    for i, fabric in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=fabric,
            callback_data=f"cortin_fabric_{fabric_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    total_pages = (len(fabrics) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"cortin_fabric_page_{page - 1}"
        ))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"cortin_fabric_page_{page + 1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопки возврата
    keyboard.append([
        InlineKeyboardButton(text="🔙 К выбору буквы", callback_data="cortin_back_to_letters"),
    ])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_cortin_final_keyboard():
    """Создает финальную клавиатуру для Cortin"""
    keyboard = [
        [InlineKeyboardButton(text="🔙 К выбору полотна", callback_data="cortin_back_to_fabric_types")],
        [InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_cortin_shutter_categories_keyboard():
    """Создает клавиатуру с категориями штор Cortin (старая функция, оставлена для совместимости)"""
    from cortin_data import get_shutter_categories
    categories = get_shutter_categories()
    
    keyboard = []
    for i, category in enumerate(categories):
        keyboard.append([InlineKeyboardButton(
            text=category,
            callback_data=f"cortin_shutter_cat_{i}"
        )])
    
    # Кнопка возврата к выбору завода
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору завода",
        callback_data="back_to_factory"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Функции для создания клавиатур Inter
def create_inter_fabric_types_keyboard():
    """Создает клавиатуру с типами штор Inter"""
    fabric_types = inter_data.get_fabric_types()
    
    keyboard = []
    for i, fabric_type in enumerate(fabric_types):
        display_name = inter_data.get_display_name(fabric_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
        keyboard.append([InlineKeyboardButton(
            text=display_name,
            callback_data=f"inter_type_{i}"
        )])
    
    # Кнопка возврата к выбору завода
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору завода",
        callback_data="back_to_factory"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_inter_fabric_categories_keyboard(fabric_type: str, page: int = 0):
    """Создает клавиатуру с названиями полотен Inter (в новой логике это полотна, а не категории)"""
    fabric_groups = inter_data.get_fabric_groups(fabric_type)
    fabric_names = list(fabric_groups.keys())
    
    keyboard = []
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabric_names[start_idx:end_idx]
    
    for i, fabric_name in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=fabric_name,
            callback_data=f"inter_fabric_{fabric_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"inter_fabric_page_{page-1}"
        ))
    
    if end_idx < len(fabric_names):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"inter_fabric_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к типам штор
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору типа шторы",
        callback_data="inter_back_to_types"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_inter_fabric_names_keyboard(fabric_type: str, fabric_category: str, page: int = 0):
    """Устаревшая функция - теперь используется create_inter_fabric_categories_keyboard"""
    return create_inter_fabric_categories_keyboard(fabric_type, page)

def create_inter_colors_keyboard(fabric_type: str, fabric_category: str, fabric_name: str, page: int = 0):
    """Создает клавиатуру с цветами тканей Inter"""
    colors_data = inter_data.get_fabric_colors(fabric_type, fabric_category, fabric_name)
    
    keyboard = []
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_colors = colors_data[start_idx:end_idx]
    
    for i, item in enumerate(page_colors):
        color = inter_data.extract_color_from_name(item.get('name', ''))
        color_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=color,
            callback_data=f"inter_color_{color_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"inter_color_page_{page-1}"
        ))
    
    if end_idx < len(colors_data):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"inter_color_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к полотнам
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору полотна",
        callback_data="inter_back_to_fabrics"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_inter_final_keyboard():
    """Создает финальную клавиатуру для Inter"""
    keyboard = [
        [InlineKeyboardButton(text="🔙 К выбору полотна", callback_data="inter_back_to_colors")],
        [InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Функции для выбора по буквам в Inter
def get_inter_fabric_letters(fabric_names: List[str]) -> List[str]:
    """Получает список уникальных первых букв полотен Inter"""
    letters = set()
    for fabric in fabric_names:
        if fabric:
            first_letter = fabric[0].upper()
            letters.add(first_letter)
    return sorted(list(letters))

def filter_inter_fabrics_by_letter(fabric_names: List[str], letter: str) -> List[str]:
    """Фильтрует полотна Inter по первой букве"""
    return [fabric for fabric in fabric_names if fabric and fabric[0].upper() == letter.upper()]

def create_inter_letters_keyboard(letters: List[str]):
    """Создает клавиатуру с буквами алфавита для Inter"""
    keyboard = []
    
    # Группируем буквы по 5 в строке для компактности
    for i in range(0, len(letters), 5):
        row = []
        for j in range(i, min(i + 5, len(letters))):
            letter = letters[j]
            row.append(InlineKeyboardButton(
                text=letter,
                callback_data=f"inter_letter_{letter}"
            ))
        keyboard.append(row)
    
    # Кнопка возврата к типам штор
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору типа шторы",
        callback_data="inter_back_to_types"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_inter_fabric_by_letter_keyboard(fabric_names: List[str], page: int = 0):
    """Создает клавиатуру с полотнами Inter на определенную букву (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabric_names[start_idx:end_idx]
    
    # Добавляем кнопки полотен
    for i, fabric_name in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=fabric_name,
            callback_data=f"inter_fabric_{fabric_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"inter_fabric_page_{page-1}"
        ))
    
    if end_idx < len(fabric_names):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее", 
            callback_data=f"inter_fabric_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к выбору букв
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору буквы",
        callback_data="inter_back_to_letters"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Функции для алфавитной сортировки Amigo
def get_fabric_letters(fabrics: List[str]) -> List[str]:
    """Получает список уникальных первых букв полотен"""
    letters = set()
    for fabric in fabrics:
        if fabric:
            first_letter = fabric[0].upper()
            letters.add(first_letter)
    return sorted(list(letters))

def filter_amiga_fabrics_by_letter(fabrics: List[str], letter: str) -> List[str]:
    """Фильтрует полотна Amigo по первой букве"""
    return [fabric for fabric in fabrics if fabric and fabric[0].upper() == letter.upper()]



def create_letters_keyboard(letters: List[str]):
    """Создает клавиатуру с буквами алфавита"""
    keyboard = []
    
    # Группируем буквы по 5 в строке для компактности
    for i in range(0, len(letters), 5):
        row = []
        for j in range(i, min(i + 5, len(letters))):
            letter = letters[j]
            row.append(InlineKeyboardButton(
                text=letter,
                callback_data=f"letter_{letter}"
            ))
        keyboard.append(row)
    
    # Кнопка возврата к категориям
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору категории",
        callback_data="amiga_back_to_categories"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_fabric_by_letter_keyboard(fabrics: List[str], page: int = 0):
    """Создает клавиатуру с полотнами на определенную букву (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabrics[start_idx:end_idx]
    
    # Добавляем кнопки полотен
    for i, fabric in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=fabric,
            callback_data=f"amiga_fabric_{fabric_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"amiga_fabric_page_{page-1}"
        ))
    
    if end_idx < len(fabrics):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее", 
            callback_data=f"amiga_fabric_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к выбору букв
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору буквы",
        callback_data="amiga_back_to_letters"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_gofre_letters_keyboard(letters: List[str]):
    """Создает клавиатуру с буквами алфавита для гофре"""
    keyboard = []
    
    # Группируем буквы по 5 в строке для компактности
    for i in range(0, len(letters), 5):
        row = []
        for j in range(i, min(i + 5, len(letters))):
            letter = letters[j]
            row.append(InlineKeyboardButton(
                text=letter,
                callback_data=f"gofre_letter_{letter}"
            ))
        keyboard.append(row)
    
    # Кнопка возврата к выбору модели гофре
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору модели",
        callback_data="amiga_back_to_gofre_models"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_gofre_fabric_by_letter_keyboard(fabrics: List[str], page: int = 0):
    """Создает клавиатуру с полотнами гофре на определенную букву (с пагинацией)"""
    keyboard = []
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_fabrics = fabrics[start_idx:end_idx]
    
    # Добавляем кнопки полотен
    for i, fabric in enumerate(page_fabrics):
        fabric_idx = start_idx + i
        keyboard.append([InlineKeyboardButton(
            text=fabric,
            callback_data=f"amiga_fabric_{fabric_idx}"
        )])
    
    # Добавляем навигацию
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"amiga_fabric_page_{page-1}"
        ))
    
    if end_idx < len(fabrics):
        nav_row.append(InlineKeyboardButton(
            text="➡️ Далее", 
            callback_data=f"amiga_fabric_page_{page+1}"
        ))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата к выбору букв гофре
    keyboard.append([InlineKeyboardButton(
        text="🔙 К выбору буквы",
        callback_data="amiga_back_to_gofre_letters"
    )])
    keyboard.append([InlineKeyboardButton(text="🔄 Завершить работу", callback_data="reset_bot")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    # Всегда показываем приветствие при команде /start
    await state.set_state(MainStates.welcome_screen)
    
    welcome_text = (
        "👋 Привет! Я помощник по проверке и подбору тканей от Amigo, Cortin и Inter.\n\n"
        "📦 Здесь ты можешь быстро находить ткани, проверять наличие на складе.\n\n"
        "🔍 Выбирай нужный завод и запускай проверку!\n\n"
        "Нажми \"🚀 Начать\", чтобы приступить."
    )
    
    await message.answer(text=welcome_text, reply_markup=create_welcome_keyboard())

@dp.callback_query(F.data == "start_bot")
async def start_bot_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки '🚀 Начать' - переход к выбору завода"""
    await state.set_state(MainStates.choosing_factory)
    
    factory_text = "Выберите завод:"
    
    try:
        await callback.message.edit_text(
            text=factory_text,
            reply_markup=create_factory_keyboard()
        )
    except:
        # Если редактирование не удалось, отправляем новое сообщение
        await callback.message.answer(
            text=factory_text,
            reply_markup=create_factory_keyboard()
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("factory_"))
async def process_factory_selection(callback: CallbackQuery, state: FSMContext):
    factory = callback.data.split("_")[1]
    
    if factory == "amiga":
        await state.update_data(factory="amiga")
        await state.set_state(AmigaStates.choosing_category)
        await callback.message.edit_text(
            text="Склад: Amigo\n\nВыберите тип шторы:",
            reply_markup=create_categories_keyboard()
        )
    elif factory == "cortin":
        await state.update_data(factory="cortin")
        await state.set_state(CortinStates.choosing_letter)
        await callback.message.edit_text(
            text="Склад: Cortin\n\nВыберите букву полотна:",
            reply_markup=create_cortin_letters_keyboard()
        )
    elif factory == "inter":
        await state.update_data(factory="inter")
        await state.set_state(InterStates.choosing_fabric_type)
        await callback.message.edit_text(
            text="Склад: Inter\n\nВыберите тип шторы:",
            reply_markup=create_inter_fabric_types_keyboard()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "reset_bot")
async def reset_bot_state(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Завершить работу' - сбрасывает состояние и возвращает к экрану приветствия"""
    await state.clear()
    await state.set_state(MainStates.welcome_screen)
    
    welcome_text = (
        "👋 Привет! Я помощник по проверке и подбору тканей от Amigo, Cortin и Inter.\n\n"
        "📦 Здесь ты можешь быстро находить ткани, проверять наличие на складе и рассчитывать себестоимость изделий.\n\n"
        "🔍 Выбирай нужный завод и запускай проверку!\n\n"
        "Нажми \"🚀 Начать\", чтобы приступить."
    )
    
    try:
        await callback.message.edit_text(
            text=welcome_text,
            reply_markup=create_welcome_keyboard()
        )
    except:
        # Если редактирование не удалось, отправляем новое сообщение
        await callback.message.answer(
            text=welcome_text,
            reply_markup=create_welcome_keyboard()
        )
    
    await callback.answer("Работа завершена")

@dp.callback_query(F.data == "back_to_factory")
async def back_to_factory(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(MainStates.choosing_factory)
    try:
        await callback.message.edit_text(
            text="Выберите склад:",
            reply_markup=create_factory_keyboard()
        )
    except:
        await callback.message.answer(
            text="Выберите склад:",
            reply_markup=create_factory_keyboard()
        )
    await callback.answer()

# Обработчики для Amigo
@dp.callback_query(F.data.startswith("amiga_cat_"))
async def process_amiga_category_selection(callback: CallbackQuery, state: FSMContext):
    try:
        category_idx = int(callback.data.split("_")[2])
        categories_list = list(CATEGORIES.keys())
        
        if category_idx >= len(categories_list):
            await callback.answer("Ошибка выбора категории")
            return
            
        selected_category = categories_list[category_idx]
        logger.info(f"Пользователь выбрал категорию: {selected_category}")
        
        json_filename = CATEGORIES[selected_category]
        
        # Загружаем данные из JSON
        from amiga_data import load_json_data, load_plisse_data, load_gofre_data, get_all_plisse_models, get_all_gofre_models
        
        # Специальная обработка для плиссе и гофре
        if selected_category == "Шторы плиссе":
            # Загружаем все модели плиссе
            models = get_all_plisse_models()
            category_data = {}
            fabric_to_model = {}  # Маппинг полотна к модели
            for model in models:
                model_data = load_plisse_data(model)
                if model_data and model in model_data:
                    for fabric_name in model_data[model].keys():
                        category_data[fabric_name] = model_data[model][fabric_name]
                        fabric_to_model[fabric_name] = model
        # elif selected_category == "Шторы гофре":
        #     # Для гофре показываем выбор модели
        #     await state.update_data(
        #         category=selected_category,
        #         json_filename=json_filename
        #     )
        #     await state.set_state(AmigaStates.choosing_gofre_model)
        #     
        #     keyboard = create_gofre_model_keyboard()
        #     text = f"Склад: Amigo\n\nКатегория: {selected_category}\nВыберите модель:"
        #     await callback.message.edit_text(text=text, reply_markup=keyboard)
        #     await callback.answer()
        #     return
        else:
            # Обычная загрузка для других категорий
            fabric_to_model = {}
            json_data = load_json_data(json_filename)
            if not json_data:
                await callback.message.edit_text(
                    f"❌ Данные для категории '{selected_category}' временно недоступны.\n"
                    "Попробуйте выбрать другую категорию.",
                    reply_markup=create_categories_keyboard()
                )
                return
            
            # Если структура { 'Категория': {...} }, берём только подсловарь
            category_data = json_data
            if selected_category in json_data:
                category_data = json_data[selected_category]
        
        if not category_data:
            await callback.message.edit_text(
                f"❌ Данные для категории '{selected_category}' временно недоступны.\n"
                "Попробуйте выбрать другую категорию.",
                reply_markup=create_categories_keyboard()
            )
            return
        
        # Сохраняем данные в состоянии
        await state.update_data(
            category=selected_category,
            json_filename=json_filename,
            category_data=category_data,
            fabric_to_model=fabric_to_model,  # Добавляем маппинг полотна к модели
            fabric_page=0
        )
        await state.set_state(AmigaStates.choosing_letter)
        
        # Показываем буквы алфавита
        fabrics = list(category_data.keys())
        letters = get_fabric_letters(fabrics)
        keyboard = create_letters_keyboard(letters)
        text = f"Склад: Amigo\n\nКатегория: {selected_category}\nВыберите первую букву полотна:"
        await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе категории: {e}")
        await callback.answer("Произошла ошибка")

# @dp.callback_query(F.data.startswith("gofre_model_"))
# async def process_gofre_model_selection(callback: CallbackQuery, state: FSMContext):
#     try:
#         model = callback.data.split("_")[2]  # MAXI, MIDI, или RUS
#         logger.info(f"Пользователь выбрал модель гофре: {model}")
#         
#         data = await state.get_data()
#         selected_category = data['category']
#         
#         # Загружаем данные для выбранной модели
#         from amiga_data import load_gofre_data
#         model_data = load_gofre_data(model)
#         
#         if not model_data or model not in model_data:
#             await callback.message.edit_text(
#                 f"❌ Данные для модели '{model}' временно недоступны.\n"
#                 "Попробуйте выбрать другую модель.",
#                 reply_markup=create_gofre_model_keyboard()
#             )
#             await callback.answer()
#             return
#         
#         category_data = model_data[model]
#         fabric_to_model = {fabric_name: model for fabric_name in category_data.keys()}
#         
#         # Сохраняем данные в состоянии
#         await state.update_data(
#             gofre_model=model,
#             category_data=category_data,
#             fabric_to_model=fabric_to_model,
#             fabric_page=0
#         )
#         await state.set_state(AmigaStates.choosing_letter)
#         
#         # Показываем буквы алфавита для выбранной модели
#         fabrics = list(category_data.keys())
#         letters = get_fabric_letters(fabrics)
#         keyboard = create_gofre_letters_keyboard(letters)
#         text = f"Склад: Amigo\n\nКатегория: {selected_category}\nМодель: {model}\nВыберите первую букву полотна:"
#         await callback.message.edit_text(text=text, reply_markup=keyboard)
#         await callback.answer()
#         
#     except Exception as e:
#         logger.error(f"Ошибка при выборе модели гофре: {e}")
#         await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("letter_"))
async def process_letter_selection(callback: CallbackQuery, state: FSMContext):
    try:
        letter = callback.data.split("_")[1]
        logger.info(f"Пользователь выбрал букву: {letter}")
        
        data = await state.get_data()
        category_data = data['category_data']
        selected_category = data['category']
        
        # Фильтруем полотна по выбранной букве
        all_fabrics = list(category_data.keys())
        filtered_fabrics = filter_amiga_fabrics_by_letter(all_fabrics, letter)
        
        if not filtered_fabrics:
            await callback.answer(f"Нет полотен на букву '{letter}'")
            return
        
        # Сохраняем выбранную букву и отфильтрованные полотна
        await state.update_data(
            selected_letter=letter,
            filtered_fabrics=filtered_fabrics,
            fabric_page=0
        )
        await state.set_state(AmigaStates.choosing_fabric)
        
        # Показываем полотна на выбранную букву
        keyboard = create_fabric_by_letter_keyboard(filtered_fabrics, 0)
        text = f"Склад: Amigo\n\nКатегория: {selected_category}\nБуква: {letter}\nВыберите полотно:"
        await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе буквы: {e}")
        await callback.answer("Произошла ошибка")

# @dp.callback_query(F.data.startswith("gofre_letter_"))
# async def process_gofre_letter_selection(callback: CallbackQuery, state: FSMContext):
#     try:
#         letter = callback.data.split("_")[2]
#         logger.info(f"Пользователь выбрал букву для гофре: {letter}")
#         
#         data = await state.get_data()
#         category_data = data['category_data']
#         selected_category = data['category']
#         gofre_model = data['gofre_model']
#         
#         # Фильтруем полотна по выбранной букве
#         all_fabrics = list(category_data.keys())
#         filtered_fabrics = filter_amiga_fabrics_by_letter(all_fabrics, letter)
#         
#         if not filtered_fabrics:
#             await callback.answer(f"Нет полотен на букву '{letter}'")
#             return
#         
#         # Сохраняем выбранную букву и отфильтрованные полотна
#         await state.update_data(
#             selected_letter=letter,
#             filtered_fabrics=filtered_fabrics,
#             fabric_page=0
#         )
#         await state.set_state(AmigaStates.choosing_fabric)
#         
#         # Показываем полотна на выбранную букву
#         keyboard = create_gofre_fabric_by_letter_keyboard(filtered_fabrics, 0)
#         text = f"Склад: Amigo\n\nКатегория: {selected_category}\nМодель: {gofre_model}\nБуква: {letter}\nВыберите полотно:"
#         await callback.message.edit_text(text=text, reply_markup=keyboard)
#         await callback.answer()
#         
#     except Exception as e:
#         logger.error(f"Ошибка при выборе буквы для гофре: {e}")
#         await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("amiga_fabric_"))
async def process_amiga_fabric_selection(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        
        if 'category_data' not in data:
            await callback.message.edit_text(
                "❌ Данные для выбранной категории недоступны. Пожалуйста, выберите категорию заново.",
                reply_markup=create_categories_keyboard()
            )
            await state.set_state(AmigaStates.choosing_category)
            await callback.answer()
            return
        
        # Используем отфильтрованные полотна, если они есть, иначе все полотна
        if 'filtered_fabrics' in data:
            fabrics = data['filtered_fabrics']
        else:
            fabrics = list(data['category_data'].keys())
        
        if callback.data.startswith("amiga_fabric_page_"):
            # Обработка пагинации
            page = int(callback.data.split("_")[3])
            await state.update_data(fabric_page=page)
            
            # Выбираем правильную клавиатуру в зависимости от контекста
            if 'filtered_fabrics' in data:
                # Используем клавиатуру для отфильтрованных полотен
                # if data.get('category') == "Шторы гофре" and 'gofre_model' in data:
                #     keyboard = create_gofre_fabric_by_letter_keyboard(fabrics, page)
                # else:
                keyboard = create_fabric_by_letter_keyboard(fabrics, page)
            else:
                # Используем обычную клавиатуру
                # if data.get('category') == "Шторы гофре" and 'gofre_model' in data:
                #     keyboard = create_gofre_fabric_keyboard(fabrics, page)
                # else:
                keyboard = create_fabric_keyboard(fabrics, page)
            
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer()
            return
        
        # Обработка выбора полотна
        fabric_idx = int(callback.data.split("_")[2])
        
        if fabric_idx >= len(fabrics):
            await callback.answer("Ошибка выбора полотна")
            return
            
        selected_fabric = fabrics[fabric_idx]
        logger.info(f"Пользователь выбрал полотно: {selected_fabric}")
        variants = data['category_data'][selected_fabric]
        
        if not variants:
            await callback.message.edit_text(
                "❌ Для выбранного полотна нет доступных вариантов. Пожалуйста, выберите другое полотно.",
                reply_markup=create_fabric_keyboard(fabrics, data.get('fabric_page', 0))
            )
            await callback.answer()
            return
        
        # Сохраняем состояние
        await state.update_data(
            fabric=selected_fabric,
            variants=variants,
            variant_page=0
        )
        await state.set_state(AmigaStates.choosing_variant)
        
        # Показываем варианты
        keyboard = create_variants_keyboard(variants, 0)
        
        # Формируем текст с учетом модели для гофре
        # if data.get('category') == "Шторы гофре" and 'gofre_model' in data:
        #     text = (f"Склад: Amigo\n\n"
        #             f"Категория: {data['category']}\n"
        #             f"Модель: {data['gofre_model']}\n"
        #             f"Полотно: {selected_fabric}\n"
        #             f"Выберите вариант:")
        # else:
        text = (f"Склад: Amigo\n\n"
                f"Категория: {data['category']}\n"
                f"Полотно: {selected_fabric}\n"
                f"Выберите вариант:")
        
        await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе полотна: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("amiga_variant_"))
async def process_amiga_variant_selection(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        category = data['category']
        
        if 'variants' not in data or not data['variants']:
            await callback.message.edit_text(
                "❌ Нет доступных вариантов для выбранного полотна. Пожалуйста, выберите другое полотно.",
                reply_markup=create_fabric_keyboard(
                    list(data.get('category_data', {}).keys()), 
                    data.get('fabric_page', 0)
                )
            )
            await state.set_state(AmigaStates.choosing_fabric)
            await callback.answer()
            return
            
        variants = data['variants']
        
        if callback.data.startswith("amiga_variant_page_"):
            # Обработка пагинации
            page = int(callback.data.split("_")[3])
            await state.update_data(variant_page=page)
            keyboard = create_variants_keyboard(variants, page)
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer()
            return
            
        # Обработка выбора варианта
        variant_idx = int(callback.data.split("_")[2])
        
        if variant_idx >= len(variants):
            await callback.answer("Ошибка выбора варианта")
            return
            
        selected_variant = variants[variant_idx]
        logger.info(f"Пользователь выбрал вариант: {selected_variant}")
        
        # Сохраняем состояние
        await state.update_data(variant=selected_variant)
        await state.set_state(AmigaStates.final_selection)
        
        await callback.message.edit_text("🔄 Получаю информацию о товаре, пожалуйста подождите...")
        
        fabric_name = data['fabric']
        
        # Определяем model_id для плиссе и гофре
        model_id = None
        if category in ["Шторы плиссе"]:  # Убрали "Шторы гофре"
            fabric_to_model = data.get('fabric_to_model', {})
            model_name = fabric_to_model.get(fabric_name)
            if model_name:
                if category == "Шторы плиссе":
                    from amiga_data import PLISSE_MODEL_IDS
                    model_id = PLISSE_MODEL_IDS.get(model_name)
                # elif category == "Шторы гофре":
                #     from amiga_data import GOFRE_MODEL_IDS
                #     model_id = GOFRE_MODEL_IDS.get(model_name)
                logger.info(f"Для {category} {fabric_name} используем model_id={model_id} (модель {model_name})")
        
        # Выполняем API запрос
        from amiga_data import make_api_request, get_availability_status, make_absolute_url
        api_response = await make_api_request(
            category,
            fabric_name,
            selected_variant,
            model_id=model_id
        )
        
        if api_response:
            availability_code = api_response['material'].get('availability', 0)
            availability_status = get_availability_status(availability_code)
            image_url = make_absolute_url(api_response['material'].get('image'))
            material_name = api_response['material'].get('name', f"{fabric_name} {selected_variant}")
        else:
            availability_status = "❓ Информация временно недоступна"
            availability_code = None
            image_url = None
            material_name = f"{fabric_name} {selected_variant}"
        
        # Формируем текст карточки товара
        # if data.get('category') == "Шторы гофре" and 'gofre_model' in data:
        #     card_text = (
        #         f"Склад: Amigo\n\n"
        #         f"Ваш выбор:\n\n"
        #         f"Категория: {data['category']}\n"
        #         f"Модель: {data['gofre_model']}\n"
        #         f"Полотно: {data['fabric']}\n"
        #         f"Вариант: {selected_variant}\n"
        #         f"Название: {material_name}\n\n"
        #         f"📦 Наличие: {availability_status}"
        #     )
        # else:
        card_text = (
            f"Склад: Amigo\n\n"
            f"Ваш выбор:\n\n"
            f"Категория: {data['category']}\n"
            f"Полотно: {data['fabric']}\n"
            f"Вариант: {selected_variant}\n"
            f"Название: {material_name}\n\n"
            f"📦 Наличие: {availability_status}"
        )
        
        keyboard = create_final_keyboard()
        
        # Отправляем результат с фото или без
        if image_url:
            try:
                await callback.message.delete()
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=image_url,
                    caption=card_text,
                    reply_markup=keyboard
                )
                await callback.answer()
                return
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
                await callback.message.edit_text(text=card_text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(text=card_text, reply_markup=keyboard)
            
        await callback.answer()
        logger.info(f"Пользователь выбрал товар: {data['category']} - {data['fabric']} - {selected_variant}")
        
    except Exception as e:
        logger.error(f"Ошибка при выборе варианта: {e}")
        await callback.answer("Произошла ошибка")

# Обработчики Cortin
@dp.callback_query(F.data.startswith("cortin_letter_"))
async def process_cortin_letter_selection(callback: CallbackQuery, state: FSMContext):
    try:
        letter = callback.data.split("_")[2]
        logger.info(f"Пользователь выбрал букву для Cortin: {letter}")
        
        # Получаем типы тканей для выбранной буквы
        from cortin_data import get_fabric_types_by_letter
        fabric_types = get_fabric_types_by_letter(letter)
        
        if not fabric_types:
            await callback.answer(f"Нет типов тканей на букву '{letter}'")
            return
        
        # Сохраняем выбранную букву
        await state.update_data(selected_letter=letter, fabric_types=fabric_types)
        await state.set_state(CortinStates.choosing_fabric_type)
        
        # Показываем типы тканей на выбранную букву
        keyboard = create_cortin_fabric_types_keyboard(fabric_types)
        text = f"Склад: Cortin\n\nБуква: {letter}\nВыберите тип ткани:"
        await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе буквы для Cortin: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("cortin_fabric_type_page_"))
async def process_cortin_fabric_type_page(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split("_")[4])
        data = await state.get_data()
        fabrics = data.get('fabrics', [])
        selected_fabric_type = data.get('selected_fabric_type', '')
        
        # Обновляем страницу
        await state.update_data(fabric_page=page)
        
        # Показываем полотна на новой странице
        keyboard = create_cortin_fabric_by_type_keyboard(fabrics, page)
        text = f"Склад: Cortin\n\nБуква: {data.get('selected_letter', '')}\nТип ткани: {selected_fabric_type}\nВыберите полотно:"
        await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при переходе по страницам Cortin: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("cortin_fabric_type_") & ~F.data.contains("page"))
async def process_cortin_fabric_type_selection(callback: CallbackQuery, state: FSMContext):
    try:
        fabric_type_idx = int(callback.data.split("_")[3])
        data = await state.get_data()
        fabric_types = data.get('fabric_types', [])
        
        if fabric_type_idx >= len(fabric_types):
            await callback.answer("Ошибка выбора типа ткани")
            return
            
        selected_fabric_type = fabric_types[fabric_type_idx]
        logger.info(f"Пользователь выбрал тип ткани Cortin: {selected_fabric_type}")
        
        # Получаем полотна выбранного типа
        from cortin_data import get_fabrics_by_type
        fabrics = get_fabrics_by_type(selected_fabric_type)
        
        if not fabrics:
            await callback.answer(f"Нет полотен типа '{selected_fabric_type}'")
            return
        
        # Сохраняем выбранный тип ткани и полотна
        await state.update_data(
            selected_fabric_type=selected_fabric_type,
            fabrics=fabrics,
            fabric_page=0
        )
        await state.set_state(CortinStates.choosing_fabric)
        
        # Показываем полотна выбранного типа
        keyboard = create_cortin_fabric_by_type_keyboard(fabrics, 0)
        text = f"Склад: Cortin\n\nБуква: {data.get('selected_letter', '')}\nТип ткани: {selected_fabric_type}\nВыберите полотно:"
        await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе типа ткани для Cortin: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("cortin_fabric_") & ~F.data.contains("page") & ~F.data.contains("final") & ~F.data.contains("type"))
async def process_cortin_fabric_selection(callback: CallbackQuery, state: FSMContext):
    try:
        fabric_idx = int(callback.data.split("_")[2])
        data = await state.get_data()
        filtered_fabrics = data.get('filtered_fabrics', [])
        
        if fabric_idx >= len(filtered_fabrics):
            await callback.answer("Ошибка выбора полотна")
            return
            
        selected_fabric = filtered_fabrics[fabric_idx]
        logger.info(f"Пользователь выбрал полотно Cortin: {selected_fabric}")
        
        # Получаем информацию о полотне
        from cortin_data import find_fabric_by_name, get_fabric_stock_online
        fabric_info = find_fabric_by_name(selected_fabric)
        
        if not fabric_info:
            await callback.answer("Полотно не найдено")
            return
        
        await state.update_data(selected_fabric=fabric_info)
        await state.set_state(CortinStates.final_selection)
        
        # Показываем сообщение о загрузке
        await callback.message.edit_text("🔄 Получаю информацию о товаре, пожалуйста подождите...")
        
        # Получаем данные о наличии
        try:
            stock_info = await get_fabric_stock_online(selected_fabric, "Римские шторы", "День-Ночь")
            availability = stock_info.get('availability', '❓ Нет данных')
        except Exception as e:
            logger.error(f"Ошибка получения наличия для {selected_fabric}: {e}")
            availability = "❓ Нет данных"
        
        # Формируем сообщение
        message_text = f"Информация о товаре\n\n"
        message_text += f"Склад: Cortin\n"
        message_text += f"Название полотна: {selected_fabric}\n"
        message_text += f"📦 Наличие: {availability}\n"
        
        # Отправляем фото если есть
        image_url = fabric_info.get('image')
        if image_url and image_url.strip():
            try:
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=image_url,
                    caption=message_text,
                    reply_markup=create_cortin_final_keyboard()
                )
            except Exception as photo_error:
                logger.warning(f"Не удалось загрузить изображение {image_url}: {photo_error}")
                # Если фото не загрузилось, отправляем только текст
                await callback.message.edit_text(
                    message_text + "\n❌ Изображение недоступно",
                    reply_markup=create_cortin_final_keyboard()
                )
        else:
            await callback.message.edit_text(
                message_text + "\n📷 Изображение отсутствует",
                reply_markup=create_cortin_final_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка при выборе полотна Cortin: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("cortin_fabric_final_"))
async def process_cortin_fabric_final_selection(callback: CallbackQuery, state: FSMContext):
    try:
        fabric_id = int(callback.data.split("_")[3])
        logger.info(f"Пользователь выбрал полотно Cortin с ID: {fabric_id}")
        
        # Получаем информацию о полотне по ID
        from cortin_data import find_variant_by_id, get_fabric_stock_online
        fabric_info = find_variant_by_id(fabric_id)
        
        if not fabric_info:
            await callback.answer("Полотно не найдено")
            return
        
        selected_fabric = fabric_info.get('name', 'Без названия')
        await state.update_data(selected_fabric=fabric_info)
        await state.set_state(CortinStates.final_selection)
        
        # Показываем сообщение о загрузке
        await callback.message.edit_text("🔄 Получаю информацию о товаре, пожалуйста подождите...")
        
        # Получаем данные о наличии
        try:
            stock_info = await get_fabric_stock_online(selected_fabric, "Римские шторы", "День-Ночь")
            availability = stock_info.get('availability', '❓ Нет данных')
        except Exception as e:
            logger.error(f"Ошибка получения наличия для {selected_fabric}: {e}")
            availability = "❓ Нет данных"
        
        # Формируем сообщение
        message_text = f"Информация о товаре\n\n"
        message_text += f"Склад: Cortin\n"
        message_text += f"Название полотна: {selected_fabric}\n"
        message_text += f"📦 Наличие: {availability}\n"
        
        # Отправляем фото если есть
        image_url = fabric_info.get('image')
        if image_url:
            try:
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=image_url,
                    caption=message_text,
                    reply_markup=create_cortin_final_keyboard(),
                    parse_mode="Markdown"
                )
            except Exception as photo_error:
                # Если фото не загрузилось, отправляем только текст
                await callback.message.edit_text(
                    message_text + "\n❌ Изображение недоступно",
                    reply_markup=create_cortin_final_keyboard(),
                    parse_mode="Markdown"
                )
        else:
            await callback.message.edit_text(
                message_text,
                reply_markup=create_cortin_final_keyboard(),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка при выборе полотна Cortin: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("cortin_fabric_page_"))
async def process_cortin_fabric_page(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split("_")[3])
        data = await state.get_data()
        fabrics = data.get('fabrics', [])
        selected_fabric_type = data.get('selected_fabric_type', '')
        
        await state.update_data(fabric_page=page)
        
        keyboard = create_cortin_fabric_by_type_keyboard(fabrics, page)
        text = f"Склад: Cortin\n\nБуква: {data.get('selected_letter', '')}\nТип ткани: {selected_fabric_type}\nВыберите полотно:"
        await callback.message.edit_text(text=text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при навигации по страницам Cortin: {e}")
        await callback.answer("Произошла ошибка")

# Обработчики навигации для Amigo
@dp.callback_query(F.data == "amiga_back_to_categories")
async def amiga_back_to_categories(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AmigaStates.choosing_category)
    
    # Очищаем состояние букв и отфильтрованных полотен
    await state.update_data(filtered_fabrics=None, selected_letter=None)
    
    try:
        await callback.message.edit_text(
            text="Склад: Amigo\n\nВыберите тип шторы:",
            reply_markup=create_categories_keyboard()
        )
    except:
        # Если не удается редактировать (например, сообщение с изображением), создаем новое
        await callback.message.answer(
            text="Склад: Amigo\n\nВыберите тип шторы:",
            reply_markup=create_categories_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data == "amiga_back_to_fabrics")
async def amiga_back_to_fabrics(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if 'category_data' in data:
        await state.set_state(AmigaStates.choosing_letter)
        
        # Получаем все полотна для категории
        category_data = data.get('category_data', {})
        fabrics = list(category_data.keys())
        letters = get_fabric_letters(fabrics)
        
        # Проверяем, это гофре или нет
        # if data.get('category') == "Шторы гофре" and 'gofre_model' in data:
        #     keyboard = create_gofre_letters_keyboard(letters)
        #     text = f"Склад: Amigo\n\nКатегория: {data['category']}\nМодель: {data['gofre_model']}\nВыберите первую букву полотна:"
        # else:
        keyboard = create_letters_keyboard(letters)
        text = f"Склад: Amigo\n\nКатегория: {data['category']}\nВыберите первую букву полотна:"
        
        try:
            await callback.message.edit_text(text=text, reply_markup=keyboard)
        except:
            await callback.message.answer(text=text, reply_markup=keyboard)
    else:
        await amiga_back_to_categories(callback, state)
    await callback.answer()

# @dp.callback_query(F.data == "amiga_back_to_gofre_models")
# async def amiga_back_to_gofre_models(callback: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     await state.set_state(AmigaStates.choosing_gofre_model)
#     
#     # Очищаем состояние букв и отфильтрованных полотен
#     await state.update_data(filtered_fabrics=None, selected_letter=None)
#     
#     keyboard = create_gofre_model_keyboard()
#     text = f"Склад: Amigo\n\nКатегория: {data.get('category', 'Шторы гофре')}\nВыберите модель:"
#     
#     try:
#         await callback.message.edit_text(text=text, reply_markup=keyboard)
#     except:
#         await callback.message.answer(text=text, reply_markup=keyboard)
#     await callback.answer()

@dp.callback_query(F.data == "amiga_back_to_variants")
async def amiga_back_to_variants(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if 'variants' in data:
        await state.set_state(AmigaStates.choosing_variant)
        variants = data['variants']
        keyboard = create_variants_keyboard(variants, data.get('variant_page', 0))
        text = (f"Склад: Amigo\n\n"
                f"Категория: {data['category']}\n"
                f"Полотно: {data['fabric']}\n"
                f"Выберите вариант:")
        try:
            await callback.message.edit_text(text=text, reply_markup=keyboard)
        except:
            await callback.message.answer(text=text, reply_markup=keyboard)
    else:
        await amiga_back_to_fabrics(callback, state)
    await callback.answer()

@dp.callback_query(F.data == "amiga_back_to_letters")
async def amiga_back_to_letters(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AmigaStates.choosing_letter)
    
    # Очищаем отфильтрованные полотна
    await state.update_data(filtered_fabrics=None, selected_letter=None)
    
    # Получаем все полотна для категории
    category_data = data.get('category_data', {})
    fabrics = list(category_data.keys())
    letters = get_fabric_letters(fabrics)
    
    keyboard = create_letters_keyboard(letters)
    text = f"Склад: Amigo\n\nКатегория: {data.get('category')}\nВыберите первую букву полотна:"
    
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    except:
        await callback.message.answer(text=text, reply_markup=keyboard)
    await callback.answer()

# @dp.callback_query(F.data == "amiga_back_to_gofre_letters")
# async def amiga_back_to_gofre_letters(callback: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     await state.set_state(AmigaStates.choosing_letter)
#     
#     # Очищаем отфильтрованные полотна
#     await state.update_data(filtered_fabrics=None, selected_letter=None)
#     
#     # Получаем все полотна для гофре модели
#     category_data = data.get('category_data', {})
#     fabrics = list(category_data.keys())
#     letters = get_fabric_letters(fabrics)
#     
#     keyboard = create_gofre_letters_keyboard(letters)
#     text = f"Склад: Amigo\n\nКатегория: {data.get('category')}\nМодель: {data.get('gofre_model')}\nВыберите первую букву полотна:"
#     
#     try:
#         await callback.message.edit_text(text=text, reply_markup=keyboard)
#     except:
#         await callback.message.answer(text=text, reply_markup=keyboard)
#     await callback.answer()

@dp.callback_query(F.data == "amiga_new_search")
async def amiga_new_search(callback: CallbackQuery, state: FSMContext):
    await state.update_data(factory="Amigo")
    await state.set_state(AmigaStates.choosing_category)
    
    # Очищаем состояние букв и отфильтрованных полотен
    await state.update_data(filtered_fabrics=None, selected_letter=None)
    
    await callback.message.edit_text(
        text="Склад: Amigo\n\nВыберите тип шторы:",
        reply_markup=create_categories_keyboard()
    )
    await callback.answer()

# Обработчики пагинации и навигации Cortin
@dp.callback_query(F.data.startswith("cortin_shutter_page_"))
async def cortin_shutter_pagination(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split("_")[-1])
        data = await state.get_data()
        category = data.get('shutter_category', '')
        
        await callback.message.edit_text(
            f"Категория: {category}\n\nВыберите тип шторы:",
            reply_markup=create_cortin_shutters_keyboard(category, page)
        )
    except Exception as e:
        await callback.message.edit_text(
            "❌ Ошибка пагинации",
            reply_markup=create_cortin_shutter_categories_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("cortin_fabric_cat_page_"))
async def cortin_fabric_category_pagination(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split("_")[-1])
        
        await callback.message.edit_text(
            "Выберите категорию ткани:",
            reply_markup=create_cortin_fabric_categories_keyboard(page)
        )
    except Exception as e:
        await callback.message.edit_text(
            "❌ Ошибка пагинации",
            reply_markup=create_cortin_fabric_categories_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("cortin_variant_page_"))
async def cortin_variant_pagination(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split("_")[-1])
        data = await state.get_data()
        fabric_category = data.get('fabric_category', '')
        
        await callback.message.edit_text(
            f"Категория ткани: {fabric_category}\n\nВыберите вариант:",
            reply_markup=create_cortin_fabric_variants_keyboard(fabric_category, page)
        )
    except Exception as e:
        data = await state.get_data()
        fabric_category = data.get('fabric_category', '')
        await callback.message.edit_text(
            "❌ Ошибка пагинации",
            reply_markup=create_cortin_fabric_variants_keyboard(fabric_category)
        )
    await callback.answer()

# Обработчики навигации Cortin
@dp.callback_query(F.data == "cortin_back_to_fabric_types")
async def cortin_back_to_fabric_types(callback: CallbackQuery, state: FSMContext):
    # Возвращаемся к выбору типов полотен
    data = await state.get_data()
    selected_letter = data.get('selected_letter', '')
    fabric_types = data.get('fabric_types', [])
    
    await state.set_state(CortinStates.choosing_fabric_type)
    
    if fabric_types:
        keyboard = create_cortin_fabric_types_keyboard(fabric_types)
        text = f"Склад: Cortin\n\nБуква: {selected_letter}\nВыберите тип полотна:"
    else:
        # Если нет сохраненных типов, возвращаемся к выбору букв
        await cortin_back_to_letters(callback, state)
        return
    
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    except:
        await callback.message.answer(text=text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "cortin_back_to_letters")
async def cortin_back_to_letters(callback: CallbackQuery, state: FSMContext):
    # Возвращаемся к выбору букв
    await state.set_state(CortinStates.choosing_letter)
    try:
        await callback.message.edit_text(
            "Склад: Cortin\n\nВыберите букву полотна:",
            reply_markup=create_cortin_letters_keyboard()
        )
    except:
        await callback.message.answer(
            "Склад: Cortin\n\nВыберите букву полотна:",
            reply_markup=create_cortin_letters_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data == "cortin_new_search")
async def cortin_new_search(callback: CallbackQuery, state: FSMContext):
    # Возвращаемся к выбору букв
    await state.set_state(CortinStates.choosing_letter)
    try:
        await callback.message.edit_text(
            "Склад: Cortin\n\nВыберите букву полотна:",
            reply_markup=create_cortin_letters_keyboard()
        )
    except:
        await callback.message.answer(
            "Склад: Cortin\n\nВыберите букву полотна:",
            reply_markup=create_cortin_letters_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data == "back_to_factories")
async def back_to_factories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(MainStates.choosing_factory)
    try:
        await callback.message.edit_text(
            text="Выберите склад:",
            reply_markup=create_factory_keyboard()
        )
    except:
        await callback.message.answer(
            text="Выберите склад:",
            reply_markup=create_factory_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("inter_type_"))
async def process_inter_fabric_type_selection(callback: CallbackQuery, state: FSMContext):
    try:
        type_idx = int(callback.data.split("_")[2])
        fabric_types = inter_data.get_fabric_types()
        
        if type_idx >= len(fabric_types):
            await callback.answer("Ошибка выбора типа шторы")
            return
            
        selected_type = fabric_types[type_idx]
        logger.info(f"Пользователь выбрал тип шторы Inter: {selected_type}")
        
        await state.update_data(fabric_type=selected_type)
        
        display_name = inter_data.get_display_name(selected_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
        
        # Проверяем, нужен ли выбор по буквам для этого типа
        if selected_type in ["Ткани плиссе", "Ткани рулонные", "Ткани вертикальные 89 мм", "Ткани Комбо"]:
            # Для плиссе и рулонных - показываем выбор букв
            await state.set_state(InterStates.choosing_letter)
            
            # Получаем все полотна для этого типа
            fabric_groups = inter_data.get_fabric_groups(selected_type)
            fabric_names = list(fabric_groups.keys())
            
            # Получаем уникальные буквы
            letters = get_inter_fabric_letters(fabric_names)
            
            await callback.message.edit_text(
                text=f"Склад: Inter\n\nТип шторы: {display_name}\n\nВыберите первую букву названия полотна:",
                reply_markup=create_inter_letters_keyboard(letters)
            )
        else:
            # Для остальных типов - обычная логика
            await state.set_state(InterStates.choosing_fabric_name)
            
            await callback.message.edit_text(
                text=f"Склад: Inter\n\nТип шторы: {display_name}\n\nВыберите полотно:",
                reply_markup=create_inter_fabric_categories_keyboard(selected_type)
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе типа шторы Inter: {e}")
        await callback.answer("Произошла ошибка")

# Удаляем старый обработчик inter_cat_ так как он больше не нужен

@dp.callback_query(F.data.startswith("inter_fabric_"))
async def process_inter_fabric_name_selection(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        fabric_type = data.get('fabric_type', '')
        
        if callback.data.startswith("inter_fabric_page_"):
            # Обработка пагинации
            page = int(callback.data.split("_")[3])
            await state.update_data(fabric_page=page)
            
            # Проверяем, используются ли отфильтрованные полотна
            filtered_fabrics = data.get('filtered_fabrics', [])
            if filtered_fabrics:
                keyboard = create_inter_fabric_by_letter_keyboard(filtered_fabrics, page)
            else:
                keyboard = create_inter_fabric_categories_keyboard(fabric_type, page)
            
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer()
            return
        
        # Обработка выбора полотна
        fabric_idx = int(callback.data.split("_")[2])
        
        # Проверяем, используются ли отфильтрованные полотна
        filtered_fabrics = data.get('filtered_fabrics', [])
        if filtered_fabrics:
            # Используем отфильтрованные полотна
            fabric_names = filtered_fabrics
        else:
            # Используем все полотна для типа
            fabric_groups = inter_data.get_fabric_groups(fabric_type)
            fabric_names = list(fabric_groups.keys())
        
        if fabric_idx >= len(fabric_names):
            await callback.answer("Ошибка выбора полотна")
            return
            
        selected_fabric = fabric_names[fabric_idx]
        logger.info(f"Пользователь выбрал полотно Inter: {selected_fabric}")
        
        await state.update_data(fabric_name=selected_fabric)
        await state.set_state(InterStates.choosing_color)
        
        display_type = inter_data.get_display_name(fabric_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
        
        await callback.message.edit_text(
            text=f"Склад: Inter\n\nТип шторы: {display_type}\nПолотно: {selected_fabric}\n\nВыберите цвет:",
            reply_markup=create_inter_colors_keyboard(fabric_type, "", selected_fabric)  # fabric_category не используется
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе полотна Inter: {e}")
        await callback.answer("Произошла ошибка")

@dp.callback_query(F.data.startswith("inter_color_"))
async def process_inter_color_selection(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        fabric_type = data.get('fabric_type', '')
        fabric_name = data.get('fabric_name', '')
        
        if callback.data.startswith("inter_color_page_"):
            # Обработка пагинации
            page = int(callback.data.split("_")[3])
            await state.update_data(color_page=page)
            
            keyboard = create_inter_colors_keyboard(fabric_type, "", fabric_name, page)
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer()
            return
        
        # Обработка выбора цвета
        color_idx = int(callback.data.split("_")[2])
        colors_data = inter_data.get_fabric_colors(fabric_type, "", fabric_name)
        
        if color_idx >= len(colors_data):
            await callback.answer("Ошибка выбора цвета")
            return
            
        selected_item = colors_data[color_idx]
        selected_color = inter_data.extract_color_from_name(selected_item.get('name', ''))
        logger.info(f"Пользователь выбрал цвет Inter: {selected_color}")
        
        await state.update_data(color=selected_color)
        await state.set_state(InterStates.final_selection)
        
        await callback.message.edit_text("🔄 Получаю информацию о товаре, пожалуйста подождите...")
        
        # Получаем информацию о ткани
        fabric_info = await inter_data.get_fabric_info(fabric_type, "", fabric_name, selected_color)
        
        if not fabric_info:
            await callback.message.edit_text(
                "❌ Информация о выбранной ткани недоступна",
                reply_markup=create_inter_colors_keyboard(fabric_type, "", fabric_name)
            )
            await state.set_state(InterStates.choosing_color)
            await callback.answer()
            return
        
        # Формируем сообщение
        display_type = inter_data.get_display_name(fabric_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
        
        message_text = f"""Склад: Inter

Название: {fabric_info['name']}
Тип шторы: {display_type}
📦 Наличие: {fabric_info['status']}

Дополнительная информация: {fabric_info['availability_text']}"""
        
        # Отправляем результат с фото или без
        image_url = fabric_info.get('image_url', '')
        if image_url:
            try:
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=image_url,
                    caption=message_text,
                    reply_markup=create_inter_final_keyboard(),
                    parse_mode="Markdown"
                )
            except Exception as photo_error:
                # Если фото не загрузилось, отправляем только текст
                await callback.message.edit_text(
                    message_text + "\n❌ Изображение недоступно",
                    reply_markup=create_inter_final_keyboard(),
                    parse_mode="Markdown"
                )
        else:
            await callback.message.edit_text(
                message_text,
                reply_markup=create_inter_final_keyboard(),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка при выборе цвета Inter: {e}")
        data = await state.get_data()
        fabric_type = data.get('fabric_type', '')
        fabric_name = data.get('fabric_name', '')
        await callback.message.edit_text(
            "❌ Произошла ошибка при получении информации о товаре",
            reply_markup=create_inter_colors_keyboard(fabric_type, "", fabric_name)
        )
    await callback.answer()

# Обработчики для выбора по буквам в Inter
@dp.callback_query(F.data.startswith("inter_letter_"))
async def process_inter_letter_selection(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        fabric_type = data.get('fabric_type', '')
        
        # Извлекаем выбранную букву
        selected_letter = callback.data.split("_")[2]
        logger.info(f"Пользователь выбрал букву Inter: {selected_letter}")
        
        # Получаем все полотна для этого типа
        fabric_groups = inter_data.get_fabric_groups(fabric_type)
        fabric_names = list(fabric_groups.keys())
        
        # Фильтруем полотна по выбранной букве
        filtered_fabrics = filter_inter_fabrics_by_letter(fabric_names, selected_letter)
        
        if not filtered_fabrics:
            await callback.answer(f"Нет полотен на букву {selected_letter}")
            return
        
        # Сохраняем отфильтрованные полотна и букву в состоянии
        await state.update_data(
            selected_letter=selected_letter,
            filtered_fabrics=filtered_fabrics
        )
        await state.set_state(InterStates.choosing_fabric_name)
        
        display_type = inter_data.get_display_name(fabric_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
        
        await callback.message.edit_text(
            text=f"Склад: Inter\n\nТип шторы: {display_type}\nБуква: {selected_letter}\n\nВыберите полотно:",
            reply_markup=create_inter_fabric_by_letter_keyboard(filtered_fabrics)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе буквы Inter: {e}")
        await callback.answer("Произошла ошибка")

# Обработчики навигации для Inter
@dp.callback_query(F.data == "inter_back_to_letters")
async def inter_back_to_letters(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    fabric_type = data.get('fabric_type', '')
    await state.set_state(InterStates.choosing_letter)
    
    # Получаем все полотна для этого типа
    fabric_groups = inter_data.get_fabric_groups(fabric_type)
    fabric_names = list(fabric_groups.keys())
    
    # Получаем уникальные буквы
    letters = get_inter_fabric_letters(fabric_names)
    
    display_type = inter_data.get_display_name(fabric_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
    
    try:
        await callback.message.edit_text(
            text=f"Склад: Inter\n\nТип шторы: {display_type}\n\nВыберите первую букву названия полотна:",
            reply_markup=create_inter_letters_keyboard(letters)
        )
    except:
        await callback.message.answer(
            text=f"Склад: Inter\n\nТип шторы: {display_type}\n\nВыберите первую букву названия полотна:",
            reply_markup=create_inter_letters_keyboard(letters)
        )
    await callback.answer()

@dp.callback_query(F.data == "inter_back_to_types")
async def inter_back_to_types(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InterStates.choosing_fabric_type)
    try:
        await callback.message.edit_text(
            text="Склад: Inter\n\nВыберите тип шторы:",
            reply_markup=create_inter_fabric_types_keyboard()
        )
    except:
        await callback.message.answer(
            text="Склад: Inter\n\nВыберите тип шторы:",
            reply_markup=create_inter_fabric_types_keyboard()
        )
    await callback.answer()

# Удаляем inter_back_to_categories так как этот шаг больше не нужен

@dp.callback_query(F.data == "inter_back_to_fabrics")
async def inter_back_to_fabrics(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    fabric_type = data.get('fabric_type', '')
    await state.set_state(InterStates.choosing_fabric_name)
    
    display_type = inter_data.get_display_name(fabric_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
    
    # Проверяем, используется ли выбор по буквам для этого типа
    if fabric_type in ["Ткани плиссе", "Ткани рулонные", "Ткани вертикальные 89 мм", "Ткани Комбо"]:
        # Если есть отфильтрованные полотна, используем их
        filtered_fabrics = data.get('filtered_fabrics', [])
        selected_letter = data.get('selected_letter', '')
        
        if filtered_fabrics and selected_letter:
            try:
                await callback.message.edit_text(
                    text=f"Склад: Inter\n\nТип шторы: {display_type}\nБуква: {selected_letter}\n\nВыберите полотно:",
                    reply_markup=create_inter_fabric_by_letter_keyboard(filtered_fabrics)
                )
            except:
                await callback.message.answer(
                    text=f"Склад: Inter\n\nТип шторы: {display_type}\nБуква: {selected_letter}\n\nВыберите полотно:",
                    reply_markup=create_inter_fabric_by_letter_keyboard(filtered_fabrics)
                )
        else:
            # Возвращаемся к выбору букв
            await inter_back_to_letters(callback, state)
            return
    else:
        # Для остальных типов - обычная логика
        try:
            await callback.message.edit_text(
                text=f"Склад: Inter\n\nТип шторы: {display_type}\n\nВыберите полотно:",
                reply_markup=create_inter_fabric_categories_keyboard(fabric_type)
            )
        except:
            await callback.message.answer(
                text=f"Склад: Inter\n\nТип шторы: {display_type}\n\nВыберите полотно:",
                reply_markup=create_inter_fabric_categories_keyboard(fabric_type)
            )
    await callback.answer()

@dp.callback_query(F.data == "inter_back_to_colors")
async def inter_back_to_colors(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    fabric_type = data.get('fabric_type', '')
    fabric_name = data.get('fabric_name', '')
    await state.set_state(InterStates.choosing_color)
    
    display_type = inter_data.get_display_name(fabric_type, inter_data.FABRIC_TYPE_DISPLAY_NAMES)
    
    try:
        await callback.message.edit_text(
            text=f"Склад: Inter\n\nТип шторы: {display_type}\nПолотно: {fabric_name}\n\nВыберите цвет:",
            reply_markup=create_inter_colors_keyboard(fabric_type, "", fabric_name)
        )
    except:
        await callback.message.answer(
            text=f"Склад: Inter\n\nТип шторы: {display_type}\nПолотно: {fabric_name}\n\nВыберите цвет:",
            reply_markup=create_inter_colors_keyboard(fabric_type, "", fabric_name)
        )
    await callback.answer()

if __name__ == "__main__":
    async def main():
        # Удаляем webhook перед запуском polling
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Webhook удален успешно")
        except Exception as e:
            print(f"Ошибка при удалении webhook: {e}")
        
        await dp.start_polling(bot)
    
    asyncio.run(main())