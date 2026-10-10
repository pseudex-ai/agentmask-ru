// One public-page loader gates both providers; private-page exclusions and CSP
// remain server-owned. Provider scripts are not even requested without consent.
(function () {
    "use strict";

    var tag = document.currentScript;
    if (!tag || window.__pseudexAnalytics) { return; }
    var host = tag.getAttribute("data-host");
    var key = tag.getAttribute("data-key");
    var mode = tag.getAttribute("data-mode");
    var metrikaId = tag.getAttribute("data-metrika-id") || "";
    var goal = tag.getAttribute("data-goal") || "";
    var rybbit = Boolean(host && key && mode === "full");
    var metrika = Boolean(metrikaId);
    if (!rybbit && !metrika) { return; }

    // A document-level guard owns listeners as well as scripts. A second loader
    // must not turn one natural click into two goals or duplicate the dialog.
    window.__pseudexAnalytics = true;
    var CONSENT = "pseudex.analytics.consent";
    var acquisition = tag.getAttribute("data-acquisition-enabled") === "true";
    var REVISION = "acquisition-v1";
    var PENDING = "pseudex.analytics.revoke-pending";
    var csrf = tag.getAttribute("data-csrf") || "";
    function pending(value) {
        try {
            if (value !== undefined) { window.localStorage.setItem(PENDING, value ? "1" : "0"); }
            return window.localStorage.getItem(PENDING) === "1";
        } catch (e) { return false; }
    }
    function postPermission(path, data) {
        return fetch(path, { method: "POST", credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
            body: JSON.stringify(data) }).then(function (response) {
                if (!response.ok) { throw new Error("Permission not confirmed"); }
                return response.json();
            });
    }
    function permissionStatus(message) {
        var node = document.querySelector('[data-acquisition-status]');
        if (!node) {
            node = document.createElement("p");
            node.setAttribute("data-acquisition-status", "");
            node.setAttribute("role", "status");
            document.body.appendChild(node);
        }
        node.textContent = message;
    }
    var purposeGeneration = 0;
    function revokePermission() {
        purposeGeneration += 1;
        pending(true);
        permissionStatus("Серверный отзыв ещё не подтверждён. Ожидаем ответ; повторный отзыв доступен через «Отзыв связи с аналитикой».");
        return postPermission("/analytics/revoke", {}).then(function () {
            pending(false);
            permissionStatus("Серверный отзыв подтверждён. Ранее переданные данные автоматически не удалены.");
        }).catch(function () {
            permissionStatus("Серверный отзыв ещё не подтверждён. Повторите отзыв через «Отзыв связи с аналитикой». Локальный выбор счётчиков сохранён отдельно.");
        });
    }
    function grantPermission() {
        if (!acquisition || !enabled()) { return; }
        var generation = purposeGeneration;
        var finished = false;
        function current() { return generation === purposeGeneration && stored() === "yes"; }
        var timer = window.setTimeout(function () {
            finished = true;
            if (current()) {
                permissionStatus("Сервер не подтвердил связь. Регистрация доступна без неё; отзыв доступен в настройках аналитики.");
            }
        }, 2500);
        // A prepared receipt carries no ClientID and is inactive. Its HttpOnly
        // cookie must be acknowledged before either SDK lookup or grant POST:
        // revoke can then lock that exact row, even while grant is in flight.
        postPermission("/analytics/prepare", { purpose_revision: REVISION,
            affirmative: "1", browser_consent: "yes" }).then(function () {
            if (finished || !current()) { return; }
            // Official getClientID returns a STRING. Never round through Number.
            window.ym(metrikaId, "getClientID", function (clientID) {
                if (finished || !current()) { return; }
                finished = true;
                if (typeof clientID !== "string" || !/^[0-9]{1,32}$/.test(clientID)) {
                    window.clearTimeout(timer);
                    permissionStatus("Связь не включена: идентификатор недоступен. Регистрация доступна.");
                    return;
                }
                if (!current()) { return; }
                postPermission("/analytics/grant", { purpose_revision: REVISION,
                    affirmative: "1", browser_consent: "yes", client_id: clientID }).then(function () {
                    window.clearTimeout(timer);
                    if (current()) { permissionStatus("Разрешение связи сохранено; оно предварительное до подтверждения почты."); }
                }).catch(failed);
            });
        }).catch(failed);
        function failed() {
            finished = true;
            window.clearTimeout(timer);
            if (current()) { permissionStatus("Сервер не подтвердил разрешение связи. Регистрация доступна без него."); }
        }
    }
    var booted = false;
    var signupSent = false;
    var pricingSent = false;
    var pricingObserver = null;
    var dialog = null;
    var preferenceButton = null;

    function stored() {
        try { return window.localStorage.getItem(CONSENT); } catch (e) { return null; }
    }
    function remember(value) {
        try {
            window.localStorage.setItem(CONSENT, value);
            document.dispatchEvent(new CustomEvent("pseudex:analytics-consent"));
            return stored() === value;
        } catch (e) { return false; }
    }
    function enabled() {
        return metrika && booted && stored() === "yes" && typeof window.ym === "function";
    }

    // Closed schemas, not arbitrary DOM goal names or spread event.detail.
    // Every transmitted value is a fixed enum; URLs, contact fields, input text,
    // copied commands and query contents never enter a custom goal payload.
    var PLANS = ["free", "start", "work", "scale", "industrial", "enterprise"];
    var SCHEMAS = {
        start_cta_click: { placement: ["header", "hero", "pricing", "bottom"] },
        pricing_view: { placement: ["pricing"] },
        signup_attempt: { placement: ["signup"], plan: PLANS },
        plan_selected: { placement: ["signup"], plan: PLANS },
        integration_copy: { placement: ["onboarding"], source: ["agent_prompt"] },
        enterprise_contact_click: { placement: ["pricing"], channel: ["email", "telegram", "requisites"] },
        support_contact_click: { placement: ["floating", "faq", "footer"], channel: ["email", "telegram", "feedback"] },
        docs_open: { doc: ["docs", "how", "architecture", "litellm", "knowledge_base", "knowledge_article"] },
        content_engaged: { section: ["home", "how", "architecture", "detection", "types", "litellm", "knowledge_base", "knowledge_article", "faq", "team", "offer", "privacy", "requisites"], threshold: ["20s_visible"] },
        setup_video_started: { placement: ["setup"] },
        setup_video_completed: { placement: ["setup"] },
        faq_open: { section: ["faq", "home"] },
        configurator_used: { placement: ["configurator"] }
    };
    function reach(name, params) {
        if (!enabled() || !params || typeof params !== "object" || !Object.prototype.hasOwnProperty.call(SCHEMAS, name)) { return false; }
        var schema = SCHEMAS[name];
        var clean = {};
        var fields = Object.keys(schema);
        for (var i = 0; i < fields.length; i++) {
            var field = fields[i];
            if (schema[field].indexOf(params[field]) === -1) { return false; }
            clean[field] = params[field];
        }
        window.ym(metrikaId, "reachGoal", name, clean);
        return true;
    }

    document.addEventListener("pseudex:public-action", function (event) {
        var detail = event.detail;
        if (!detail || ["content_engaged", "setup_video_started", "setup_video_completed", "faq_open", "configurator_used", "docs_open"].indexOf(detail.name) === -1) { return; }
        reach(detail.name, detail.params);
    });

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
            webvisor: true
        });
    }
    function observePricing() {
        if (!enabled() || pricingSent || pricingObserver || !("IntersectionObserver" in window)) { return; }
        var pricing = document.querySelector("#pricing [data-acquisition-pricing]");
        if (!pricing) { return; }
        // Observe the visible heading, not the entire tall section or a 200
        // render. No fallback invents a view when observation is unavailable.
        pricingObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting || entry.intersectionRatio < 0.5) { return; }
                if (reach("pricing_view", { placement: "pricing" })) {
                    pricingSent = true;
                    pricingObserver.disconnect();
                }
            });
        }, { threshold: 0.5 });
        pricingObserver.observe(pricing);
    }
    function boot() {
        if (booted || stored() !== "yes") { return; }
        booted = true;
        bootRybbit();
        bootMetrika();
        // Only the server-rendered successful signup may convert; resend and
        // form attempts do not. This legacy goal remains once per document.
        if (enabled() && goal === "signup" && !signupSent) {
            signupSent = true;
            window.ym(metrikaId, "reachGoal", "signup");
        }
        if (document.readyState !== "loading") { observePricing(); }
    }

    document.addEventListener("click", function (event) {
        var link = event.target.closest && event.target.closest("a[data-acquisition-goal]");
        if (!link) { return; }
        var name = link.getAttribute("data-acquisition-goal");
        // Non-click goals cannot be manufactured by annotating an arbitrary link.
        if (["start_cta_click", "enterprise_contact_click", "support_contact_click", "docs_open"].indexOf(name) === -1) { return; }
        reach(name, {
            placement: link.getAttribute("data-acquisition-placement"),
            channel: link.getAttribute("data-acquisition-channel"),
            doc: link.getAttribute("data-acquisition-doc")
        });
    });
    document.addEventListener("submit", function (event) {
        if (!event.target.matches("#signup-form")) { return; }
        var plan = event.target.querySelector('input[type="radio"][name="plan"]:checked');
        reach("signup_attempt", { placement: "signup", plan: plan && plan.value });
    });
    // Pricing CTAs dispatch a non-bubbling radio change, so capture also covers
    // that existing path without adding a second plan-specific click handler.
    document.addEventListener("change", function (event) {
        if (!event.target.matches('#signup-form input[type="radio"][name="plan"]') || !event.target.checked) { return; }
        reach("plan_selected", { placement: "signup", plan: event.target.value });
    }, true);
    document.addEventListener("pseudex:integration-copy", function (event) {
        var source = event.target;
        if (!source.matches || !source.matches('#start [data-copy][data-integration-copy="agent_prompt"]')) { return; }
        // The source is explicitly public. Event detail is deliberately ignored.
        reach("integration_copy", { placement: "onboarding", source: "agent_prompt" });
    });

    var providers = [];
    if (rybbit) { providers.push("своя аналитика на нашем сервере в России"); }
    if (metrika) { providers.push("Яндекс.Метрика с записью экрана (Вебвизор)"); }
    var text = "С вашего согласия мы считаем открытия и нажатия: " + providers.join(" и ") +
        ". Поля ввода маскируются. Выбор можно изменить кнопкой «Настройки аналитики» внизу страницы. " +
        "Отказ остановит дальнейшую запись после перезагрузки страницы, но не удалит уже собранные данные. ";

    function closeDialog() {
        if (dialog) { dialog.remove(); dialog = null; }
        if (preferenceButton) { preferenceButton.focus({ preventScroll: true }); }
    }
    function withdraw() {
        if (pricingObserver) { pricingObserver.disconnect(); }
        // Destroy the whole loaded document rather than promising that removing
        // script tags stops replay. Navigation is GET even after a signup POST;
        // do not resend a form or carry its query contents into a new page.
        window.location.replace(window.location.origin + window.location.pathname);
    }
    function showDialog() {
        if (dialog) { return; }
        dialog = document.createElement("div");
        dialog.className = "consent-bar";
        dialog.setAttribute("role", "dialog");
        dialog.setAttribute("aria-label", "Аналитика");
        dialog.innerHTML =
            '<div class="consent-text">' + text + '<a href="/policy">Политика</a>.</div>' +
            (acquisition ? '<label><input type="checkbox" data-acquisition-purpose> Отдельно согласен (acquisition-v1) связать публичный визит с новым аккаунтом, подтверждением почты, первым ключом, первым наблюдением аренды и маскирования и первой подтверждённой оплатой с суммой. До 21 дня; без продлений и дальнейшего использования. <a href="/policy#acquisition">Условия</a></label>' : '') +
            '<div class="consent-buttons">' +
            '<button type="button" class="btn" data-consent="no">Не считать</button>' +
            '<button type="button" class="btn" data-consent="yes">Согласен</button>' +
            '<button type="button" class="btn" data-consent-close>Закрыть</button></div>';
        document.body.appendChild(dialog);
        dialog.addEventListener("click", function (event) {
            var button = event.target.closest("button");
            if (!button) { return; }
            if (button.hasAttribute("data-consent-close")) { closeDialog(); return; }
            var answer = button.getAttribute("data-consent");
            if (answer !== "yes" && answer !== "no") { return; }
            // Every purpose choice invalidates earlier asynchronous work, even
            // browser-yes with purpose unchecked (browser consent is separate).
            purposeGeneration += 1;
            if (!remember(answer)) {
                dialog.querySelector(".consent-text").textContent =
                    "Не удалось сохранить выбор в браузере. Текущий выбор не изменён. Проверьте настройки хранилища браузера и повторите.";
                return;
            }
            var purpose = dialog.querySelector('[data-acquisition-purpose]');
            var affirmative = purpose && purpose.checked;
            closeDialog();
            if (answer === "yes") {
                boot();
                if (acquisition && affirmative) { grantPermission(); }
                else if (acquisition) { revokePermission(); }
            } else if (acquisition) {
                pending(true);
                // Leave provider-loaded DOM immediately. The clean GET resumes
                // the CSRF POST and truthfully reports a pending server failure.
                if (booted) { withdraw(); }
                else { revokePermission(); }
            } else if (booted) { withdraw(); }
        });
        dialog.querySelector('[data-consent="no"]').focus({ preventScroll: true });
    }
    function ready() {
        preferenceButton = document.querySelector("[data-analytics-preferences]");
        if (preferenceButton) {
            preferenceButton.hidden = false;
            preferenceButton.addEventListener("click", showDialog);
        }
        observePricing();
        if (pending()) { revokePermission(); }
        if (stored() !== "yes" && stored() !== "no") { showDialog(); }
    }
    window.addEventListener("storage", function (event) {
        if ((event.key === CONSENT || event.key === null) && stored() !== "yes" && booted) { withdraw(); }
    });
    window.addEventListener("pageshow", function (event) {
        // A back/forward-cache restore can revive a provider-loaded document
        // after consent was withdrawn on another public page.
        if (event.persisted && booted && stored() !== "yes") { withdraw(); }
    });
    if (stored() === "yes") { boot(); }
    if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", ready, { once: true }); }
    else { ready(); }
})();
