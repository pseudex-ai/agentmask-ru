/* Pseudonym: solid ink passes over a word, the identity changes only while it
 * is fully covered. One visible text node per private word; hidden measurements
 * reserve BOTH widths so surrounding prose/code never shifts during a swap.
 * Fixed synthetic fixtures, not detection, a real transcript or tool execution.
 * A finite introduction; no timers, carousel, magnetic links or perpetual RAF. */
(function () {
  'use strict';
  const root = document.querySelector('[data-poster-demo]');
  if (!root || root.dataset.ppReady) return;
  root.dataset.ppReady = '1';
  const hero = root.closest('.pp-hero');
  const material = root.querySelector('[data-pp-material]');
  const source = root.querySelector('[data-pp-source]');
  const view = root.querySelector('[data-pp-view]');
  const action = root.querySelector('[data-pp-action]');
  const hint = root.querySelector('[data-pp-hint]');
  const nextFormat = root.querySelector('[data-pp-next-format]');
  const receipt = root.querySelector('[data-pp-receipt]');
  const toolName = root.querySelector('[data-pp-tool-name]');
  const toolCode = root.querySelector('[data-pp-tool-code]');
  const status = root.querySelector('[data-pp-status]');
  const tracks = [...hero.querySelectorAll('[data-pp-track]')];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const clamp = n => Math.max(0, Math.min(1, n));
  const smooth = n => n * n * (3 - 2 * n);
  const privatePart = (key, original, substitute, label, extra = {}) => ({key, original, substitute, label, ...extra});
  // New synthetic examples in benchmark register, NOT copied private cases.
  // Fixed runs are fixture annotations, not a detector: only actual notation
  // (prefixes, punctuation, markers, selected endings) is colored as preserved.
  const addressPart = (runs) => privatePart('address',
    runs.map(x => Array.isArray(x) ? x[0] : x).join(''),
    runs.map(x => Array.isArray(x) ? x[1] : x).join(''),
    'Адрес доставки', {wrap: 'words', runs});
  const namePart = (original, substitute, endings) => privatePart('name', original, substitute, 'Имя клиента', {form: 'name', endings});
  const phonePart = (original, substitute) => privatePart('phone', original, substitute, 'Телефон клиента', {form: 'phone'});
  const staff = namePart('морозову сергею', 'крылову андрею', ['у', 'ю']);
  const staffPhone = phonePart('+7 916 238-47-50', '+7 930 482-71-56');
  const customer = namePart('катя морозова', 'марина тихонова', ['', 'а']);
  const customerAddress = addressPart(['ул ', ['садовая', 'кедровая'], ' д', ['24', '57'], ' кв', ['8', '3']]);
  const customerPhone = phonePart('8-916-238-47-50', '8-930-482-71-56');
  // Existing never-issued coding-session fixtures. credentials.py recognizes
  // ghp_ + 36 characters; vault._fake_secret preserves prefix and every body's
  // digit/upper/lower position. A substitute does NOT authorize any request.
  const githubKey = privatePart('api-key',
    'ghp_A7m9K2p4R8v1T6x3B5n0C9d2F4g7H1j6L8q5',
    'ghp_H0t2R5w7Y1c4A9e6I8u3J2k5M7n0O4q9S1x8',
    'GitHub API-ключ', {prefix: 'ghp_', quoted: true});
  function companyScene(person, phone, register) {
    return {
      kind: 'prose', source: 'Запрос менеджера / ' + register,
      rows: [
        {className: 'pp-request-line', parts: ['глянь в CRM просрочку по', person]},
        {className: 'pp-request-contact', parts: ['телефон', phone]},
        {className: 'pp-request-continuation', parts: ['и накидай черновик напоминания, пока не отправляй']},
      ],
      tool: 'Внутри компании / разрешённое чтение CRM',
      result: ['Модель: get_open_invoices({ phone: "+79304827156" })\nCRM:    get_open_invoices({ phone: ', '"+79162384750"', ' })'],
      accessible: 'Корпоративная платформа, beta. Запрос менеджера проверить счета и подготовить черновик, не отправляя его. ' + person.original + ' заменено на ' + person.substitute + '; ' + phone.original + ' — на ' + phone.substitute + '. Форма имени и группировка телефона сохраняются. Права на чтение CRM задаёт приложение клиента; соответствия остаются в контуре. В аргумент возвращается исходный номер в записи агента E.164. Ничего не исполняется.',
    };
  }
  function serviceScene(person, address, phone, register) {
    const crm = register === 'заявка из CRM';
    return {
      kind: 'prose', source: 'Клиентский сервис / ' + register,
      rows: [
        {className: 'pp-request-line', parts: [crm ? 'Кофе зерновой, 1 кг × 2. Получатель:' : 'хочу 2 пачки кофе по 1 кг. я', person]},
        {className: 'pp-row-address', parts: [crm ? 'Доставка завтра:' : 'доставка завтра на', address]},
        {className: 'pp-request-contact', parts: [crm ? 'Телефон:' : 'перед приездом наберите', phone]},
      ],
      tool: 'Ваш сервис / аргументы create_order',
      result: ['create_order({ items: [{ product: "кофе зерновой 1 кг", quantity: 2 }],\n  recipient: ' + JSON.stringify(person.original) + ',\n  address: ' + JSON.stringify(address.original) + ',\n  phone: ', '"+79162384750"', ', delivery: "tomorrow" })'],
      accessible: 'Клиентский сервис. Новая заявка: две пачки кофе по одному килограмму, доставка завтра. ' + person.original + ' подменено на ' + person.substitute + '; адрес ' + address.original + ' — на ' + address.substitute + '; номер ' + phone.original + ' — на ' + phone.substitute + '. Товар и количество не меняются. Сохранены исходный регистр, порядок частей имени, маркеры адреса и разделители номера. Для разрешённого create_order возвращаются оригиналы. Заказ не создаётся, доставка и звонок не выполняются.',
    };
  }
  const scenes = {
    platform: companyScene(staff, staffPhone, 'чат'),
    service: serviceScene(customer, customerAddress, customerPhone, 'чат'),
    coding: {
      kind: 'code', source: 'Read / src/github.ts · вымышленный фрагмент',
      rows: [
        {className: 'pp-code-prefix', parts: ['const github = new Octokit({']},
        {className: 'pp-code-secret', parts: ['auth:', githubKey]},
        {className: 'pp-code-rest', parts: ['});']},
        {className: 'pp-code-rest', parts: ['await github.rest.issues.get(issue);']},
      ],
      tool: 'Исполнение в вашем контуре / иллюстрация',
      result: ['issues.get({ issue_number: 42 })\nАвторизация: ', 'process.env.GITHUB_TOKEN', '\nСекрет берётся локально для разрешённой операции, не из подмены в контексте модели. Код не исполняется.'],
      toolView: 'Оригинальный ключ остаётся локально',
      accessible: 'AI-кодинг, beta. В TypeScript подменяется не переменная, а GitHub API-ключ внутри строкового литерала. Префикс ghp_, общая длина 40 знаков и класс символа в каждой позиции сохранены. Синтаксис и имя auth не меняются. Для выполнения разрешённой операции credentials подаются локально, не восстановлением секрета в произвольный Bash или записью ключа в репозиторий. Это вымышленные никогда не выданные ключи, без исполнения кода.',
    },
  };
  const formats = {
    platform: [scenes.platform,
      companyScene(namePart('Морозову С. А.', 'Крылову А. П.', ['у', '', '']), phonePart('89162384750', '89304827156'), 'инициалы')],
    service: [scenes.service,
      serviceScene(namePart('Морозова Е. А.', 'Тихонова М. П.', ['а', '', '']),
        addressPart(['ул. ', ['Садовая', 'Кедровая'], ', д. ', ['24', '57'], ', кв. ', ['8', '3']]),
        phonePart('+7 916 238-47-50', '+7 930 482-71-56'), 'заявка из CRM')],
    coding: [scenes.coding],
  };
  let selected = 'platform', formatIndex = 0, progress = 0, mode = 'original';
  const currentScene = () => formats[selected][formatIndex];
  let animation = null, frame = 0, last = 0, drag = null;
  let visible = !('IntersectionObserver' in window), suppressClickUntil = 0;
  let buttons = [], shownModel = null, metadataState = null;

  function addText(parent, text, className) {
    const node = document.createElement('span');
    if (className) node.className = className;
    node.textContent = text; parent.append(node); return node;
  }
  function renderValue(node, text, part) {
    if (part.runs) {
      node.replaceChildren();
      const side = text === part.original ? 0 : 1;
      part.runs.forEach(run => addText(node, Array.isArray(run) ? run[side] : run, Array.isArray(run) ? '' : 'pp-affix'));
      return;
    }
    if (part.form === 'phone') {
      node.replaceChildren();
      const prefix = (text.match(/^(?:\+7|8|7)/) || [''])[0];
      if (prefix) addText(node, prefix, 'pp-affix');
      (text.slice(prefix.length).match(/\d+|[^\d]+/g) || []).forEach(run => {
        addText(node, run, /^\d+$/.test(run) ? '' : 'pp-affix');
      });
      return;
    }
    if (part.form === 'name') {
      node.replaceChildren();
      let index = 0;
      (text.match(/[\p{L}]+|[^\p{L}]+/gu) || []).forEach(run => {
        if (!/\p{L}/u.test(run)) { addText(node, run, 'pp-affix'); return; }
        const ending = part.endings[index++] || '';
        if (ending && run.endsWith(ending)) {
          addText(node, run.slice(0, -ending.length)); addText(node, ending, 'pp-affix');
        } else addText(node, run);
      });
      return;
    }
    if (!part.prefix) { node.textContent = text; return; }
    node.replaceChildren();
    if (part.quoted) addText(node, '"', 'pp-code-quote');
    addText(node, text.slice(0, part.prefix.length), 'pp-affix');
    // Legal visual wrapping points only: no ellipsis or newline is inserted
    // into the credential. The complete 40-character value stays copyable.
    const body = text.slice(part.prefix.length);
    for (let i = 0; i < body.length; i += 8) {
      node.append(document.createElement('wbr'));
      const close = part.quoted && i + 8 >= body.length ? '"' : '';
      addText(node, body.slice(i, i + 8) + close, 'pp-key-chunk');
    }
  }
  function word(part) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'pp-private';
    button.dataset.ppKey = part.key;
    button.dataset.ppOriginal = part.original;
    button.dataset.ppSubstitute = part.substitute;
    if (part.prefix) button.dataset.ppPrefix = part.prefix;
    if (part.wrap) button.dataset.ppWrap = part.wrap;
    const window = document.createElement('span'); window.className = 'pp-window';
    [part.original, part.substitute].forEach(text => {
      const measure = addText(window, '', 'pp-measure'); measure.setAttribute('aria-hidden', 'true');
      renderValue(measure, text, part);
    });
    const value = addText(window, '', 'pp-value');
    renderValue(value, part.original, part);
    const tape = document.createElement('span'); tape.className = 'pp-tape'; tape.setAttribute('aria-hidden', 'true');
    addText(tape, 'pseudex'); window.append(tape); button.append(window);
    const originText = part.prefix ? 'оригинальный ключ остаётся у вас' : 'у вас: ' + part.original;
    const original = addText(button, originText, 'pp-origin'); original.setAttribute('aria-hidden', 'true');
    button.addEventListener('click', event => {
      if (event.detail && performance.now() < suppressClickUntil) return;
      toggle();
    });
    button.addEventListener('keydown', event => {
      if (event.key === 'Escape') { endDrag(true); return; }
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault(); endDrag(true);
      const target = event.key === 'ArrowRight' || event.key === 'End' ? 1 : 0;
      go(target, target ? 'model' : 'tool');
    });
    buttons.push({button, value, part});
    return button;
  }
  function mount() {
    const scene = currentScene();
    buttons = []; shownModel = null; metadataState = null;
    const fragment = document.createDocumentFragment();
    scene.rows.forEach(row => {
      const line = document.createElement('p'); line.className = 'pp-row' + (row.className ? ' ' + row.className : '');
      row.parts.forEach(part => {
        if (typeof part === 'string') addText(line, part, /^[.,;:!?]/.test(part) ? 'pp-punctuation' : '');
        else line.append(word(part));
      });
      fragment.append(line);
    });
    material.replaceChildren(fragment); material.dataset.kind = scene.kind;
    source.textContent = scene.source;
    root.dataset.format = String(formatIndex);
    if (nextFormat) {
      nextFormat.hidden = formats[selected].length < 2;
      nextFormat.disabled = false;
      nextFormat.setAttribute('aria-label', 'Ещё формат. Сейчас пример ' + (formatIndex + 1) + ' из ' + formats[selected].length);
    }
    toolName.textContent = scene.tool;
    toolCode.replaceChildren(document.createTextNode(scene.result[0]));
    const original = document.createElement('b'); original.textContent = scene.result[1]; toolCode.append(original);
    toolCode.append(document.createTextNode(scene.result[2]));
    root.dataset.scene = selected;
    tracks.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.ppTrack === selected)));
    render(); announce();
  }
  function render() {
    const model = progress >= .5;
    if (model !== shownModel) {
      buttons.forEach(({button, value, part}) => {
        renderValue(value, model ? part.substitute : part.original, part);
        button.setAttribute('aria-label', part.label + ': ' + value.textContent + '. Нажмите или потяните для сравнения.');
      });
      shownModel = model;
    }
    root.style.setProperty('--pp-tape', ((progress * 2 - 1) * 104).toFixed(3) + '%');
    root.style.setProperty('--pp-origin', String(clamp((progress - .68) / .32)));
    const dragging = drag && drag.active;
    const state = dragging ? 'dragging' : animation ? animation.to ? 'masking' : 'restoring' : mode === 'tool' ? 'tool' : model ? 'model' : 'original';
    if (metadataState === state) return;
    metadataState = state;
    root.dataset.state = state;
    view.textContent = dragging || animation ? 'Другие значения. Тот же формат.' : state === 'tool' ? (currentScene().toolView || 'Инструмент получает оригинал') : model ? 'Так видит модель' : 'Исходный фрагмент';
    receipt.hidden = state !== 'tool';
    let label = 'Глазами модели';
    if (animation) label = 'Сразу показать';
    else if (state === 'tool') label = 'Снова модели';
    else if (model) label = 'А инструменту?';
    action.replaceChildren(document.createTextNode(label + ' '));
    const arrow = document.createElement('span'); arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = state === 'model' ? '↙' : '↗'; action.append(arrow);
    action.setAttribute('aria-label', label);
    const prompt = 'Потяните ' + (model ? 'влево' : 'вправо') + ' в любом месте.';
    hint.textContent = prompt;
  }
  function announce() {
    status.textContent = currentScene().accessible + ' Сейчас показан ' + (mode === 'tool' ? 'локальный вид для разрешённой операции.' : progress >= .5 ? 'контекст модели с подменой.' : 'исходный фрагмент.');
  }
  function cancelFrame() { cancelAnimationFrame(frame); frame = 0; last = 0; }
  function canRun() {
    if (!visible || document.hidden || reduce.matches) return false;
    if (drag && drag.active) return Math.abs(progress - drag.target) > .0005;
    return animation !== null;
  }
  function schedule() { if (!frame && canRun()) frame = requestAnimationFrame(paintPseudonym); }
  function settle() {
    if (animation) progress = animation.to;
    animation = null; cancelFrame(); render(); announce();
  }
  function go(target, nextMode, delay = 0) {
    cancelFrame(); mode = nextMode;
    if (reduce.matches || Math.abs(progress - target) < .001) {
      progress = target; animation = null; render(); announce(); return;
    }
    animation = {from: progress, to: target, elapsed: 0, delay, duration: 1300 * Math.max(.28, Math.abs(progress - target))};
    render(); schedule();
  }
  function paintPseudonym(now) {
    frame = 0;
    if (!canRun()) { last = 0; return; }
    if (drag && drag.active) {
      // One filtered progress drives BOTH ink and the covered text swap. A CSS
      // transition on ink alone would reveal the new identity before coverage.
      const dt = last ? Math.min(64, now - last) : 16.67;
      last = now;
      progress += (drag.target - progress) * (1 - Math.exp(-dt / 60));
      if (Math.abs(progress - drag.target) < .0005) progress = drag.target;
      render(); schedule();
      if (!frame) last = 0;
      return;
    }
    if (last) animation.elapsed += Math.min(64, now - last);
    last = now;
    const t = clamp((animation.elapsed - animation.delay) / animation.duration);
    progress = animation.from + (animation.to - animation.from) * smooth(t);
    if (t >= 1) { settle(); return; }
    render(); schedule();
  }
  function toggle() {
    if (animation) { settle(); return; }
    const target = progress >= .5 ? 0 : 1;
    go(target, target ? 'model' : 'tool');
  }
  function beginDrag(event) {
    if (!event.isPrimary || event.button !== 0 || drag) return;
    const word = event.target.closest('.pp-private');
    // A broad gesture surface must not become a blanket click interceptor.
    // Native links/controls and copyable tool arguments keep their own behavior.
    if (!word && event.target.closest('a,button,input,textarea,select,label,[contenteditable="true"],[role="button"],.pp-receipt')) return;
    drag = {id: event.pointerId, word, x: event.clientX, y: event.clientY,
      active: false, from: progress, target: progress, mode,
      distance: Math.max(140, Math.min(360, hero.clientWidth * .28))};
  }
  function moveDrag(event) {
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (!drag.active) {
      if (Math.abs(dy) > 8 && Math.abs(dy) > Math.abs(dx) * 1.15) {
        if (drag.word) suppressClickUntil = performance.now() + 350;
        drag = null; return; // Let native vertical touch scrolling own the gesture.
      }
      if (Math.abs(dx) <= 8 || Math.abs(dx) <= Math.abs(dy) * 1.15) return;
      cancelFrame(); animation = null;
      drag.active = true; drag.from = progress; drag.mode = mode;
      root.classList.add('is-dragging'); hero.classList.add('is-dragging');
      hero.setPointerCapture(event.pointerId);
      if (event.pointerType !== 'touch' && drag.word) drag.word.focus({preventScroll: true});
    }
    if (event.cancelable) event.preventDefault();
    drag.target = clamp(drag.from + dx / drag.distance);
    if (reduce.matches) { progress = drag.target; render(); }
    else { render(); schedule(); }
  }
  function endDrag(cancelled) {
    if (!drag) return;
    const previous = drag; drag = null;
    if (!previous.active) return; // A click/tap must not freeze or restart the intro.
    cancelFrame(); root.classList.remove('is-dragging'); hero.classList.remove('is-dragging');
    if (hero.hasPointerCapture(previous.id)) hero.releasePointerCapture(previous.id);
    suppressClickUntil = performance.now() + 350;
    // Settle toward finger intent, not the slightly lagging filtered position.
    // Otherwise a quick deliberate swipe could spring back to the wrong side.
    const target = (cancelled ? previous.from : previous.target) >= .5 ? 1 : 0;
    go(target, target ? 'model' : cancelled && previous.mode !== 'tool' ? 'original' : 'tool');
  }
  hero.addEventListener('pointerdown', beginDrag);
  addEventListener('pointermove', moveDrag, {passive: false});
  addEventListener('pointerup', event => { if (drag && drag.id === event.pointerId) endDrag(false); });
  addEventListener('pointercancel', event => { if (drag && drag.id === event.pointerId) endDrag(true); });
  hero.addEventListener('lostpointercapture', event => {
    if (event.target === hero && drag && drag.id === event.pointerId) endDrag(true);
  });
  addEventListener('keydown', event => { if (event.key === 'Escape' && drag) endDrag(true); });
  hero.addEventListener('click', event => {
    if (!event.detail || performance.now() >= suppressClickUntil) return;
    if (event.target.closest('a,button:not(.pp-private),input,textarea,select,.pp-receipt')) return;
    event.preventDefault(); event.stopPropagation();
  }, true);
  action.addEventListener('click', toggle);
  if (nextFormat) nextFormat.addEventListener('click', () => {
    endDrag(true); cancelFrame(); animation = null;
    formatIndex = (formatIndex + 1) % formats[selected].length;
    progress = reduce.matches ? 1 : 0; mode = reduce.matches ? 'model' : 'original';
    mount();
    if (!reduce.matches) go(1, 'model', 300);
  });
  tracks.forEach(button => button.addEventListener('click', () => {
    endDrag(true); cancelFrame(); animation = null;
    selected = button.dataset.ppTrack; formatIndex = 0; progress = reduce.matches ? 1 : 0;
    mode = reduce.matches ? 'model' : 'original'; mount();
    if (!reduce.matches) go(1, 'model', 300);
  }));
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      if (!visible) { cancelFrame(); endDrag(true); } else schedule();
    }, {threshold: .08});
    observer.observe(hero);
  }
  if ('ResizeObserver' in window) new ResizeObserver(() => { if (drag) endDrag(true); }).observe(material);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelFrame(); endDrag(true); } else schedule();
  });
  addEventListener('pagehide', () => { cancelFrame(); endDrag(true); });
  addEventListener('pageshow', schedule);
  reduce.addEventListener('change', () => { endDrag(true); if (reduce.matches) settle(); });
  progress = reduce.matches ? 1 : 0; mode = reduce.matches ? 'model' : 'original';
  mount(); hero.classList.add('is-interactive');
  action.disabled = false; tracks.forEach(button => { button.disabled = false; });
  if (!reduce.matches) go(1, 'model', 550);
}());
