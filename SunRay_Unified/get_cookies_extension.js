// Скрипт для получения cookies через консоль браузера Arc
// 1. Откройте сайт https://sale.cortin.ru в Arc
// 2. Авторизуйтесь на сайте
// 3. Откройте Developer Tools (F12 или Cmd+Option+I)
// 4. Вставьте этот код в консоль и нажмите Enter

function getCookiesForCortin() {
    console.log('🔍 ДИАГНОСТИКА:');
    console.log('Текущий URL:', window.location.href);
    console.log('Домен:', window.location.hostname);
    console.log('Протокол:', window.location.protocol);
    
    // Проверяем, что мы на правильном сайте
    if (!window.location.hostname.includes('cortin.ru')) {
        console.log('❌ ОШИБКА: Вы не на сайте cortin.ru!');
        console.log('📍 Перейдите на https://sale.cortin.ru и авторизуйтесь');
        return null;
    }
    
    // Получаем все cookies для текущего домена
    const allCookies = document.cookie;
    console.log('Все cookies:', allCookies);
    
    if (!allCookies) {
        console.log('❌ ОШИБКА: Cookies не найдены!');
        console.log('🔐 Убедитесь, что вы авторизованы на сайте');
        console.log('🍪 Проверьте настройки cookies в браузере');
        return null;
    }
    
    const cookies = allCookies.split(';').reduce((acc, cookie) => {
        const [name, value] = cookie.trim().split('=');
        if (name && value) {
            acc[name] = value;
        }
        return acc;
    }, {});
    
    console.log('Найденные cookies:', Object.keys(cookies));
    
    // Извлекаем нужные cookies
    const requiredCookies = {
        PHPSESSID: cookies.PHPSESSID || '',
        _identity: cookies._identity || ''
    };
    
    console.log('\n=== COOKIES ДЛЯ CORTIN ===');
    console.log('PHPSESSID:', requiredCookies.PHPSESSID);
    console.log('_identity:', requiredCookies._identity ? requiredCookies._identity.substring(0, 50) + '...' : '');
    console.log('========================');
    
    // Проверяем, что cookies найдены
    if (!requiredCookies.PHPSESSID || !requiredCookies._identity) {
        console.log('❌ ПРОБЛЕМА: Необходимые cookies не найдены!');
        console.log('🔐 Убедитесь, что вы авторизованы на сайте sale.cortin.ru');
        console.log('🔄 Попробуйте:');
        console.log('   1. Перезагрузить страницу');
        console.log('   2. Выйти и войти заново');
        console.log('   3. Очистить cookies и авторизоваться снова');
        return null;
    }
    
    // Создаем JSON для копирования
    const jsonOutput = JSON.stringify(requiredCookies, null, 2);
    console.log('\n📋 JSON для копирования:');
    console.log(jsonOutput);
    
    // Создаем глобальную функцию для копирования
    window.copyCortin = () => {
        try {
            // Пробуем современный API
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(jsonOutput).then(() => {
                    console.log('✅ Cookies скопированы через clipboard API!');
                }).catch(() => {
                    // Fallback к старому методу
                    copyWithExecCommand();
                });
            } else {
                copyWithExecCommand();
            }
        } catch (err) {
            console.log('❌ Ошибка копирования:', err);
            console.log('📋 Скопируйте JSON вручную из вывода выше');
        }
    };
    
    function copyWithExecCommand() {
        try {
            const tempTextArea = document.createElement('textarea');
            tempTextArea.value = jsonOutput;
            tempTextArea.style.position = 'fixed';
            tempTextArea.style.left = '-999999px';
            tempTextArea.style.top = '-999999px';
            document.body.appendChild(tempTextArea);
            tempTextArea.focus();
            tempTextArea.select();
            
            const successful = document.execCommand('copy');
            document.body.removeChild(tempTextArea);
            
            if (successful) {
                console.log('✅ Cookies скопированы через execCommand!');
            } else {
                console.log('📋 Скопируйте JSON вручную из вывода выше');
            }
        } catch (err) {
            console.log('📋 Скопируйте JSON вручную из вывода выше');
        }
    }
    
    // Автоматически пробуем скопировать
    console.log('\n🔄 Попытка автоматического копирования...');
    copyWithExecCommand();
    
    console.log('\n💡 Команды:');
    console.log('   copyCortin() - повторить копирование');
    console.log('   getCookiesForCortin() - запустить заново');
    
    return requiredCookies;
}

// Запускаем функцию
getCookiesForCortin();