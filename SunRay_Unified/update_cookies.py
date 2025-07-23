#!/usr/bin/env python3
"""
Скрипт для автоматического обновления cookies для доступа к сайту Cortin.
Можно запускать еженедельно через cron.
"""

import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

def get_cookies_from_arc_database():
    """Получает cookies из базы данных Arc браузера"""
    
    # Путь к базе данных Arc (может отличаться в зависимости от версии)
    arc_paths = [
        "~/Library/Application Support/Arc/User Data/Default/Cookies",
        "~/Library/Application Support/Arc/User Data/Profile 1/Cookies",
        "~/Library/Application Support/Company/Arc/User Data/Default/Cookies"
    ]
    
    cookies_db_path = None
    for path in arc_paths:
        expanded_path = Path(path).expanduser()
        if expanded_path.exists():
            cookies_db_path = expanded_path
            break
    
    if not cookies_db_path:
        print("❌ Не удалось найти базу данных cookies Arc")
        return None
    
    try:
        # Создаем временную копию базы данных (Arc может блокировать доступ)
        temp_db = "/tmp/arc_cookies_temp.db"
        subprocess.run(["cp", str(cookies_db_path), temp_db], check=True)
        
        # Подключаемся к базе данных
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Запрос для получения cookies с сайта cortin.ru
        query = """
        SELECT name, value 
        FROM cookies 
        WHERE host_key LIKE '%cortin.ru%' 
        AND (name = 'PHPSESSID' OR name = '_identity')
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cookies = {}
        for name, value in results:
            cookies[name] = value
        
        conn.close()
        os.remove(temp_db)
        
        if 'PHPSESSID' in cookies and '_identity' in cookies:
            return cookies
        else:
            print("❌ Не найдены необходимые cookies в базе данных Arc")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка при чтении базы данных Arc: {e}")
        return None

def get_cookies_manual_input():
    """Получает cookies через ручной ввод"""
    print("\n=== РУЧНОЙ ВВОД COOKIES ===")
    print("1. Откройте Arc браузер")
    print("2. Перейдите на https://sale.cortin.ru")
    print("3. Авторизуйтесь на сайте")
    print("4. Откройте Developer Tools (F12 или Cmd+Option+I)")
    print("5. Перейдите на вкладку 'Application' -> 'Storage' -> 'Cookies' -> 'https://sale.cortin.ru'")
    print("6. Найдите cookies PHPSESSID и _identity")
    print("7. Скопируйте их значения и вставьте ниже")
    print("\nИли используйте JavaScript скрипт из файла get_cookies_extension.js\n")
    
    phpsessid = input("Введите значение PHPSESSID: ").strip()
    identity = input("Введите значение _identity: ").strip()
    
    if phpsessid and identity:
        return {
            'PHPSESSID': phpsessid,
            '_identity': identity
        }
    else:
        print("❌ Не все cookies введены")
        return None

def get_cookies_from_browser():
    """Получает cookies из браузера после авторизации"""
    
    # Настройки Chrome (для совместимости)
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Убрать эту строку если хотите видеть браузер
    # chrome_options.add_argument("--headless")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"❌ Не удалось запустить Chrome WebDriver: {e}")
        print("Используйте ручной ввод cookies")
        return None
    
    try:
        # Переходим на страницу авторизации
        driver.get("https://sale.cortin.ru/site/login")
        
        print("Откройте браузер и авторизуйтесь на сайте...")
        print("После авторизации нажмите Enter в консоли...")
        input("Нажмите Enter после авторизации: ")
        
        # Получаем cookies
        cookies = driver.get_cookies()
        
        # Извлекаем нужные cookies
        phpsessid = None
        identity = None
        
        for cookie in cookies:
            if cookie['name'] == 'PHPSESSID':
                phpsessid = cookie['value']
            elif cookie['name'] == '_identity':
                identity = cookie['value']
        
        if phpsessid and identity:
            return {
                'PHPSESSID': phpsessid,
                '_identity': identity
            }
        else:
            print("Не удалось найти необходимые cookies")
            return None
            
    finally:
        driver.quit()

def update_cookies_in_file(cookies_dict):
    """Обновляет cookies в файле cortin_data.py"""
    
    file_path = "cortin_data.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем PHPSESSID
    content = re.sub(
        r'"PHPSESSID":\s*"[^"]*"',
        f'"PHPSESSID": "{cookies_dict["PHPSESSID"]}"',
        content
    )
    
    # Заменяем _identity (экранируем специальные символы)
    identity_escaped = cookies_dict["_identity"].replace("\\", "\\\\").replace('"', '\\"')
    content = re.sub(
        r'"_identity":\s*"[^"]*"',
        f'"_identity": "{identity_escaped}"',
        content
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Cookies обновлены в файле {file_path}")

def main():
    """Основная функция"""
    print("🔄 Запуск обновления cookies для Arc браузера...")
    
    new_cookies = None
    
    # Способ 1: Попытка получить из базы данных Arc
    print("\n1️⃣ Попытка получения cookies из базы данных Arc...")
    new_cookies = get_cookies_from_arc_database()
    
    # Способ 2: Ручной ввод (если первый способ не сработал)
    if not new_cookies:
        print("\n2️⃣ Переход к ручному вводу cookies...")
        new_cookies = get_cookies_manual_input()
    
    # Способ 3: Selenium (если доступен Chrome WebDriver)
    if not new_cookies:
        print("\n3️⃣ Попытка получения через Selenium...")
        new_cookies = get_cookies_from_browser()
    
    if new_cookies:
        # Обновляем файл
        update_cookies_in_file(new_cookies)
        
        # Сохраняем backup cookies
        with open('cookies_backup.json', 'w', encoding='utf-8') as f:
            json.dump(new_cookies, f, ensure_ascii=False, indent=2)
        
        print("\n✅ Cookies успешно обновлены!")
        print("📁 Backup сохранен в cookies_backup.json")
        print("\n📋 Обновленные cookies:")
        print(f"PHPSESSID: {new_cookies['PHPSESSID'][:20]}...")
        print(f"_identity: {new_cookies['_identity'][:50]}...")
    else:
        print("\n❌ Не удалось получить cookies ни одним из способов")
        print("\n💡 Попробуйте:")
        print("1. Использовать JavaScript скрипт из get_cookies_extension.js")
        print("2. Скопировать cookies вручную из Developer Tools")
        print("3. Установить Chrome и ChromeDriver для Selenium")

if __name__ == "__main__":
    main()