#!/bin/bash
# Скрипт для еженедельного обновления cookies
# Добавить в crontab: 0 2 * * 1 /path/to/update_cookies_weekly.sh

cd "/Users/user/Documents/deSmet researches/SunRay unified warehouse bot/SunRay_Unified"

# Логирование
echo "$(date): Запуск обновления cookies" >> cookies_update.log

# Запуск Python скрипта
python3 update_cookies.py >> cookies_update.log 2>&1

# Перезапуск бота если он запущен
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "$(date): Перезапуск бота" >> cookies_update.log
    pkill -f "python.*bot.py"
    sleep 2
    nohup python3 bot.py > bot.log 2>&1 &
    echo "$(date): Бот перезапущен" >> cookies_update.log
fi

echo "$(date): Обновление cookies завершено" >> cookies_update.log