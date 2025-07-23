// Улучшенный скрипт для получения cookies с проверкой авторизации
// Используйте этот скрипт, если основной не находит cookies

function checkAuthAndGetCookies() {
    console.log('🔍 РАСШИРЕННАЯ ДИАГНОСТИКА:');
    console.log('Текущий URL:', window.location.href);
    console.log('Домен:', window.location.hostname);
    console.log('Протокол:', window.location.protocol);
    
    // Проверяем, что мы на правильном сайте
    if (!window.location.hostname.includes('cortin.ru')) {
        console.log('❌ ОШИБКА: Вы не на сайте cortin.ru!');
        console.log('📍 Перейдите на https://sale.cortin.ru');
        return null;
    }
    
    // Проверяем настройки cookies в браузере
    console.log('\n🍪 ПРОВЕРКА НАСТРОЕК COOKIES:');
    console.log('navigator.cookieEnabled:', navigator.cookieEnabled);
    
    if (!navigator.cookieEnabled) {
        console.log('❌ Cookies отключены в браузере!');
        console.log('🔧 Включите cookies в настройках браузера');
        return null;
    }
    
    // Получаем все cookies
    const allCookies = document.cookie;
    console.log('Все cookies:', allCookies || 'ПУСТО');
    
    if (!allCookies) {
        console.log('\n❌ COOKIES НЕ НАЙДЕНЫ!');
        console.log('🔐 ВЫ НЕ АВТОРИЗОВАНЫ НА САЙТЕ');
        console.log('\n📋 ПОШАГОВАЯ ИНСТРУКЦИЯ:');
        console.log('1. Перейдите на главную страницу: https://sale.cortin.ru');
        console.log('2. Нажмите "Войти" или "Авторизация"');
        console.log('3. Введите логин и пароль');
        console.log('4. После успешного входа запустите скрипт заново');
        console.log('\n🔄 Или попробуйте:');
        console.log('   - Очистить cookies и кэш браузера');
        console.log('   - Перезагрузить страницу');
        console.log('   - Проверить блокировщики рекламы');
        
        // Проверяем, есть ли форма авторизации на странице
        const loginForm = document.querySelector('form[action*="login"]') || 
                         document.querySelector('input[type="password"]') ||
                         document.querySelector('.login-form') ||
                         document.querySelector('#login');
        
        if (loginForm) {
            console.log('\n✅ На странице найдена форма авторизации');
            console.log('👆 Авторизуйтесь и запустите скрипт заново');
        } else {
            console.log('\n🔍 Форма авторизации не найдена на текущей странице');
            console.log('📍 Перейдите на страницу входа: https://sale.cortin.ru/site/login');
        }
        
        return null;
    }
    
    // Парсим cookies
    const cookies = allCookies.split(';').reduce((acc, cookie) => {
        const [name, value] = cookie.trim().split('=');
        if (name && value) {
            acc[name] = value;
        }
        return acc;
    }, {});
    
    console.log('\n📋 Найденные cookies:', Object.keys(cookies));
    
    // Проверяем наличие нужных cookies
    const requiredCookies = {
        PHPSESSID: cookies.PHPSESSID || '',
        _identity: cookies._identity || ''
    };
    
    console.log('\n=== РЕЗУЛЬТАТ ===');
    console.log('PHPSESSID:', requiredCookies.PHPSESSID ? '✅ Найден' : '❌ Отсутствует');
    console.log('_identity:', requiredCookies._identity ? '✅ Найден' : '❌ Отсутствует');
    
    if (!requiredCookies.PHPSESSID || !requiredCookies._identity) {
        console.log('\n❌ НЕОБХОДИМЫЕ COOKIES НЕ НАЙДЕНЫ!');
        console.log('🔐 Это означает, что авторизация не завершена');
        console.log('\n🔄 РЕШЕНИЕ:');
        console.log('1. Убедитесь, что вы ПОЛНОСТЬЮ авторизованы');
        console.log('2. Проверьте, что вы можете видеть личный кабинет');
        console.log('3. Перезагрузите страницу после авторизации');
        console.log('4. Запустите скрипт заново');
        
        return null;
    }
    
    // Успех! Показываем cookies
    console.log('\n🎉 УСПЕХ! Cookies найдены:');
    console.log('PHPSESSID:', requiredCookies.PHPSESSID);
    console.log('_identity:', requiredCookies._identity.substring(0, 50) + '...');
    
    const jsonOutput = JSON.stringify(requiredCookies, null, 2);
    console.log('\n📋 JSON для копирования:');
    console.log(jsonOutput);
    
    // Функция копирования
    window.copyCortin = () => {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(jsonOutput).then(() => {
                    console.log('✅ Cookies скопированы!');
                }).catch(() => {
                    fallbackCopy();
                });
            } else {
                fallbackCopy();
            }
        } catch (err) {
            console.log('📋 Скопируйте JSON вручную');
        }
    };
    
    function fallbackCopy() {
        try {
            const tempTextArea = document.createElement('textarea');
            tempTextArea.value = jsonOutput;
            tempTextArea.style.position = 'fixed';
            tempTextArea.style.left = '-999999px';
            document.body.appendChild(tempTextArea);
            tempTextArea.select();
            document.execCommand('copy');
            document.body.removeChild(tempTextArea);
            console.log('✅ Cookies скопированы!');
        } catch (err) {
            console.log('📋 Скопируйте JSON вручную');
        }
    }
    
    // Автоматически копируем
    console.log('\n🔄 Автоматическое копирование...');
    fallbackCopy();
    
    console.log('\n💡 Команды:');
    console.log('   copyCortin() - повторить копирование');
    console.log('   checkAuthAndGetCookies() - запустить заново');
    
    return requiredCookies;
}

// Запускаем функцию
checkAuthAndGetCookies();