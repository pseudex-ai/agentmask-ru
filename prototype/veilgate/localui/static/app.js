/* The operator interface. Six screens over the engine's own API.
 *
 * Preact + htm, no build step and no bundler. Two reasons, and the first is not
 * about convenience: every screen here renders values that came out of the
 * customer's own traffic — token previews, revealed values, agent names. With
 * string concatenation into innerHTML, a name containing markup would execute
 * as script in a page holding a session that can reveal personal data. Preact
 * escapes text children by default, so the whole class of bug is gone by
 * construction rather than by remembering to escape at 40 call sites.
 *
 * The second: a release image with an npm build chain in it is a supply chain
 * and a rebuild step we would have to keep honest. These two files are vendored,
 * byte-identical to what upstream published, and served from the container.
 */
import { h, render } from 'preact';
import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

/* ---------- api ---------- */

let SESSION = sessionStorage.getItem('vg_session') || '';

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(SESSION ? { Authorization: `Bearer ${SESSION}` } : {}),
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
  if (response.status === 401) {
    SESSION = '';
    sessionStorage.removeItem('vg_session');
    throw { kind: 'unauthorized' };
  }
  const text = await response.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch (error) { body = { raw: text }; }
  if (!response.ok) throw { kind: 'http', status: response.status, body };
  return body;
}

const engineGet = (name, params) =>
  api(`/api/engine${name}?${new URLSearchParams(params || {})}`);
const enginePost = (name, payload) =>
  api(`/api/engine${name}`, { method: 'POST', body: JSON.stringify(payload) });

/* ---------- formatting ---------- */

const nf = new Intl.NumberFormat('ru-RU');
const num = (value) => (value === null || value === undefined ? '—' : nf.format(value));

function clock(ts) {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleTimeString('ru-RU', { hour12: false });
}

function stamp(ts) {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString('ru-RU', { hour12: false });
}

function duration(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${Math.round(seconds)} с`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ч ${minutes % 60} мин`;
  return `${Math.floor(hours / 24)} д ${hours % 24} ч`;
}

/* Split text into marked and unmarked runs. Offsets come from the engine and
 * index the ORIGINAL string — the detector's normalization is length-preserving
 * precisely so this stays true. */
function byOffsets(text, spans, cls) {
  const ordered = [...spans].sort((a, b) => a.start - b.start);
  const parts = [];
  let cursor = 0;
  for (const span of ordered) {
    if (span.start < cursor) continue;
    if (span.start > cursor) parts.push({ text: text.slice(cursor, span.start) });
    parts.push({ text: text.slice(span.start, span.end), cls });
    cursor = span.end;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor) });
  return parts;
}

/* Highlight known substrings. Used for the model-facing text, where the engine
 * reports which tokens it minted but not where they landed. */
function byNeedles(text, needles, cls) {
  const found = [];
  for (const needle of needles) {
    if (!needle) continue;
    let at = text.indexOf(needle);
    while (at !== -1) {
      found.push({ start: at, end: at + needle.length });
      at = text.indexOf(needle, at + needle.length);
    }
  }
  return byOffsets(text, found, cls);
}

const Marked = ({ parts }) => html`
  <div class="text">
    ${parts.map((part) => html`<span class=${part.cls || ''}>${part.text}</span>`)}
  </div>`;

const Logo = ({ size = 20 }) => html`
  <svg width=${size} height=${size} viewBox="0 0 32 32" fill="none" style="display:block">
    <rect x="3" y="11" width="18" height="18" rx="5" fill="#b3a0ea" />
    <rect x="11" y="3" width="18" height="18" rx="5" fill="#1c1c20" stroke="#b3a0ea" stroke-width="2.6" />
  </svg>`;

/* ---------- sign in ---------- */

function SignIn({ onDone }) {
  const fromUrl = new URLSearchParams(location.search).get('token') || '';
  const [secret, setSecret] = useState(fromUrl);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = useCallback(async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/signin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || 'не вышло');
      SESSION = body.session;
      sessionStorage.setItem('vg_session', body.session);
      // Drop the token from the address bar: a URL lands in browser history and
      // in whatever the operator pastes into a support ticket.
      history.replaceState(null, '', location.pathname);
      onDone(body.org_id);
    } catch (problem) {
      setError(String(problem.message || problem));
    } finally {
      setBusy(false);
    }
  }, [secret, onDone]);

  // Auto-submit when the operator followed the link from the log: the token is
  // already in the URL and asking them to press a button proves nothing.
  useEffect(() => { if (fromUrl) submit(new Event('submit')); }, []);

  return html`
    <div class="signin">
      <form onSubmit=${submit}>
        <div class="brand"><${Logo} size=${24} /><div class="brand-name">veilgate</div></div>
        <p>Введите токен из лога контейнера. Он печатается при каждом запуске.</p>
        <input type="password" value=${secret} autofocus
               placeholder="токен или пароль"
               onInput=${(event) => setSecret(event.target.value)} />
        <button class="btn primary" type="submit" disabled=${busy}>
          ${busy ? 'ПРОВЕРЯЮ…' : 'ВОЙТИ'}
        </button>
        ${error && html`<div class="err">${error}</div>`}
        <code>docker logs veilgate 2>&1 | grep "локальный интерфейс" -A2</code>
      </form>
    </div>`;
}

/* ---------- status ---------- */

function pillFor(status, engineDown) {
  if (engineDown) return { cls: 'bad', text: 'НЕ ОТВЕЧАЕТ' };
  const state = status?.license?.state;
  if (state === 'expired') return { cls: 'bad', text: 'МАСКИРОВАНИЕ ОСТАНОВЛЕНО' };
  if (state === 'stale') {
    return { cls: 'warn', text: `РАБОТАЕТ · GRACE ${duration(status.license.grace_left_s).toUpperCase()}` };
  }
  return { cls: 'ok', text: 'РАБОТАЕТ' };
}

function bannerFor(status, engineDown) {
  if (engineDown) {
    return { cls: 'bad', tag: 'КОНТЕЙНЕР НЕ ОТВЕЧАЕТ',
      text: 'Интерфейс не получает ответ от движка. Проверьте, что контейнер запущен, и пришлите нам вывод: docker logs veilgate --tail 200' };
  }
  const license = status?.license || {};
  if (license.state === 'expired') {
    return { cls: 'bad', tag: 'ЛИЦЕНЗИЯ ИСТЕКЛА',
      text: `Причина: ${license.code || 'аренда не продлевается'}. Новый трафик не маскируется и шлюз его не пропускает. Журнал и статистика остаются доступными — это ваши уже собранные данные.` };
  }
  if (license.state === 'stale') {
    return { cls: 'warn', tag: 'АРЕНДА НЕ ПРОДЛЕВАЕТСЯ',
      text: `Последняя успешная аренда ${duration(license.seconds_since_lease)} назад. Осталось ${duration(license.grace_left_s)} grace, после чего маскирование остановится и шлюз начнёт блокировать запросы. Оплатите подписку или проверьте доступ к лицензионному серверу.` };
  }
  if (status && !status.today.requests) {
    return { cls: 'info', tag: 'ТРАФИКА ЕЩЁ НЕ БЫЛО',
      text: 'Контейнер поднялся и лицензия активна. Нажмите «Проверить сейчас» — за несколько секунд увидите настоящее маскирование на заготовленном сообщении.' };
  }
  return null;
}

function CheckResult({ check }) {
  if (!check) return null;
  const tokens = check.spans.map((span) => span.token).filter(Boolean);
  return html`
    <div class="boxed">
      <div class="panes-head">
        <div class=${`label ${check.ok ? 'g' : 'a'}`}>
          ${check.ok ? 'ПРОВЕРКА ПРОЙДЕНА · ПД ЗАМАСКИРОВАНЫ И ВЕРНУЛИСЬ'
                     : 'ПРОВЕРКА НЕ ПРОЙДЕНА — ПРИШЛИТЕ НАМ ЭТОТ ЭКРАН'}
        </div>
        <div class="t">${check.elapsed_ms} мс</div>
      </div>
      <div class="panes">
        <div class="pane">
          <div class="label">БЫЛО</div>
          <${Marked} parts=${byOffsets(check.original, check.spans, 'mark-pii')} />
        </div>
        <div class="pane">
          <div class="label a">ЧТО УВИДЕЛА МОДЕЛЬ</div>
          <${Marked} parts=${byNeedles(check.masked, tokens, 'mark-fake')} />
        </div>
        <div class="pane">
          <div class="label g">ЧТО ВЕРНУЛОСЬ ИНСТРУМЕНТУ</div>
          <${Marked} parts=${byOffsets(check.restored, check.spans, 'mark-pii')} />
        </div>
      </div>
    </div>`;
}

function Status({ status, engineDown, org, goSandbox }) {
  const [check, setCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const runCheck = useCallback(async () => {
    setChecking(true);
    setError('');
    try {
      setCheck(await enginePost('/selfcheck', {}));
    } catch (problem) {
      setCheck(null);
      setError(problem.body?.error === 'license_expired' || problem.status === 503
        ? 'Маскирование сейчас остановлено: движок отвечает 503. Оплатите подписку или проверьте связь с лицензионным сервером.'
        : `Проверка не выполнилась: ${problem.status || ''} ${problem.body?.detail || problem.body?.error || ''}`);
    } finally {
      setChecking(false);
    }
  }, []);

  const copy = useCallback(() => {
    navigator.clipboard?.writeText('docker logs veilgate --tail 200');
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  }, []);

  const license = status?.license || {};
  const engine = status?.engine || {};
  const today = status?.today || {};
  const big = engineDown
    ? { title: 'не работает', color: 'var(--pink)', sub: 'движок не отвечает',
        note: 'Интерфейс живёт в том же контейнере, но не получает ответа от движка. Показанные ниже данные — последние известные.' }
    : license.state === 'expired'
    ? { title: 'не работает', color: 'var(--pink)', sub: 'лицензия истекла',
        note: 'Fail-closed: если маскировать нечем, запрос дальше не уходит. Данные не утекут даже в аварии.' }
    : license.state === 'stale'
    ? { title: 'работает', color: 'var(--amber)', sub: 'подписка истекает',
        note: `Маскирование идёт как обычно. Grace истекает через ${duration(license.grace_left_s)}.` }
    : { title: 'работает', color: 'var(--green)',
        sub: today.requests ? 'все процессы на связи' : 'трафика не было',
        note: today.requests
          ? `Движок обрабатывает трафик в ${engine.processes?.length || '—'} процесс(ов), аренда продлена, версия бандла актуальна.`
          : 'Движок загрузил модели и слушает порт. Первый настоящий запрос ещё не приходил.' };

  const breakdown = Object.entries(today.by_type || {})
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => `${type} ${num(count)}`)
    .join(' · ') || 'разбивки пока нет';

  return html`
    <div class="page">
      <div class="grid cols-fit">
        <div class="cell lit pad-lg">
          <div class="label">СОСТОЯНИЕ</div>
          <div class="big-row">
            <div class="big" style=${`color:${big.color}`}>${big.title}</div>
            <div class="big-sub">${big.sub}</div>
          </div>
          <div class="note">${big.note}</div>
          <div class="row mt">
            <button class="btn primary" onClick=${runCheck} disabled=${checking || engineDown}>
              ${checking ? 'ПРОВЕРЯЮ…' : 'ПРОВЕРИТЬ СЕЙЧАС'}
            </button>
            <button class="btn" onClick=${goSandbox}>ПЕСОЧНИЦА →</button>
          </div>
          <div class="hint">Проверка отправляет заготовленное сообщение через реальный /mask, затем /unmask. Ваши данные в ней не участвуют, и она не тарифицируется.</div>
          ${error && html`<div class="hint" style="color:var(--pink)">${error}</div>`}
        </div>
        <div class="cell">
          <div class="label mb">СЕГОДНЯ</div>
          <div class="stack">
            <div>
              <div class="stat">${engineDown ? '—' : num(today.requests)}</div>
              <div class="stat-cap">запросов обработано</div>
            </div>
            <div>
              <div class="stat green">${engineDown ? '—' : num(today.values)}</div>
              <div class="stat-cap">значений защищено</div>
            </div>
            <div class="breakdown">${engineDown ? 'сводка читается из движка — он не отвечает' : breakdown}</div>
          </div>
        </div>
      </div>

      <${CheckResult} check=${check} />

      <div class="grid cols-fit-sm attach">
        <div class="cell">
          <div class="label mb">ЛИЦЕНЗИЯ</div>
          ${[
            ['состояние', license.state || '—', license.state === 'expired' ? 'pink' : license.state === 'stale' ? 'amber' : 'green'],
            ['остаток grace', license.state === 'expired' ? 'исчерпан' : duration(license.grace_left_s), license.state === 'expired' ? 'pink' : ''],
            ['последняя аренда', license.seconds_since_lease === null ? '—' : `${duration(license.seconds_since_lease)} назад`, ''],
            ['версия бандла', engine.bundle_version || '—', ''],
            ['движок', engine.version || '—', ''],
          ].map(([key, value, tone]) => html`
            <div class="kv"><span class="k">${key}</span><span class=${`v ${tone}`}>${value}</span></div>`)}
        </div>
        <div class="cell">
          <div class="label mb">ПРОЦЕССЫ</div>
          ${(engine.processes || []).length
            ? engine.processes.map((process) => html`
                <div class="proc">
                  <span class="pid">pid ${process.pid}</span>
                  <span class="role">${process.role}</span>
                  <span class="up">${duration(process.uptime_s)}</span>
                </div>`)
            : html`<div class="foot-note">${engineDown ? 'нет ответа' : 'список процессов доступен только внутри контейнера Linux'}</div>`}
        </div>
        <div class="cell">
          <div class="label mb">ЕСЛИ ЧТО-ТО НЕ ТАК</div>
          <div class="foot-note">Первое, что попросит поддержка — нажать «Проверить сейчас» и прислать вывод логов контейнера.</div>
          <div class="copybar">
            <code>docker logs veilgate --tail 200</code>
            <button onClick=${copy}>${copied ? 'СКОПИРОВАНО' : 'КОПИРОВАТЬ'}</button>
          </div>
        </div>
      </div>
    </div>`;
}

/* ---------- sandbox ---------- */

const PRESETS = [
  ['ФИО И ТЕЛЕФОН', 'Здравствуйте! Меня зовут Иванов Пётр Сергеевич, заказ №A-4471. Перезвоните на +7 916 214-88-03, доставку жду по адресу Москва, Ленинский пр-т 42, кв. 118.'],
  ['JSON ЗАКАЗА', '{"order": "A-4471", "customer": "Иванова Мария Львовна", "phone": "+79162148803", "email": "m.ivanova@acme.ru", "total": 12400}'],
  ['АДРЕС', 'Курьер не нашёл вход. Адрес: г. Казань, ул. Профсоюзная, д. 17, под. 3, кв. 84, домофон 84К.'],
  ['ДОКУМЕНТЫ', 'Для оформления: паспорт 4517 № 812345, СНИЛС 112-233-445 95, ИНН 770512345678. Договор 2024/117.'],
  ['СМЕШАННЫЙ СЛУЧАЙ', 'Заказ 2024/117 на 12 400 ₽, вес 4517 г, трек 812345. Получатель Соколова Анна Игоревна, +7 916 214-88-03.'],
];

function Sandbox({ org }) {
  const [text, setText] = useState(PRESETS[0][1]);
  const [preset, setPreset] = useState(0);
  const [spans, setSpans] = useState(null);
  const [full, setFull] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const findSpans = useCallback(async () => {
    setBusy('spans'); setError(''); setFull(null);
    try {
      const body = await enginePost('/spans', { org_id: org, texts: [text] });
      setSpans(body.results[0] || []);
    } catch (problem) {
      setError(problem.status === 503
        ? 'Лицензия истекла: разбор недоступен, движок отвечает 503.'
        : `Не вышло: ${problem.status || ''} ${problem.body?.error || ''}`);
    } finally { setBusy(''); }
  }, [text, org]);

  const runFull = useCallback(async () => {
    setBusy('full'); setError('');
    const started = performance.now();
    try {
      const masked = await enginePost('/mask', {
        org_id: org, agent_id: 'песочница',
        messages: [{ role: 'user', content: text }],
      });
      const maskedText = masked.messages[0].content;
      const spansBody = await enginePost('/spans', { org_id: org, texts: [text] });
      const found = spansBody.results[0] || [];
      setSpans(found);
      setFull({
        masked: maskedText,
        tokens: found.map((span) => span.token).filter(Boolean),
        ms: Math.round(performance.now() - started),
      });
    } catch (problem) {
      setError(problem.status === 503
        ? 'Маскирование остановлено: /mask отдаёт 503. Полный прогон недоступен, разбор «что найдено» — остаётся.'
        : `Не вышло: ${problem.status || ''} ${problem.body?.error || ''}`);
    } finally { setBusy(''); }
  }, [text, org]);

  return html`
    <div class="page">
      <div class="pagehead">
        <div>
          <h1 class="title">Песочница</h1>
          <div class="subtitle">Здесь можно вставлять настоящий текст: данные не покидают контур.</div>
        </div>
        <div class="row">
          ${PRESETS.map(([label, body], index) => html`
            <button class=${`btn sm ${preset === index ? 'on' : ''}`}
                    onClick=${() => { setPreset(index); setText(body); setSpans(null); setFull(null); }}>
              ${label}
            </button>`)}
        </div>
      </div>

      <div class="grid cols-fit-md">
        <div class="cell sandbox-in" style="padding:0">
          <textarea spellcheck="false" value=${text}
                    onInput=${(event) => { setText(event.target.value); setSpans(null); setFull(null); }}></textarea>
          <div class="row">
            <button class="btn md" onClick=${findSpans} disabled=${busy !== ''}>
              ${busy === 'spans' ? 'СМОТРЮ…' : 'ЧТО НАЙДЕНО'}
            </button>
            <button class="btn md primary" onClick=${runFull} disabled=${busy !== ''}>
              ${busy === 'full' ? 'ПРОГОНЯЮ…' : 'ПРОГНАТЬ ПОЛНОСТЬЮ'}
            </button>
            <p>Первая кнопка только смотрит (<span class="mono">/spans</span>) и токенов не создаёт. Вторая создаёт токены в волте.</p>
          </div>
        </div>
        <div class="cell">
          <div class="label mb">НАЙДЕНО · ${spans === null ? 'нажмите «что найдено»' : `${spans.length}`}</div>
          ${(spans || []).map((span) => html`
            <div class="span-row">
              <div class="top">
                <span class="type">${span.type}</span>
                <span class="pos">${span.start}–${span.end}</span>
              </div>
              <div class="val">${text.slice(span.start, span.end)}</div>
              <div class="fake">→ ${span.token || 'токен ещё не создан — нажмите «прогнать полностью»'}</div>
            </div>`)}
          ${spans !== null && spans.length === 0 && html`<div class="foot-note">Персональных данных не найдено.</div>`}
          <div class="hint">
            ${error ? html`<span style="color:var(--pink)">${error}</span>`
              : spans !== null ? 'Read-only: /spans ничего не меняет в волте и токенов не создаёт.'
              : 'Разбор идёт локально. Ни текст, ни результат наружу не уходят.'}
          </div>
        </div>
      </div>

      ${full && html`
        <div class="boxed">
          <div class="panes-head">
            <div class="label a">ПОЛНЫЙ ПРОГОН · СОЗДАНО ТОКЕНОВ: ${full.tokens.length}</div>
            <div class="t">${full.ms} мс</div>
          </div>
          <div class="panes">
            <div class="pane">
              <div class="label">БЫЛО</div>
              <${Marked} parts=${byOffsets(text, spans || [], 'mark-pii')} />
            </div>
            <div class="pane">
              <div class="label a">ЧТО УВИДЕЛА БЫ МОДЕЛЬ</div>
              <${Marked} parts=${byNeedles(full.masked, full.tokens, 'mark-fake')} />
            </div>
          </div>
        </div>`}
    </div>`;
}

/* ---------- log ---------- */

const PERIODS = [['сегодня', 'today'], ['7 дней', '7d'], ['14 дней', '14d']];
const PAGE_SIZE = 25;

function Log({ org, onReveal }) {
  const [period, setPeriod] = useState('14d');
  const [agent, setAgent] = useState('');
  const [type, setType] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    engineGet('/events', {
      org_id: org, period, agent_id: agent, type, q: query,
      limit: PAGE_SIZE, offset: page * PAGE_SIZE,
    })
      .then((body) => { if (live) { setData(body); setError(''); } })
      .catch((problem) => { if (live) setError(problem.body?.error || 'движок не отвечает'); });
    return () => { live = false; };
  }, [org, period, agent, type, query, page]);

  useEffect(() => { setPage(0); }, [period, agent, type, query]);

  const events = data?.events || [];
  const total = data?.total || 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return html`
    <div class="page">
      <div class="pagehead">
        <div>
          <h1 class="title">Журнал</h1>
          <div class="subtitle">
            ${error ? 'Журнал читается через API движка — он не отвечает. Уже собранные данные никуда не пропали.'
                    : total ? `${num(total)} событий за период · показаны последние`
                    : 'Событий пока нет — журнал наполнится с первым трафиком'}
          </div>
        </div>
        <div class="row">
          ${PERIODS.map(([label, value]) => html`
            <button class=${`btn sm ${period === value ? 'on' : ''}`} onClick=${() => setPeriod(value)}>${label}</button>`)}
          <select class="field" value=${agent} onChange=${(event) => setAgent(event.target.value)}>
            <option value="">все агенты</option>
            ${(data?.agents || []).map((name) => html`<option value=${name}>${name}</option>`)}
          </select>
          <select class="field" value=${type} onChange=${(event) => setType(event.target.value)}>
            <option value="">все типы</option>
            ${(data?.types || []).map((name) => html`<option value=${name}>${name}</option>`)}
          </select>
          <input class="field" placeholder="поиск по токену" value=${query}
                 onInput=${(event) => setQuery(event.target.value)} />
        </div>
      </div>

      <div class="table-wrap">
        <div class="trow head">
          <div>ВРЕМЯ</div><div>АГЕНТ</div><div>ТИП</div><div>ТОКЕН</div><div>ОРИГИНАЛ</div><div></div>
        </div>
        ${events.map((event) => html`
          <div class="trow">
            <div class="ts">${clock(event.ts)}</div>
            <div class="agent">${event.agent_id || '—'}</div>
            <div class="type">${event.type}</div>
            <div class="token" title=${event.token}>${event.token}</div>
            <div class="prev">${event.preview}</div>
            <button onClick=${() => onReveal(event)}>РАСКРЫТЬ</button>
          </div>`)}
        ${!events.length && html`<div class="empty">${error || 'Ничего не найдено по этим фильтрам.'}</div>`}
        <div class="pager">
          <div>${total ? `стр. ${page + 1} из ${num(pages)} · по ${PAGE_SIZE} строк` : 'нет строк'}</div>
          <div class="row">
            <button onClick=${() => setPage((value) => Math.max(0, value - 1))} disabled=${page === 0}>← НАЗАД</button>
            <button onClick=${() => setPage((value) => value + 1)} disabled=${page + 1 >= pages}>ДАЛЬШЕ →</button>
          </div>
        </div>
      </div>

      <div class="foot-notes">
        <div class="foot-note">
          <b>Почему событий меньше, чем сообщений.</b> Одно и то же значение, пришедшее повторно в растущем транскрипте, — это одна защищённая сущность, а не N. Повторные попадания в журнал не пишутся: для счётчиков это правильно, а здесь выглядит как пропуски.
        </div>
        <div class="foot-note">
          <b>Раскрытие пишется в журнал доступа.</b> Фиксируется сессия, токен и время. Само значение не сохраняется — иначе журнал стал бы второй копией персональных данных.
        </div>
      </div>
    </div>`;
}

/* ---------- reveal modal ---------- */

function RevealModal({ event, org, onClose }) {
  const [value, setValue] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const confirm = useCallback(async () => {
    setBusy(true);
    try {
      // No `actor` here on purpose. The engine requires one, and the UI server
      // stamps it from the session it validated — a field the page could set
      // would let whoever is at the keyboard write someone else's name into the
      // access log, which is the one thing that log exists to prevent.
      const body = await enginePost('/reveal', { org_id: org, token: event.token });
      setValue(body.value === null ? '— значение не найдено в волте' : body.value);
    } catch (problem) {
      setError(`Не вышло: ${problem.status || ''} ${problem.body?.error || ''}`);
    } finally { setBusy(false); }
  }, [event, org]);

  const revealed = value !== null;
  return html`
    <div class="scrim" onClick=${(e) => e.target === e.currentTarget && onClose()}>
      <div class="modal">
        <div class="modal-head">
          <div class=${`tag ${revealed ? 'green' : 'amber'}`}>
            ${revealed ? 'РАСКРЫТО · ЗАПИСАНО В ЖУРНАЛ ДОСТУПА' : 'ПОДТВЕРДИТЕ РАСКРЫТИЕ'}
          </div>
          <h2>${revealed ? `${event.type} · ${event.token}` : 'Показать настоящее значение?'}</h2>
          <p>
            ${revealed
              ? 'Значение не остаётся на экране после закрытия и не сохраняется в журнале доступа — там только кто, какой токен и когда.'
              : `Токен ${event.token}, тип ${event.type}. Это ваши данные, вы оператор. Раскрытие будет записано в журнал доступа: сессия интерфейса, токен, время. Само значение в журнал не попадёт.`}
          </p>
        </div>
        ${revealed && html`
          <div class="modal-val">
            <div class="label">НАСТОЯЩЕЕ ЗНАЧЕНИЕ</div>
            <div class="v">${value}</div>
            <div class="foot">${stamp(event.ts)} · автоскрытие при закрытии окна</div>
          </div>`}
        ${error && html`<div class="modal-val"><div class="msg" style="color:var(--pink)">${error}</div></div>`}
        <div class="modal-foot">
          <button class="btn md" onClick=${onClose}>ЗАКРЫТЬ</button>
          ${!revealed && html`
            <button class="btn md primary" onClick=${confirm} disabled=${busy}>
              ${busy ? 'РАСКРЫВАЮ…' : 'РАСКРЫТЬ И ЗАПИСАТЬ'}
            </button>`}
        </div>
      </div>
    </div>`;
}

/* ---------- stats ---------- */

function Stats({ org }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(14);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    engineGet('/stats', { org_id: org, days })
      .then((body) => { if (live) { setData(body); setError(''); } })
      .catch(() => { if (live) setError('движок не отвечает'); });
    return () => { live = false; };
  }, [org, days]);

  const series = data?.days || [];
  const peak = Math.max(1, ...series.map((day) => day.requests));
  const types = Object.entries(data?.by_type || {}).sort((a, b) => b[1] - a[1]);
  const topType = Math.max(1, ...types.map(([, count]) => count));

  return html`
    <div class="page">
      <div class="pagehead">
        <div>
          <h1 class="title">Статистика</h1>
          <div class="subtitle">Период: последние ${days} дней · считается локально</div>
        </div>
        <div class="row">
          ${[14, 30, 90].map((value) => html`
            <button class=${`btn sm ${days === value ? 'on' : ''}`} onClick=${() => setDays(value)}>${value} ДНЕЙ</button>`)}
          <!-- href="#", never the real URL with the session in it: a URL lands in
               history, shows in the status bar on hover, and travels into whatever
               the operator pastes into a ticket. The fetch below sends the session
               as a header instead. -->
          <a class="btn sm" href="#"
             onClick=${async (event) => {
               // The CSV is behind the session header, which a plain <a> cannot
               // send — fetch it, then hand the browser a blob to save.
               event.preventDefault();
               const response = await fetch(`/api/engine/stats.csv?org_id=${encodeURIComponent(org)}&days=${days}`,
                 { headers: { Authorization: `Bearer ${SESSION}` } });
               const blob = await response.blob();
               const url = URL.createObjectURL(blob);
               const link = document.createElement('a');
               link.href = url;
               link.download = `veilgate-${org}-${days}d.csv`;
               link.click();
               URL.revokeObjectURL(url);
             }}>ВЫГРУЗИТЬ CSV</a>
        </div>
      </div>

      ${error && html`<div class="foot-note" style="color:var(--pink);margin-bottom:12px">${error}</div>`}

      <div class="cell" style="border:1px solid var(--line-2);padding:22px 24px 26px">
        <div class="label mb">ЗАПРОСЫ ПО ДНЯМ</div>
        <div class="bars">
          ${series.map((day, index) => html`
            <div class="col" title=${`${day.day}: ${num(day.requests)} запросов, ${num(day.values)} значений`}>
              <div class=${`bar ${index === series.length - 1 ? 'last' : ''}`}
                   style=${`height:${Math.round((day.requests / peak) * 100)}%`}></div>
              <div class="cap">${day.day.slice(8)}</div>
            </div>`)}
        </div>
      </div>

      <div class="grid cols-fit-md attach">
        <div class="cell" style="padding:22px 24px">
          <div class="label mb">ПО ТИПАМ СУЩНОСТЕЙ</div>
          ${types.map(([name, count]) => html`
            <div class="tbar">
              <div class="n">${name}</div>
              <div class="track"><div class="fill" style=${`width:${Math.round((count / topType) * 100)}%`}></div></div>
              <div class="c">${num(count)}</div>
            </div>`)}
          ${!types.length && html`<div class="foot-note">Пока пусто.</div>`}
        </div>
        <div class="cell">
          <div class="label mb">ПО АГЕНТАМ</div>
          ${(data?.by_agent || []).map((row) => html`
            <div class="kv"><span class="k mono">${row.agent_id}</span><span class="v">${num(row.requests)}</span></div>`)}
          ${!(data?.by_agent || []).length && html`<div class="foot-note">Пока пусто.</div>`}
          <div class="hint">Выгрузка CSV — печатная форма для внутренней проверки: период, число обращений и сколько значений защищено. Токенов и значений в ней нет.</div>
        </div>
      </div>
    </div>`;
}

/* ---------- subscription ---------- */

function Subscription({ org }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    engineGet('/subscription', { org_id: org })
      .then((body) => { if (live) { setData(body); setError(''); } })
      .catch(() => { if (live) setError('движок не отвечает'); });
    return () => { live = false; };
  }, [org]);

  const report = data?.last_report || {};
  const tone = data?.state === 'expired' ? 'pink' : data?.state === 'stale' ? 'amber' : 'green';

  return html`
    <div class="page">
      <h1 class="title">Подписка</h1>
      <div class="subtitle" style="margin-bottom:16px">Локальное зеркало состояния лицензии — чтобы ответ на «почему встало» был здесь.</div>
      ${error && html`<div class="foot-note" style="color:var(--pink);margin-bottom:12px">${error}</div>`}
      <div class="grid cols-fit-md">
        <div class="cell" style="padding:24px">
          ${[
            ['состояние лицензии', data?.state || '—', tone],
            ['код', data?.code || '—', data?.code ? 'pink' : ''],
            ['последняя аренда', data?.seconds_since_lease === null || data?.seconds_since_lease === undefined ? '—' : `${duration(data.seconds_since_lease)} назад`, ''],
            ['остаток grace', data?.state === 'expired' ? 'исчерпан' : duration(data?.grace_left_s), data?.state === 'expired' ? 'pink' : ''],
            ['версия бандла', data?.bundle_version || '—', ''],
            ['запросов за всё время', num(data?.requests_total), ''],
          ].map(([key, value, klass]) => html`
            <div class="kv lg"><span class="k">${key}</span><span class=${`v ${klass}`}>${value}</span></div>`)}
          <div class="errbox">
            <div class="label">ПОСЛЕДНЯЯ ОШИБКА ПРОДЛЕНИЯ, ДОСЛОВНО</div>
            <div class=${`msg ${data?.last_error ? 'pink' : ''}`}>${data?.last_error || 'ошибок не было'}</div>
          </div>
          ${(data?.errors || []).length > 1 && html`
            <div style="margin-top:18px">
              <div class="label mb">РАНЕЕ</div>
              ${data.errors.slice(1).map((row) => html`
                <div class="lerow"><span class="ts">${stamp(row.ts)}</span><span class="msg">${row.message}</span></div>`)}
            </div>`}
        </div>
        <div class="cell lit" style="padding:24px">
          <div class="label mb" style="color:var(--green)">ЧТО УХОДИТ НАРУЖУ · ПОСЛЕДНИЙ ОТЧЁТ</div>
          <pre class="report">${report.body ? JSON.stringify(report.body, null, 1) : 'Отчёт ещё не отправлялся: счётчики уезжают вместе с первым продлением аренды, не при выдаче.'}</pre>
          <div class="foot-note" style="margin-top:16px">Это реально отправленное тело, а не пример из документации. Ни текстов, ни токенов, ни значений в нём нет и быть не может.</div>
          <div class="mono" style="font-size:11px;color:var(--dim-3);margin-top:14px;line-height:1.8">
            отправлено: ${stamp(report.sent_at)}<br />адрес: ${report.url || '—'}
          </div>
        </div>
      </div>
    </div>`;
}

/* ---------- diagnostics ---------- */

function Diagnostics({ org }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    engineGet('/diagnostics', { org_id: org })
      .then((body) => { if (live) { setData(body); setError(''); } })
      .catch(() => { if (live) setError('движок не отвечает'); });
    return () => { live = false; };
  }, [org]);

  const stages = Object.entries(data?.profile || {})
    .map(([name, row]) => ({ name, ms: row.total_ms ?? row.ms ?? 0, calls: row.calls ?? 0 }))
    .sort((a, b) => b.ms - a.ms);
  const slowest = Math.max(1, ...stages.map((row) => row.ms));

  return html`
    <div class="page">
      <h1 class="title">Диагностика</h1>
      <div class="subtitle" style="margin-bottom:16px">Только чтение. Настройки движка меняются переменными окружения контейнера.</div>
      ${error && html`<div class="foot-note" style="color:var(--pink);margin-bottom:12px">${error}</div>`}
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(320px,1fr))">
        <div class="cell">
          <div class="label mb">ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ</div>
          ${Object.entries(data?.env || {}).map(([key, value]) => html`
            <div class="envrow"><span class="k">${key}</span><span class="v">${value}</span></div>`)}
          <div class="hint">Показаны только настройки. Ключ лицензии и другие секреты сюда не выводятся никогда.</div>
        </div>
        <div class="cell">
          <div class="label mb">ПРОФИЛЬ ПО СТАДИЯМ</div>
          ${stages.length ? stages.map((row) => html`
            <div class="sbar">
              <span class="n mono">${row.name}</span>
              <div class="track"><div class="fill" style=${`width:${Math.round((row.ms / slowest) * 100)}%`}></div></div>
              <span class="c mono">${row.ms.toFixed ? row.ms.toFixed(1) : row.ms}</span>
            </div>`)
            : html`<div class="foot-note">Профилирование выключено. Включается <span class="mono">VEILGATE_PROFILE=1</span>.</div>`}

          <div class="label mb" style="margin-top:22px">ПАМЯТЬ ПО ПРОЦЕССАМ</div>
          ${(data?.processes || []).map((process) => html`
            <div class="kv"><span class="k mono">pid ${process.pid} · ${process.role}</span><span class="v">${process.rss_mb} МБ</span></div>`)}
          ${!(data?.processes || []).length && html`<div class="foot-note">Доступно только внутри контейнера Linux.</div>`}
        </div>
      </div>
      <div class="boxed" style="padding:22px">
        <div class="label mb" style="color:var(--amber)">ПОСЛЕДНИЕ ОШИБКИ АРЕНДЫ</div>
        ${(data?.lease_errors || []).map((row) => html`
          <div class="lerow"><span class="ts">${stamp(row.ts)}</span><span class="msg">${row.message}</span></div>`)}
        ${!(data?.lease_errors || []).length && html`<div class="foot-note">Ошибок продления не было.</div>`}
      </div>
    </div>`;
}

/* ---------- shell ---------- */

const TABS = [
  ['СТАТУС', 'status'], ['ПЕСОЧНИЦА', 'sandbox'], ['ЖУРНАЛ', 'log'],
  ['СТАТИСТИКА', 'stats'], ['ПОДПИСКА', 'sub'], ['ДИАГНОСТИКА', 'diag'],
];

function App() {
  const [session, setSession] = useState(SESSION);
  const [org, setOrg] = useState('default');
  const [orgs, setOrgs] = useState([]);
  const [tab, setTab] = useState('status');
  const [status, setStatus] = useState(null);
  const [engineDown, setEngineDown] = useState(false);
  const [reveal, setReveal] = useState(null);
  const [age, setAge] = useState(0);
  const timer = useRef(null);

  useEffect(() => {
    if (!session) return;
    api('/api/whoami').then((body) => setOrg(body.org_id)).catch(() => {});
    engineGet('/orgs').then((body) => setOrgs(body.orgs || [])).catch(() => {});
  }, [session]);

  // Poll the status. Paused while the tab is hidden — a background tab hammering
  // the engine every three seconds is load the customer pays for and never sees.
  useEffect(() => {
    if (!session) return undefined;
    let live = true;
    const tick = async () => {
      if (document.hidden) return;
      try {
        const body = await engineGet('/status', { org_id: org });
        if (!live) return;
        setStatus(body);
        setEngineDown(false);
        setAge(0);
      } catch (problem) {
        if (!live) return;
        if (problem.kind === 'unauthorized') { setSession(''); return; }
        setEngineDown(true);
      }
    };
    tick();
    timer.current = setInterval(() => { setAge((value) => value + 3); tick(); }, 3000);
    return () => { live = false; clearInterval(timer.current); };
  }, [session, org]);

  if (!session) {
    return html`<${SignIn} onDone=${(id) => { setSession(SESSION); setOrg(id); }} />`;
  }

  const pill = pillFor(status, engineDown);
  const banner = bannerFor(status, engineDown);
  const engine = status?.engine || {};

  return html`
    <div class="shell">
      <header class="head">
        <div class="head-left">
          <div class="brand">
            <${Logo} />
            <div class="brand-name">veilgate</div>
            <div class="chip">ЛОКАЛЬНЫЙ ИНТЕРФЕЙС</div>
          </div>
          <div class="meta">
            <span>org ${orgs.length > 1
              ? html`<select class="field" style="width:auto;padding:2px 6px" value=${org}
                             onChange=${(event) => setOrg(event.target.value)}>
                       ${orgs.map((name) => html`<option value=${name}>${name}</option>`)}
                     </select>`
              : html`<b>${org}</b>`}</span>
            <span>движок <b>${engine.version || '—'}</b></span>
            <span>бандл <b>${engine.bundle_version || '—'}</b></span>
          </div>
        </div>
        <div class="row">
          <div class=${`pill ${pill.cls}`}><i></i><span>${pill.text}</span></div>
          <div class="mono" style="font-size:10.5px;color:var(--dim-3)">
            ${engineDown ? 'опрос не отвечает' : `обновлено ${age} с назад`}
          </div>
        </div>
      </header>

      <div class="body">
        <aside class="rail">
          <nav>
            ${TABS.map(([label, id]) => html`
              <button class=${tab === id ? 'on' : ''} onClick=${() => setTab(id)}>
                <span>${label}</span>
                <em>${id === 'log' && status?.today?.values ? num(status.today.values) : ''}</em>
              </button>`)}
          </nav>
          <div class="rail-foot">
            <div class="label">НИЧЕГО НЕ УХОДИТ<br />ЗА ПРЕДЕЛЫ КОНТУРА</div>
            <p>Порт 8081, вход по токену из лога контейнера.</p>
          </div>
        </aside>

        <main>
          ${banner && html`
            <div class=${`banner ${banner.cls}`}>
              <div class="tag">${banner.tag}</div>
              <p>${banner.text}</p>
            </div>`}
          ${tab === 'status' && html`<${Status} status=${status} engineDown=${engineDown} org=${org} goSandbox=${() => setTab('sandbox')} />`}
          ${tab === 'sandbox' && html`<${Sandbox} org=${org} />`}
          ${tab === 'log' && html`<${Log} org=${org} onReveal=${setReveal} />`}
          ${tab === 'stats' && html`<${Stats} org=${org} />`}
          ${tab === 'sub' && html`<${Subscription} org=${org} />`}
          ${tab === 'diag' && html`<${Diagnostics} org=${org} />`}
        </main>
      </div>

      ${reveal && html`<${RevealModal} event=${reveal} org=${org} onClose=${() => setReveal(null)} />`}
    </div>`;
}

render(html`<${App} />`, document.getElementById('root'));
