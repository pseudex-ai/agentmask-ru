// Продуктовая аналитика: свой Rybbit, на своём домене, на ПУБЛИЧНЫХ страницах.
//
// ОТДЕЛЬНЫЙ ФАЙЛ, А НЕ ВСТРОЕННЫЙ СКРИПТ, И ЭТО НЕ СТИЛЬ. CSP сайта — это
// `script-src 'self' <хост аналитики>` без `unsafe-inline`: встроенный тег из
// чужой документации просто не выполнился бы, а браузер сообщил бы об этом
// только в консоли. Настройки приходят data-атрибутами собственного тега.
//
// СКРИПТ АНАЛИТИКИ НЕ ГРУЗИТСЯ ДО СОГЛАСИЯ — вообще, а не «грузится и молчит».
// У PostHog был opt-out на стороне библиотеки; у Rybbit скрипт при загрузке
// сразу кладёт идентификатор посетителя в localStorage и шлёт pageview, и
// единственный честный способ «не считать» — не создавать тег. Поэтому тег
// создаётся в двух случаях: согласие уже сохранено, или человек только что
// нажал «Согласен».
//
// ЧЕГО ЗДЕСЬ НЕТ И НЕ БУДЕТ. Этот файл не подключается на страницах кабинета и
// админки — там на экране префиксы ключей и суммы счетов, и запись сессии
// сделала бы их копию, которую никто не заказывал. Что делают КЛИЕНТЫ, мы
// знаем из собственных серверных событий: каждое действие в кабинете это POST.
(function () {
    "use strict";

    var tag = document.currentScript;
    if (!tag) { return; }
    var host = tag.getAttribute("data-host");
    var key = tag.getAttribute("data-key");
    var mode = tag.getAttribute("data-mode");
    if (!host || !key || mode !== "full") { return; }

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
    function boot() {
        if (document.getElementById("rybbit-script")) { return; }
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

    if (stored() === "yes") { boot(); return; }
    if (stored() === "no") { return; }

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
            '<div class="consent-text">Мы считаем, что вы открываете и куда нажимаете, — своей аналитикой ' +
            'на своём сервере в России. Никаких Метрики, Google Analytics и пикселей. ' +
            'Поля ввода в записи не попадают. <a href="/policy">Политика</a>.</div>' +
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
