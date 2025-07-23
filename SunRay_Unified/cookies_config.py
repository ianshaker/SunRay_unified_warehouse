# Конфигурация для системы управления cookies
# Этот файл содержит настройки для автоматического обновления и мониторинга

# Настройки мониторинга
MONITORING = {
    "check_interval_hours": 6,  # Проверка каждые 6 часов
    "max_cookie_age_days": 7,   # Максимальный возраст cookies
    "auto_update_enabled": False,  # Автоматическое обновление (пока отключено)
    "notification_enabled": True   # Уведомления о проблемах
}

# Настройки для тестирования cookies
TESTING = {
    "test_url": "https://sale.cortin.ru/mfg/stocks/materials",
    "timeout_seconds": 10,
    "retry_attempts": 3,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Пути к файлам
PATHS = {
    "cookies_file": "cortin_data.py",
    "backup_file": "cookies_backup.json",
    "log_file": "cookies_monitor.log",
    "error_log": "cookies_errors.log"
}

# Настройки уведомлений
NOTIFICATIONS = {
    "telegram_enabled": False,  # Уведомления в Telegram
    "email_enabled": False,     # Email уведомления
    "console_enabled": True     # Вывод в консоль
}

# Настройки безопасности
SECURITY = {
    "encrypt_backup": False,    # Шифрование backup файлов
    "secure_delete": True,      # Безопасное удаление временных файлов
    "log_sensitive_data": False # Логирование чувствительных данных
}

# Расписание автоматических проверок (cron формат)
SCHEDULE = {
    "daily_check": "0 2 * * *",      # Ежедневно в 2:00
    "weekly_update": "0 1 * * 1",    # Еженедельно в понедельник в 1:00
    "health_check": "*/30 * * * *"   # Каждые 30 минут
}