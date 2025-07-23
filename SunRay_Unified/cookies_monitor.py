#!/usr/bin/env python3
"""
Система мониторинга cookies и автоматического обновления
"""

import json
import time
import requests
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cookies_monitor.log'),
        logging.StreamHandler()
    ]
)

class CookiesMonitor:
    def __init__(self):
        self.cookies_file = "cortin_data.py"
        self.test_url = "https://sale.cortin.ru/mfg/stocks/materials"
        self.backup_file = "cookies_backup.json"
        
    def load_current_cookies(self):
        """Загружает текущие cookies из файла"""
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Извлекаем cookies из Python файла
            import re
            phpsessid_match = re.search(r'"PHPSESSID":\s*"([^"]*)"', content)
            identity_match = re.search(r'"_identity":\s*"([^"]*)"', content)
            
            if phpsessid_match and identity_match:
                return {
                    'PHPSESSID': phpsessid_match.group(1),
                    '_identity': identity_match.group(1)
                }
            return None
        except Exception as e:
            logging.error(f"Ошибка загрузки cookies: {e}")
            return None
    
    def test_cookies_validity(self, cookies):
        """Проверяет валидность cookies"""
        try:
            response = requests.get(
                self.test_url,
                cookies=cookies,
                timeout=10,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )
            
            if response.status_code != 200:
                logging.warning(f"HTTP статус: {response.status_code}")
                return False
            
            text = response.text
            
            # Проверяем наличие данных о материалах
            has_data_material = 'data-material=' in text
            has_table = '<table' in text.lower()
            material_count = text.count('data-material=')
            
            # Проверяем заголовок страницы
            title_success = False
            title_start = text.find('<title>')
            title_end = text.find('</title>')
            if title_start != -1 and title_end != -1:
                title = text[title_start+7:title_end].lower()
                title_success = 'остатки' in title or 'материалы' in title
            
            # Проверяем признаки неудачной авторизации
            has_login_form = 'type="password"' in text or 'action="/site/login"' in text
            has_auth_redirect = 'авторизация' in text.lower() and 'остатки' not in text.lower()
            
            if has_login_form or has_auth_redirect:
                logging.warning("Обнаружена форма авторизации или редирект")
                return False
            
            # Успешная авторизация если есть данные и правильный заголовок
            if has_data_material and has_table and title_success and material_count > 100:
                logging.info(f"✅ Cookies валидны - найдено {material_count} материалов")
                return True
            else:
                logging.warning(f"❌ Недостаточно данных: materials={material_count}, table={has_table}, title={title_success}")
                return False
                
        except Exception as e:
            logging.error(f"Ошибка проверки cookies: {e}")
            return False
    
    def save_backup(self, cookies):
        """Сохраняет backup cookies"""
        try:
            backup_data = {
                'cookies': cookies,
                'timestamp': datetime.now().isoformat(),
                'status': 'valid'
            }
            
            with open(self.backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
                
            logging.info("Backup cookies сохранен")
        except Exception as e:
            logging.error(f"Ошибка сохранения backup: {e}")
    
    def check_cookies_status(self):
        """Основная функция проверки статуса cookies"""
        logging.info("Начинаем проверку cookies...")
        
        cookies = self.load_current_cookies()
        if not cookies:
            logging.error("Не удалось загрузить cookies")
            return False
        
        if not cookies['PHPSESSID'] or not cookies['_identity']:
            logging.warning("Cookies пустые - требуется обновление")
            return False
        
        is_valid = self.test_cookies_validity(cookies)
        
        if is_valid:
            logging.info("✅ Cookies валидны")
            self.save_backup(cookies)
            return True
        else:
            logging.warning("❌ Cookies устарели - требуется обновление")
            return False
    
    def get_cookies_age(self):
        """Возвращает возраст cookies в днях"""
        try:
            with open(self.backup_file, 'r', encoding='utf-8') as f:
                backup = json.load(f)
                
            timestamp = datetime.fromisoformat(backup['timestamp'])
            age = datetime.now() - timestamp
            return age.days
        except:
            return None

def main():
    monitor = CookiesMonitor()
    
    print("🔍 Проверка статуса cookies...")
    is_valid = monitor.check_cookies_status()
    
    age = monitor.get_cookies_age()
    if age is not None:
        print(f"📅 Возраст cookies: {age} дней")
        
        if age > 7:
            print("⚠️ Cookies старше 7 дней - рекомендуется обновление")
    
    if not is_valid:
        print("\n🔄 Требуется обновление cookies!")
        print("📋 Используйте:")
        print("   python quick_update_cookies.py")
        print("   или следуйте инструкции в AUTHORIZATION_GUIDE.md")
    else:
        print("\n✅ Cookies работают корректно")

if __name__ == "__main__":
    main()