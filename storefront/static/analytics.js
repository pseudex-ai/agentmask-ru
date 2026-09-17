// Счётчики на сайте: свой Rybbit и/или Яндекс.Метрика, на ПУБЛИЧНЫХ страницах.
//
// ОТДЕЛЬНЫЙ ФАЙЛ, А НЕ ВСТРОЕННЫЙ СКРИПТ, И ЭТО НЕ СТИЛЬ. CSP сайта — это
// `script-src 'self' <разрешённое>` без `unsafe-inline`: встроенный тег из чужой
// документации просто не выполнился бы, а браузер сообщил бы об этом только в
// консоли. Настройки приходят data-атрибутами собственного тега.
//
// ПОЧЕМУ МЕТРИКА ЗДЕСЬ, А НЕ В ОТДЕЛЬНОМ ФАЙЛЕ. Согласие — одно на сайт, и
// баннер — один. Два загрузчика означали бы два баннера (или, что хуже, один
// баннер и один счётчик, который про согласие не знает). Шлюз согласия живёт в
// одном месте, и счётчики проходят через него все.
//
// СКРИПТ НЕ ГРУЗИТСЯ ДО СОГЛАСИЯ — вообще, а не «грузится и молчит». У Rybbit
// скрипт при загрузке сразу кладёт идентификатор посетителя в localStorage и
// шлёт pageview; у Метрики то же самое с её кукой. Единственный честный способ
// «не считать» — не создавать тег. Поэтому теги создаются в двух случаях:
// согласие уже сохранено, или человек только что нажал «Согласен».
//
// ЧЕГО ЗДЕСЬ НЕТ И НЕ БУДЕТ. Этот файл не подключается на страницах кабинета и
// админки — там на экране префиксы ключей и суммы счетов, и запись сессии
// сделала бы их копию, которую никто не заказывал. Что делают КЛИЕНТЫ, мы
// знаем из собственных серверных событий: каждое действие в кабинете это POST.
// Граница продублирована в CSP (`middleware._policy_for`), поэтому даже ошибка
// в этом файле не пустила бы `mc.yandex.ru` на закрытую страницу.
(function () {
    "use strict";

    var tag = document.currentScript;
    if (!tag) { return; }
    var host = tag.getAttribute("data-host");
    var key = tag.getAttribute("data-key");
    var mode = tag.getAttribute("data-mode");
    var metrikaId = tag.getAttribute("data-metrika-id") || "";

    var rybbit = Boolean(host && key && mode === "full");
    var metrika = Boolean(metrikaId);
    if (!rybbit && !metrika) { return; }

    // СОГЛАСИЕ ХРАНИТСЯ У ПОСЕТИТЕЛЯ, А НЕ У НАС. Запись «кто согласился» на
    // сервере была бы ещё одним профилем посетителя — ровно тем, чего баннер
    // призван не создавать. localStorage сайта, «нет» помнится так же, как «да».
    var CONSENT = "pseudex.analytics.consent";
    function stored() {
        try { return window.localStorage.getItem(CONSENT); } catch (e) { return null; }
    }
    function remember(value) {
        try { window.localStorage.setItem(CONSENT, value); } catch (e) { /* приватное окно */ }
    }

    // Загрузчик Rybbit — их же файл, с НАШЕГО хоста аналитики. Все настройки
    // записи — атрибутами: поля ввода маскируются ЦЕЛИКОМ (не «пароли», а всё,
    // что печатают), включая форму регистрации. Сэмплирование не включаем:
    // трафик витрины — сотни визитов в день, и «каждый десятый» здесь значил
    // бы «почти никто».
    function bootRybbit() {
        if (!rybbit || document.getElementById("rybbit-script")) { return; }
        var script = document.createElement("script");
        script.id = "rybbit-script";
        script.src = host.replace(/\/$/, "") + "/api/script.js";
        script.async = true;
        script.defer = true;
        script.setAttribute("data-site-id", key);
        script.setAttribute("data-replay-mask-all-inputs", "true");
        script.setAttribute("data-replay-mask-text-selectors", JSON.stringify(["[data-private]"]));
        document.head.appendChild(script);
    }

    // МЕТРИКА. `webvisor` ВЫКЛЮЧЕН НАМЕРЕННО, и это расходится с их же
    // рекомендацией по умолчанию. Вебвизор записывает движение по странице и
    // то, что человек на ней делает; продукт продаёт минимизацию данных, и
    // запись экрана посетителя — самый заметный способ ей изменить. Кликмап и
    // карта ссылок остаются: они дают агрегат («сюда нажимают»), а не запись.
    // Включать Вебвизор — решение владельца, и принимать его надо осознанно.
    function bootMetrika() {
        if (!metrika || window.__pseudexMetrika) { return; }
        window.__pseudexMetrika = true;
        (function (m, e, t, r, i, k, a) {
            m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
            m[i].l = 1 * new Date();
            for (var j = 0; j < document.scripts.length; j++) {
                if (document.scripts[j].src === r) { return; }
            }
            k = e.createElement(t); a = e.getElementsByTagName(t)[0];
            k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
        })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
        window.ym(metrikaId, "init", {
            clickmap: true,
            trackLinks: true,
            accurateTrackBounce: true,
            webvisor: false
        });
    }

    function boot() { bootRybbit(); bootMetrika(); }

    if (stored() === "yes") { boot(); return; }
    if (stored() === "no") { return; }

    // ТЕКСТ БАННЕРА СОБИРАЕТСЯ ИЗ ТОГО, ЧТО ВКЛЮЧЕНО. Он называет счётчики по
    // именам, и копия, написанная рядом с настройкой, разошлась бы с ней молча:
    // страница обещала бы «никакой Метрики» ровно на том сайте, где она стоит.
    // Здесь обещание не может разойтись с кодом — оно из него и берётся.
    var text = metrika
        ? "Мы считаем, что вы открываете и куда нажимаете: своя аналитика на нашем " +
          "сервере в России" + (rybbit ? "" : "") + " и Яндекс.Метрика. Вебвизор " +
          "выключен — запись экрана не ведётся. Поля ввода в записи не попадают. "
        : "Мы считаем, что вы открываете и куда нажимаете, — своей аналитикой " +
          "на своём сервере в России. Никаких Метрики, Google Analytics и пикселей. " +
          "Поля ввода в записи не попадают. ";

    // БАННЕР — ТОЛЬКО ПОКА ОТВЕТА НЕТ, и «Не считать» на нём — такая же кнопка,
    // как «Согласен»: не мельче, не серее, не спрятана в «настройки». Отказ в
    // один клик, как и согласие, — это и есть разница между выбором и его
    // имитацией.
    document.addEventListener("DOMContentLoaded", function () {
        var box = document.createElement("div");
        box.className = "consent-bar";
        box.setAttribute("role", "dialog");
        box.setAttribute("aria-label", "Аналитика");
        box.innerHTML =
            '<div class="consent-text">' + text +
            '<a href="/policy">Политика</a>.</div>' +
            '<div class="consent-buttons">' +
            '<button type="button" class="btn" data-consent="no">Не считать</button>' +
            '<button type="button" class="btn accent" data-consent="yes">Согласен</button>' +
            "</div>";
        document.body.appendChild(box);
        box.addEventListener("click", function (event) {
            var answer = event.target.getAttribute && event.target.getAttribute("data-consent");
            if (!answer) { return; }
            remember(answer);
            if (answer === "yes") { boot(); }
            box.remove();
        });
    });
})();
