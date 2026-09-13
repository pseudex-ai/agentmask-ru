// Продуктовая аналитика: свой PostHog, на своём домене, на ПУБЛИЧНЫХ страницах.
//
// ОТДЕЛЬНЫЙ ФАЙЛ, А НЕ ВСТРОЕННЫЙ СКРИПТ, И ЭТО НЕ СТИЛЬ. CSP сайта — это
// `script-src 'self' <хост аналитики>` без `unsafe-inline`: встроенный тег
// PostHog из их документации просто не выполнился бы, а браузер сообщил бы об
// этом только в консоли. Настройки приходят data-атрибутами собственного тега.
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
    if (!host || !key || (mode !== "full" && mode !== "cookieless")) { return; }

    // СОГЛАСИЕ ХРАНИТСЯ У ПОСЕТИТЕЛЯ, А НЕ У НАС. В режиме `cookieless` его не
    // спрашивают вовсе: хранить нечего, значит и отказываться не от чего, а
    // баннер там, где выбора нет, — ритуал, а не соблюдение закона.
    var CONSENT = "pseudex.analytics.consent";
    function stored() {
        try { return window.localStorage.getItem(CONSENT); } catch (e) { return null; }
    }
    function remember(value) {
        try { window.localStorage.setItem(CONSENT, value); } catch (e) { /* приватное окно */ }
    }

    function boot(posthog) {
        posthog.init(key, {
            api_host: host,
            // ЗАПРОС УХОДИТ НА НАШ ЖЕ ДОМЕН. Иначе блокировщики режут его как
            // сторонний трекер, и цифры оказываются неполными ровно на той
            // аудитории, которая нам интереснее всего — на технической.
            ui_host: host,
            autocapture: true,
            capture_pageview: true,
            capture_pageleave: true,
            // Профиль человека заводится ТОЛЬКО для опознанных: анонимный
            // посетитель не должен порождать запись о себе.
            person_profiles: "identified_only",
            respect_dnt: true,
            // В режиме без куки состояние живёт в памяти вкладки: закрыл —
            // забыли. Воронка между визитами при этом не строится, и это
            // названная цена, а не недосмотр.
            persistence: mode === "full" ? "localStorage+cookie" : "memory",
            disable_session_recording: mode !== "full",
            session_recording: {
                // ПОЛЯ ВВОДА МАСКИРУЮТСЯ ВСЕГДА. На публичных страницах есть
                // форма регистрации, и человек печатает туда свою почту.
                // Запись, сохранившая её, была бы вторым местом хранения
                // персональных данных, заведённым ради удобства.
                maskAllInputs: true,
                maskTextSelector: "[data-private]",
                blockSelector: "[data-private]"
            },
            // Согласие спрашивается ДО первого события, а не после.
            opt_out_capturing_by_default: mode === "full" && stored() !== "yes",
            opt_out_capturing_persistence_type: "localStorage",
            loaded: function (ph) {
                if (mode === "cookieless") { ph.opt_in_capturing(); }
            }
        });
        window.posthog = posthog;
    }

    // Загрузчик PostHog — их же файл, с НАШЕГО хоста. Ставится тегом, а не
    // eval-ом строки: `unsafe-eval` пришлось бы разрешать в CSP.
    var script = document.createElement("script");
    script.src = host.replace(/\/+$/, "") + "/static/array.js";
    script.async = true;
    script.onload = function () {
        if (window.posthog) { boot(window.posthog); }
    };
    document.head.appendChild(script);

    // ── БАННЕР СОГЛАСИЯ ────────────────────────────────────────────────────
    // Появляется ТОЛЬКО в режиме `full` и только пока выбор не сделан. Две
    // равновеликие кнопки: отказ не должен быть мельче и бледнее согласия —
    // это и есть разница между выбором и его имитацией.
    if (mode !== "full" || stored()) { return; }

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
            if (answer === "yes" && window.posthog) { window.posthog.opt_in_capturing(); }
            if (answer === "no" && window.posthog) { window.posthog.opt_out_capturing(); }
            box.remove();
        });
    });
})();
