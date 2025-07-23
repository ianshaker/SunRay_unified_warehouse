#!/usr/bin/env python3
"""
Быстрый скрипт для обновления cookies из Arc браузера
Использует только ручной ввод - самый надежный способ
"""

import json
import re

def update_cookies_in_file(cookies_dict):
    """Обновляет cookies в файле cortin_data.py"""
    
    file_path = "cortin_data.py"
    
    try:
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
        
        print(f"✅ Cookies обновлены в файле {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении файла: {e}")
        return False

def main():
    print("🔄 Быстрое обновление cookies для Arc браузера")
    print("=" * 50)
    print("📋 Инструкция:")
    print("1. Откройте Arc браузер")
    print("2. Перейдите на https://sale.cortin.ru")
    print("3. Авторизуйтесь на сайте")
    print("4. Нажмите F12 (или Cmd+Option+I)")
    print("5. Перейдите: Application → Storage → Cookies → https://sale.cortin.ru")
    print("6. Найдите PHPSESSID и _identity")
    print("7. Скопируйте их значения")
    print("=" * 50)
    
    # Получаем cookies от пользователя
    phpsessid = input("\n🔑 Введите PHPSESSID: ").strip()
    if not phpsessid:
        print("❌ PHPSESSID не может быть пустым")
        return
    
    identity = input("🔑 Введите _identity: ").strip()
    if not identity:
        print("❌ _identity не может быть пустым")
        return
    
    cookies = {
        'PHPSESSID': phpsessid,
        '_identity': identity
    }
    
    # Обновляем файл
    if update_cookies_in_file(cookies):
        # Сохраняем backup
        try:
            with open('cookies_backup.json', 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print("📁 Backup сохранен в cookies_backup.json")
        except Exception as e:
            print(f"⚠️ Не удалось сохранить backup: {e}")
        
        print("\n🎉 Готово! Cookies обновлены.")
        print("💡 Теперь перезапустите бота для применения изменений")
    else:
        print("\n❌ Не удалось обновить cookies")

if __name__ == "__main__":
    main()