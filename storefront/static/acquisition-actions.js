// Loaded only by the server's eligible-public-page gate, never as a URL-based
// substitute for that gate. This module has no provider or network dependency.
(function () {
    "use strict";
    if (window.__pseudexPublicActions) { return; }
    var config = document.querySelector('script[data-metrika-id]');
    if (!config || !/^[1-9][0-9]*$/.test(config.getAttribute('data-metrika-id') || '')) { return; }
    window.__pseudexPublicActions = true;
    var KEY = 'pseudex.analytics.consent';
    var sections = {
        '/': 'home', '/how': 'how', '/architecture': 'architecture',
        '/detection': 'detection', '/types': 'types', '/litellm': 'litellm',
        '/baza-znaniy': 'knowledge_base', '/faq': 'faq', '/i/': 'team',
        '/i/igor': 'team', '/i/gosha': 'team', '/i/slava': 'team',
        '/offer': 'offer', '/policy': 'privacy', '/requisites': 'requisites'
    };
    var docs = { '/docs': 'docs', '/how': 'how', '/architecture': 'architecture',
        '/litellm': 'litellm', '/baza-znaniy': 'knowledge_base' };
    // Exact published articles, not arbitrary slugs or user-controlled path data.
    ['kak-obezlichit-personalnye-dannye', 'transgranichnaya-peredacha',
        'obyazannosti-operatora', 'personalnye-dannye-v-chatgpt',
        'obezlichivanie-dlya-ii-agentov', 'blokirovanie-unichtozhenie-obezlichivanie',
        'dokumenty-dlya-obezlichivaniya', 'proverki-i-shtrafy', 'kak-vybrat-sistemu'
    ].forEach(function (slug) {
        sections['/baza-znaniy/' + slug] = 'knowledge_article';
        docs['/baza-znaniy/' + slug] = 'knowledge_article';
    });
    function own(map, key) { return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : null; }
    var section = own(sections, window.location.pathname);
    if (!section) { return; }
    var seenHeading = false, elapsed = 0, last = null, engaged = false;
    var consent = false, videoStates = [], faqPending = new WeakSet(), faqSent = new WeakSet();
    var configured = false, videoStarted = false, videoCompleted = false;
    function stored() {
        try { return window.localStorage.getItem(KEY) === 'yes'; } catch (ignore) { return false; }
    }
    function reset() {
        seenHeading = false; elapsed = 0; last = null; faqPending = new WeakSet();
        videoStates.forEach(function (s) { s.authorized = false; s.ranges = []; s.previous = null; s.gesture = null; });
    }
    function allowed() {
        var next = stored();
        if (next !== consent) { reset(); consent = next; }
        return next;
    }
    function foreground() { return document.visibilityState === 'visible' && document.hasFocus(); }
    function emit(name, params) {
        if (!allowed()) { return false; }
        try {
            document.dispatchEvent(new CustomEvent('pseudex:public-action', { detail: { name: name, params: params } }));
            return true;
        } catch (ignore) { return false; }
    }
    function headingVisible() {
        var heading = document.querySelector('h1, h2');
        if (!heading || !heading.getClientRects().length) { return false; }
        var rect = heading.getBoundingClientRect();
        var style = window.getComputedStyle(heading);
        if (style.visibility !== 'visible' || Number(style.opacity) === 0 || rect.width <= 0 || rect.height <= 0) { return false; }
        var width = Math.max(0, Math.min(rect.right, innerWidth) - Math.max(rect.left, 0));
        var height = Math.max(0, Math.min(rect.bottom, innerHeight) - Math.max(rect.top, 0));
        return width * height / (rect.width * rect.height) >= 0.5;
    }
    function tick() {
        if (!allowed()) { return; }
        var now = performance.now();
        if (!foreground()) { last = null; return; }
        // Seeing the heading is a prerequisite, not a demand to stare at it while
        // reading a long article. Suspended/throttled callbacks never backfill time.
        if (!seenHeading && headingVisible()) { seenHeading = true; last = now; }
        if (seenHeading && last !== null) { elapsed += Math.min(1000, Math.max(0, now - last)); }
        last = seenHeading ? now : null;
        if (!engaged && elapsed >= 20000) {
            engaged = emit('content_engaged', { section: section, threshold: '20s_visible' });
        }
    }
    function safe(fn) { return function (event) { try { fn(event); } catch (ignore) {} }; }
    document.addEventListener('pseudex:analytics-consent', safe(allowed));
    window.addEventListener('storage', safe(allowed));
    function pause() {
        last = null;
        videoStates.forEach(function (s) { s.previous = null; s.gesture = null; });
    }
    document.addEventListener('visibilitychange', safe(function () { allowed(); pause(); }));
    window.addEventListener('blur', pause);
    window.addEventListener('focus', safe(function () { last = null; tick(); }));
    window.addEventListener('pagehide', function () { reset(); });
    document.addEventListener('click', safe(function (event) {
        if (!allowed() || !event.isTrusted || !foreground()) { return; }
        var target = event.target;
        var link = target.closest && target.closest('a[href]');
        if (link && !link.hasAttribute('data-acquisition-goal')) {
            var url = new URL(link.getAttribute('href'), document.baseURI);
            if (url.origin === location.origin && !url.username && !url.password && /^https?:$/.test(url.protocol)) {
                var doc = own(docs, url.pathname);
                if (doc) { emit('docs_open', { doc: doc }); }
            }
        }
        var summary = target.closest && target.closest('summary');
        var details = summary && summary.parentElement;
        if (details && details.tagName === 'DETAILS' && !details.open &&
            ((section === 'home' && details.closest('#faq')) ||
             (section === 'faq' && details.closest('.faq-grid'))) && !faqSent.has(details)) {
            faqPending.add(details);
        }
    }));
    document.addEventListener('toggle', safe(function (event) {
        var details = event.target;
        if (!allowed() || !foreground() || !details.open || !faqPending.has(details)) { return; }
        faqPending.delete(details);
        if (emit('faq_open', { section: section })) { faqSent.add(details); }
    }), true);
    document.addEventListener('change', safe(function (event) {
        if (!allowed() || !event.isTrusted || !foreground() || configured || section !== 'detection') { return; }
        if (event.target.matches('#configurator #cfg input[type="checkbox"][data-group]') && event.target.checked) {
            configured = emit('configurator_used', { placement: 'configurator' });
        }
    }), true);
    function setupSource(video) {
        if (!video.currentSrc) { return false; }
        var url = new URL(video.currentSrc, document.baseURI);
        return url.origin === location.origin && !url.search && !url.hash &&
            /^\/static\/media\/setup(?:\.[a-f0-9]{8,64})?\.mp4$/.test(url.pathname);
    }
    function bindVideo(video) {
        var s = { authorized: false, ranges: [], previous: null, gesture: null };
        videoStates.push(s);
        function gesture(event) {
            if (allowed() && event.isTrusted && foreground() &&
                (event.type !== 'keydown' || [' ', 'Enter', 'k'].indexOf(event.key) !== -1)) {
                s.gesture = performance.now();
            }
        }
        video.addEventListener('pointerdown', safe(gesture));
        video.addEventListener('keydown', safe(gesture));
        video.addEventListener('play', safe(function (event) {
            if (!allowed() || !event.isTrusted || !foreground() || !setupSource(video) ||
                s.gesture === null || performance.now() - s.gesture > 2000) { return; }
            s.gesture = null; s.authorized = true;
            s.previous = { time: video.currentTime, wall: performance.now() };
            if (!videoStarted) { videoStarted = emit('setup_video_started', { placement: 'setup' }); }
        }));
        function sample() {
            if (!allowed() || !s.authorized || !setupSource(video)) { return; }
            var now = performance.now(), time = video.currentTime, prior = s.previous;
            s.previous = { time: time, wall: now };
            if (!foreground() || video.seeking || !prior) { return; }
            var delta = time - prior.time;
            // Only continuous media progress bounded by actual elapsed time earns
            // coverage. A seek cannot purchase completion; replay is unioned once.
            if (delta <= 0 || delta > (now - prior.wall) / 1000 * Math.max(1, video.playbackRate) + 0.25) { return; }
            s.ranges.push([prior.time, time]);
            s.ranges.sort(function (a, b) { return a[0] - b[0]; });
            var merged = [];
            s.ranges.forEach(function (range) {
                var tail = merged[merged.length - 1];
                if (tail && range[0] <= tail[1]) { tail[1] = Math.max(tail[1], range[1]); }
                else { merged.push(range.slice()); }
            });
            s.ranges = merged;
        }
        video.addEventListener('timeupdate', safe(sample));
        video.addEventListener('seeking', function () { s.previous = null; });
        video.addEventListener('seeked', function () { s.previous = null; });
        video.addEventListener('pause', safe(function () { sample(); s.previous = null; }));
        video.addEventListener('emptied', function () { s.authorized = false; s.ranges = []; s.previous = null; });
        video.addEventListener('ended', safe(function (event) {
            sample();
            if (!allowed() || !event.isTrusted || !s.authorized || !foreground() || !setupSource(video) || videoCompleted) { return; }
            var played = s.ranges.reduce(function (total, range) { return total + range[1] - range[0]; }, 0);
            if (Number.isFinite(video.duration) && video.duration > 0 && played >= video.duration * 0.8) {
                videoCompleted = emit('setup_video_completed', { placement: 'setup' });
            }
        }));
    }
    function start() {
        document.querySelectorAll('video').forEach(bindVideo);
        tick();
        window.setInterval(safe(tick), 250);
    }
    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', safe(start), { once: true }); }
    else { safe(start)(); }
}());
