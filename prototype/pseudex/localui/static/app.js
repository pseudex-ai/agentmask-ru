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

let SESSION = sessionStorage.getItem('ps_session') || '';

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
    sessionStorage.removeItem('ps_session');
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
  const fromUrl = new URLSearchParams(location.search).get('secret')
    // `token` is still accepted: a link an operator bookmarked before
    // this rename must keep working, and both name the same secret.
    // `new` ЗДЕСЬ ОБЯЗАТЕЛЕН, и его не было: `URLSearchParams(...)` без него
    // бросает TypeError, а ветка вычисляется всегда, когда в адресе НЕТ
    // `?secret`, — то есть при обычном заходе на корень. Компонент падал, и
    // человек видел пустую страницу вместо формы входа. Проверка рендера этого
    // не видела: она всегда приходит со ссылкой с секретом.
    || new URLSearchParams(location.search).get('token') || '';
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
      sessionStorage.setItem('ps_session', body.session);
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
        <div class="brand"><${Logo} size=${24} /><div class="brand-name">pseudex</div></div>
        <p>Введите токен из лога контейнера. Он печатается при каждом запуске.</p>
        <input type="password" value=${secret} autofocus
               placeholder="токен или пароль"
               onInput=${(event) => setSecret(event.target.value)} />
        <button class="btn primary" type="submit" disabled=${busy}>
          ${busy ? 'ПРОВЕРЯЮ…' : 'ВОЙТИ'}
        </button>
        ${error && html`<div class="err">${error}</div>`}
        <code>docker logs pseudex 2>&1 | grep "локальный интерфейс" -A2</code>
      </form>
    </div>`;
}

/* ---------- status ---------- */

// The volume's own verdict, and it has FOUR values rather than two. Each store
// migrates and rekeys on its own, so a volume can be half encrypted — a boolean
// could not say that, and the engine now reports the state of every file.
const DISK = {
  encrypted: ['зашифровано (AES-256)', 'green'],
  plaintext: ['ОТКРЫТЫЙ ТЕКСТ', 'pink'],
  mixed: ['ЧАСТЬ ФАЙЛОВ ОТКРЫТА', 'pink'],
  empty: ['пусто — файлов ещё нет', ''],
};
const FILE_STATE = {
  encrypted: ['зашифрован', 'green'],
  plaintext: ['ОТКРЫТЫЙ ТЕКСТ', 'pink'],
  missing: ['нет файла', ''],
  empty: ['пустой', ''],
};

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
      text: 'Интерфейс не получает ответ от движка. Проверьте, что контейнер запущен, и пришлите нам вывод: docker logs pseudex --tail 200' };
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

function Status({ status, engineDown, org, goSandbox, onBlocked }) {
  const [check, setCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const runCheck = useCallback(async () => {
    // Refused before it is attempted when we already know it cannot work. The
    // engine would answer 503 anyway, but sending a request in order to be told
    // something the screen already displays is the kind of thing that makes an
    // operator doubt what the screen says.
    if (engineDown || status?.license?.state === 'expired') {
      onBlocked(engineDown ? 'down' : 'expired');
      return;
    }
    setChecking(true);
    setError('');
    try {
      setCheck(await enginePost('/selfcheck', {}));
    } catch (problem) {
      setCheck(null);
      if (problem.status === 503) { onBlocked('expired'); return; }
      setError(`Проверка не выполнилась: ${problem.status || ''} ${problem.body?.detail || problem.body?.error || ''}`);
    } finally {
      setChecking(false);
    }
  }, [engineDown, status, onBlocked]);

  const copy = useCallback(() => {
    navigator.clipboard?.writeText('docker logs pseudex --tail 200');
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  }, []);

  const license = status?.license || {};
  const engine = status?.engine || {};
  const memory = engine.memory;
  const today = status?.today || {};
  const vault = status?.vault || {};
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
          <div class="label mb">ХРАНИЛИЩЕ</div>
          ${/* «Движок не отвечает» is NOT «том открыт». This block reads the
                engine's own answer, so with no answer the honest value is a
                dash — the first version painted "ОТКРЫТЫЙ ТЕКСТ" in pink
                whenever the engine was merely down, which is the same false
                alarm the rekey role used to print, on the one screen an
                operator opens when something is already wrong. */ ''}
          ${[
            ['на диске', engineDown ? '—' : (DISK[vault.on_disk] || ['—', ''])[0],
             engineDown ? '' : (DISK[vault.on_disk] || ['', ''])[1]],
            // The value was already gated on engineDown and the TONE was not, so
            // a dead engine rendered a dash painted amber — an alarm about a key
            // nobody had read.
            ['ключ', engineDown ? '—' : (vault.key_source || '—'),
             engineDown ? '' : (vault.key_beside_data ? 'amber' : '')],
          ].map(([key, value, tone]) => html`
            <div class="kv"><span class="k">${key}</span><span class=${`v ${tone}`}>${value}</span></div>`)}
          ${/* Per file only when the volume disagrees with itself. On a volume
                that is wholly one thing the three rows say nothing the line
                above did not, and this screen is read in a hurry. */ ''}
          ${!engineDown && vault.on_disk === 'mixed' && (vault.files || []).map((file) => html`
            <div class="kv"><span class="k">${file.name}</span><span class=${`v ${(FILE_STATE[file.state] || ['', ''])[1]}`}>${(FILE_STATE[file.state] || [file.state, ''])[0]}</span></div>`)}
          ${engineDown && html`
            <div class="foot-note">Состояние шифрования читается из движка — он не отвечает.</div>`}
          ${!engineDown && vault.key_beside_data && html`
            <div class="foot-note">Ключ лежит в том же томе, что и данные: это защищает скопированный файл базы, но не украденный том или его резервную копию — они несут ключ с собой. PSEUDEX_VAULT_KEY_CMD переносит ключ в ваш менеджер секретов.</div>`}
          ${!engineDown && vault.on_disk === 'mixed' && html`
            <div class="foot-note">Часть хранилищ ещё лежит открытым текстом: файлы переводятся по одному, и обрыв оставляет том наполовину. Перезапуск движка с тем же ключом дошифрует остальные.</div>`}
          ${!engineDown && vault.on_disk === 'plaintext' && html`
            <div class="foot-note">Настоящие значения лежат в томе как есть. Кто получил том, снимок диска или бэкап — прочитал всё.</div>`}
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
          ${memory && memory.limit_mb ? html`
            <div class="foot-note">Память: ${memory.used_mb} из ${memory.limit_mb} МБ, крупнейший процесс ${memory.largest_process_mb} МБ при бюджете воркера ${memory.worker_mb_budget} МБ.</div>
            ${memory.largest_process_mb > memory.worker_mb_budget && html`
              <div class="foot-note">Воркер вырос выше бюджета, на котором посчитан запуск. Это и есть тот контейнер, который однажды остановит OOM-killer: поднимите лимит памяти или уменьшите PSEUDEX_WORKERS.</div>`}`
            : !engineDown && html`
            <div class="foot-note">Лимита памяти не видно — контейнер запущен без него, и предполётная проверка ничего не проверяла.</div>`}
        </div>
        <div class="cell">
          <div class="label mb">ЕСЛИ ЧТО-ТО НЕ ТАК</div>
          <div class="foot-note">Первое, что попросит поддержка — нажать «Проверить сейчас» и прислать вывод логов контейнера.</div>
          <div class="copybar">
            <code>docker logs pseudex --tail 200</code>
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
  // Deliberately mixes a real credential with a git SHA and a UUID: the point of
  // the preset is to show that the key is masked and the hashes are NOT.
  ['КЛЮЧИ И ТОКЕНЫ', 'Деплой упал. Ключ OPENAI_API_KEY=sk-proj-Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7Xy7, коммит a94a8fe5ccb19ba61c4c0873d391e987982fbbd3, задача 550e8400-e29b-41d4-a716-446655440000.'],
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
            <p>Первая кнопка только смотрит (<span class="mono">/spans</span>) и токенов не создаёт. Вторая создаёт токены в волте <b>и считается обычным запросом по тарифу</b> — в отличие от проверки на экране «Статус».</p>
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
          ${(data?.agents || []).length
            ? html`<select class="field" value=${agent} onChange=${(event) => setAgent(event.target.value)}>
                <option value="">все агенты</option>
                ${data.agents.map((name) => html`<option value=${name}>${name}</option>`)}
              </select>`
            /* A filter over an empty list is worse than no filter: it looks like
             * it works, returns nothing, and reads as «такого агента не было»
             * rather than «агенты не размечены». The caller labels them with
             * X-Pseudex-Agent; until it does, say so instead of offering it. */
            : html`<span class="hint" style="align-self:center">
                агенты не размечены — назовите их заголовком
                <code>X-Pseudex-Agent</code> в запросе к шлюзу
              </span>`}
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

function BlockedModal({ reason, onClose }) {
  return html`
    <div class="scrim" onClick=${(e) => e.target === e.currentTarget && onClose()}>
      <div class="modal">
        <div class="modal-head">
          <div class="tag pink">ПРОВЕРКА НЕВОЗМОЖНА</div>
          <h2>Маскирование сейчас остановлено</h2>
          <p>
            ${reason === 'down'
              ? 'Движок не отвечает. Запустите контейнер и повторите: docker start pseudex'
              : 'Лицензия истекла, поэтому /mask возвращает 503. Оплатите подписку в кабинете — аренда продлится в течение минуты.'}
          </p>
        </div>
        <div class="modal-foot">
          <button class="btn md" onClick=${onClose}>ЗАКРЫТЬ</button>
        </div>
      </div>
    </div>`;
}

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

/* The period report: what the operator hands to their own auditor or security
 * officer. Counts only — organisation, period, how many requests, how many
 * values of each type — and by construction it CANNOT contain a token, a
 * preview or a value, which is what makes it safe to print and file.
 *
 * Rendered into the page and printed from there rather than downloaded: a PDF
 * generator would need a native toolchain in the release image for one screen,
 * and the browser already has one. */
function PeriodReport({ org, data, days, onClose }) {
  useEffect(() => {
    const escape = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [onClose]);

  const types = Object.entries(data?.by_type || {}).sort((a, b) => b[1] - a[1]);
  const totalValues = types.reduce((sum, [, count]) => sum + count, 0);
  const first = data?.days?.[0]?.day || '—';
  const last = data?.days?.[data.days.length - 1]?.day || '—';

  return html`
    <div class="scrim report-scrim" onClick=${(e) => e.target === e.currentTarget && onClose()}>
      <div class="report-sheet">
        <div class="report-actions">
          <button class="btn md primary" onClick=${() => window.print()}>ПЕЧАТЬ / PDF</button>
          <button class="btn md" onClick=${onClose}>ЗАКРЫТЬ</button>
        </div>
        <div class="report-body">
          <h2>Отчёт о защите персональных данных</h2>
          <div class="report-meta">
            организация <b>${org}</b> · период <b>${first} — ${last}</b> (${days} дней)<br />
            сформирован ${new Date().toLocaleString('ru-RU', { hour12: false })}
          </div>
          <table class="report-table">
            <tr><th>Показатель</th><th>Значение</th></tr>
            <tr><td>Обращений обработано</td><td>${num(data?.requests_total)}</td></tr>
            <tr><td>Значений защищено</td><td>${num(totalValues)}</td></tr>
          </table>
          <h3>По типам персональных данных</h3>
          <table class="report-table">
            <tr><th>Тип</th><th>Защищено значений</th></tr>
            ${types.map(([name, count]) => html`
              <tr><td>${name}</td><td>${num(count)}</td></tr>`)}
            ${!types.length && html`<tr><td colspan="2">Данных за период нет.</td></tr>`}
          </table>
          <p class="report-note">
            Отчёт сформирован локально, внутри контура организации. Он содержит
            только количественные показатели: ни текстов сообщений, ни токенов,
            ни самих значений в нём нет и по устройству системы быть не может.
            Персональные данные не покидали периметр организации.
          </p>
        </div>
      </div>
    </div>`;
}

function Stats({ org }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(14);
  const [report, setReport] = useState(false);
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
               link.download = `pseudex-${org}-${days}d.csv`;
               link.click();
               URL.revokeObjectURL(url);
             }}>ВЫГРУЗИТЬ CSV</a>
          <button class="btn sm primary" onClick=${() => setReport(true)}>ОТЧЁТ ЗА ПЕРИОД</button>
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
      ${report && html`<${PeriodReport} org=${org} data=${data} days=${days}
                                        onClose=${() => setReport(false)} />`}
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
            ['тариф', data?.plan || '—', ''],
            ['состояние лицензии', data?.state || '—', tone],
            ['код', data?.code || '—', data?.code ? 'pink' : ''],
            ['последняя аренда', data?.seconds_since_lease === null || data?.seconds_since_lease === undefined ? '—' : `${duration(data.seconds_since_lease)} назад`, ''],
            ['следующее продление', data?.next_renewal_in_s === null || data?.next_renewal_in_s === undefined ? '—' : `через ${duration(data.next_renewal_in_s)}`, ''],
            /* GRACE ONLY WHEN GRACE IS IN PLAY. Shown unconditionally it put
             * «остаток grace 13 мин» next to an active licence — a countdown to
             * nothing, which reads as time left on the subscription. Grace is
             * the window after OUR server stops answering; while renewals
             * succeed there is nothing to count down. */
            ...(data?.state === 'active' ? [] : [
              ['остаток grace', data?.state === 'expired' ? 'исчерпан' : duration(data?.grace_left_s), data?.state === 'expired' ? 'pink' : ''],
            ]),
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

/* ---------- integration ---------- */

/* ЕДИНСТВЕННЫЙ ЭКРАН ИЗ СПЕЦИФИКАЦИИ, КОТОРОГО НЕ БЫЛО (tz-local-ui §4.6), и
   спецификация называет причину: «важнейшее место интеграции» — поведение шлюза
   при 503. Продукт fail-closed, и если чужой шлюз при ошибке маскирования
   пропустит запрос дальше, ВСЯ ЗАЩИТА ОБНУЛЯЕТСЯ — молча, потому что ответ
   модели придёт как обычно. Сказать это на экране дешевле, чем узнать по
   инциденту.

   ТОКЕН ШЛЮЗА ЗДЕСЬ НЕ ПОКАЗЫВАЕТСЯ, И ЭТО РЕШЕНИЕ. Показать было бы удобнее и
   быстрее — но интерфейс держит ДРУГОЙ токен, операторский, и разделение этих
   двух ровно для того и сделано, чтобы скомпрометированная конфигурация шлюза
   не открывала раскрытие значений. Экран, который печатает второй секрет из-под
   первого, сводит разделение к оформлению. Вместо значения — место, где оно
   лежит: одна строка в логе контейнера. */

function snippets(base, org) {
  const url = JSON.stringify(base);
  const orgLiteral = JSON.stringify(org);
  return [
    ['LiteLLM callback', 'python', `# pseudex_hook.py — регистрируется как callback в LiteLLM
#
# ХУК ОБЯЗАН БЫТЬ МЕТОДОМ CustomLogger. Модульная функция с тем же именем не
# вызывается никогда: LiteLLM зовёт хуки на ЗАРЕГИСТРИРОВАННОМ экземпляре — ни
# ошибки, ни маскирования, сырые данные просто уходят провайдеру.
import os

import httpx
from litellm.integrations.custom_logger import CustomLogger

PSEUDEX = ${url}
TOKEN = os.environ["PSEUDEX_GATEWAY_TOKEN"]   # строка «ключ шлюза» в логе контейнера


class Pseudex(CustomLogger):
    def __init__(self):
        # ОДИН КЛИЕНТ НА ПРОЦЕСС: новый AsyncClient на каждый запрос — это новый
        # пул соединений на хопе перед КАЖДЫМ вызовом модели, и он не закрывается.
        self.http = httpx.AsyncClient(timeout=30)

    def _headers(self):
        return {"Authorization": f"Bearer {TOKEN}"}

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        r = await self.http.post(f"{PSEUDEX}/mask", headers=self._headers(),
            json={"org_id": ${orgLiteral}, "messages": data["messages"],
                  "tools": data.get("tools"),
                  # ЛИЧНОСТЬ ДИАЛОГА, А НЕ ЗАПРОСА. litellm_call_id свой у
                  # каждого обращения: с ним каждый ход — новый диалог, человек
                  # получает второй псевдоним на середине разговора, сущность
                  # оплачивается заново, а правило «частичное упоминание
                  # разрешается по полному» умирает — сопоставлять не с чем.
                  # Подставьте СВОЙ идентификатор беседы.
                  "conversation_id": (data.get("metadata") or {}).get("session_id")})
        r.raise_for_status()             # 503 обязан ОСТАНОВИТЬ запрос, см. выше
        data["messages"] = r.json()["messages"]
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        # ОБРАТНОЕ ПЛЕЧО ОБЯЗАТЕЛЬНО. Без него подстановки уезжают в ваши
        # инструменты вместо настоящих значений — то есть инструмент вызывается
        # на выдуманном человеке, и снаружи это выглядит как успешный вызов.
        r = await self.http.post(f"{PSEUDEX}/unmask", headers=self._headers(),
            json={"org_id": ${orgLiteral}, "response": response.model_dump()})
        r.raise_for_status()
        body = r.json()
        # ЧТО НЕ РАЗВЕРНУЛОСЬ: модель могла склонить или обрезать подстановку, и
        # тогда в аргумент инструмента уедет ФЕЙК — при статусе 200 и целом JSON.
        # Другого способа это увидеть нет.
        if body.get("residual_tokens"):
            raise ValueError(f"не развернулось: {body['residual_tokens']}")
        return body["response"]


pseudex_hook = Pseudex()     # в config.yaml: callbacks: [pseudex_hook.pseudex_hook]`],
    ['Сырой HTTP', 'bash', `# 1. Маскируем
curl -sS ${base}/mask \\
  -H "Authorization: Bearer $PSEUDEX_GATEWAY_TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{"org_id": ${orgLiteral}, "conversation_id": "dialog-42",
       "messages": [{"role": "user", "content": "Иванов Пётр, +7 916 214-88-03"}]}'

# 2. Свою модель зовёте сами — она видит только подстановки.

# 3. Возвращаем настоящие значения. Поле называется RESPONSE, и это ОБЪЕКТ
#    ответа целиком, а не строка: детокенизируется и текст, и аргументы вызовов
#    инструментов внутри него.
curl -sS ${base}/unmask \\
  -H "Authorization: Bearer $PSEUDEX_GATEWAY_TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{"org_id": ${orgLiteral}, "response": {"choices": [{"message":
       {"role": "assistant", "content": "…ответ модели…"}}]}}'

# В ответе смотрите residual_tokens: непустой список значит, что подстановка не
# развернулась и в инструмент уедет фейк — при статусе 200 и целом JSON.`],
    ['Стриминг', 'bash', `# ДВА РАЗНЫХ ЭНДПОЙНТА, И ПЕРЕПУТАТЬ ИХ НЕЛЬЗЯ.
#
# delta.content — по мере поступления:
curl -sS ${base}/unmask_chunk \\
  -H "Authorization: Bearer $PSEUDEX_GATEWAY_TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{"org_id": ${orgLiteral}, "delta": "…кусок текста…", "carry": "", "flush": false}'

# Возвращает {text, carry}: carry держите У СЕБЯ и отдавайте обратно, ОДИН на
# каждый choice.index — при n > 1 дельты идут вперемешку по одному соединению, и
# общий carry пришьёт хвост одного ответа к голове другого.

# arguments вызова инструмента — НАКОПИТЬ ЦЕЛИКОМ и отправить один раз:
curl -sS ${base}/unmask_arguments \\
  -H "Authorization: Bearer $PSEUDEX_GATEWAY_TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{"org_id": ${orgLiteral}, "arguments": ["{\\"phone\\": \\"+7 916 000-00-00\\"}"]}'

# Через /unmask_chunk их пропускать НЕЛЬЗЯ: он подставляет плоский текст, а
# настоящее значение — произвольная строка. «ООО "Заря"», вставленное плоской
# заменой, вносит две голых кавычки, и вызов перестаёт разбираться. На русском
# деловом трафике это обычный случай, а не краевой.`],
  ];
}

/* ВТОРАЯ ФОРМА РАЗВЁРТЫВАНИЯ, И АДРЕС У НЕЁ ДРУГОЙ, поэтому поле «адрес
   сайдкара» сюда НЕ подставляется: подставленный адрес выглядел бы рабочим и не
   работал. На сайдкаре нет `/v1/chat/completions`, у прокси нет `/mask`. */
function proxySnippet() {
  return `# Здесь Pseudex сам ходит к провайдеру, а вы меняете base_url клиента.
# Адрес — тот, на котором поднят ПРОКСИ (по умолчанию порт 4000), и ручек
# /mask и /unmask на нём нет.
import os

from openai import OpenAI

client = OpenAI(base_url="http://<адрес-прокси>:4000/v1",
                api_key=os.environ["PSEUDEX_TENANT_KEY"])   # sk-ps-…

answer = client.chat.completions.create(
    model="anthropic/claude-sonnet-4.5",
    messages=[{"role": "user", "content": "Клиент Иванов Пётр, +7 916 214-88-03"}],
    tools=tools)
# Инструменты вызываются на НАСТОЯЩИХ значениях: детокенизация происходит на
# нашей стороне, до того как аргументы уедут в ваш код.`;
}

const FAIL_CLOSED = `# ЕДИНСТВЕННОЕ МЕСТО, ГДЕ ОШИБКА ИНТЕГРАЦИИ НЕ ВИДНА НИКАК.
#
# 503 от /mask означает «маскирование сейчас не работает». Если ваш шлюз в этот
# момент пропустит запрос к модели, ответ придёт как обычно, метрики не
# дрогнут, и НИЧЕГО НЕ СЛУЧИТСЯ ВИДИМОГО — кроме того, что персональные данные
# ушли в модель открытым текстом. Обнаружится это не логом, а проверкой.

try:
    masked = await mask(messages)
except (httpx.HTTPStatusError, httpx.TransportError):
    # ТАК ПРАВИЛЬНО: отказать вызывающему.
    raise HTTPException(503, "маскирование недоступно, запрос не выполнен")

# ТАК НЕЛЬЗЯ, и это самая естественная строка на свете:
# except Exception:
#     masked = messages          # <- вся защита обнулилась, молча`;

/* ДОСЛОВНО ИЗ `docs/integration.md`, И ЭТО НЕ ФОРМАЛЬНОСТЬ.
   Здесь стоял мой пересказ той же мысли другими словами — то есть клиент
   получал ДВЕ РЕДАКЦИИ одной инструкции: одну со страницы документации, другую
   с этого экрана, и должен был сам решать, какая правильная. Каноническая — та,
   что в документации: она подпёрта живым замером v4 (`docs/tz-agentpii4.md` §7),
   а эта строка её цитирует. Правится в одном месте, оттуда переносится сюда. */
const AGENT_PROMPT = `Персональные данные клиента передавай в инструменты так, как они названы в
разговоре или пришли из инструмента, не пересчитывая и не проверяя
контрольные суммы. Поля, которых в разговоре не было (почтовый индекс,
возраст, инициалы, написание латиницей), не выводи сам — спроси клиента или
оставь пустыми, если схема это позволяет.`;

const TOKEN_GREP = 'docker logs pseudex 2>&1 | grep -A2 "ключ шлюза"';

function Integration({ org }) {
  const [copied, setCopied] = useState('');
  const [copyFailed, setCopyFailed] = useState(false);
  const [base, setBase] = useState(
    `${window.location.protocol}//${window.location.hostname}:8000`);

  /* КНОПКА НЕ ИМЕЕТ ПРАВА ГОВОРИТЬ «СКОПИРОВАНО», КОГДА НЕ СКОПИРОВАЛА.
     `navigator.clipboard` отсутствует на простом HTTP вне localhost — а это
     ровно то, как этот интерфейс и открывают, — и человек уходит вставлять
     пустоту, уверенный, что всё взял. */
  const copy = useCallback((label, text) => {
    const done = navigator.clipboard?.writeText(text);
    if (!done) { setCopyFailed(true); setTimeout(() => setCopyFailed(false), 2000); return; }
    done.then(() => {
      setCopied(label);
      setTimeout(() => setCopied(''), 1400);
    }).catch(() => {
      setCopyFailed(true);
      setTimeout(() => setCopyFailed(false), 2000);
    });
  }, []);

  const blocks = snippets(base, org);
  const label = (name) => (copied === name ? 'СКОПИРОВАНО'
    : copyFailed ? 'ВЫДЕЛИТЕ И СКОПИРУЙТЕ САМИ' : 'КОПИРОВАТЬ');

  return html`
    <div class="page">
      <div class="grid">
        <div class="cell lit pad-lg">
          <div class="label mb">АДРЕС САЙДКАРА</div>
          <div class="foot-note">Подставляется во все фрагменты ниже. Угадан по
            адресу, по которому открыт этот интерфейс, и порту 8000 — если ваш
            шлюз ходит к контейнеру иначе (имя сервиса в docker-сети, другой
            порт), впишите то, что видит он.</div>
          <input class="addr" value=${base} spellcheck="false"
                 onInput=${(event) => setBase(event.target.value)} />
          <div class="kv"><span class="k">org_id</span><span class="v mono">${org}</span></div>
          <div class="kv"><span class="k">ключ шлюза</span>
            <span class="v">печатается при старте контейнера</span></div>
          <div class="foot-note">Интерфейс его не показывает намеренно: он держит
            ДРУГОЙ токен, операторский, и разделение этих двух сделано ровно для
            того, чтобы скомпрометированная конфигурация шлюза не открывала
            раскрытие значений.</div>
          <div class="copybar">
            <code>${TOKEN_GREP}</code>
            <button onClick=${() => copy('token', TOKEN_GREP)}>${label('token')}</button>
          </div>
        </div>
      </div>

      <div class="grid attach">
        <div class="cell">
          <div class="label mb" style="color:var(--amber)">ПРИ ОШИБКЕ МАСКИРОВАНИЯ — БЛОКИРОВАТЬ ЗАПРОС</div>
          <div class="foot-note">Важнейшее место интеграции. Продукт fail-closed:
            любая ошибка маскирования обязана дойти до вызывающего как отказ.
            Шлюз, который в этот момент пропустит запрос дальше, обнулит защиту —
            и не оставит следа, по которому это можно заметить.</div>
          <${Snippet} name="fail-closed" lang="python" text=${FAIL_CLOSED}
                      label=${label} onCopy=${copy} />
        </div>
      </div>

      ${blocks.map(([name, lang, text]) => html`
        <div class="grid attach">
          <div class="cell">
            <div class="label mb">${name.toUpperCase()}</div>
            <${Snippet} name=${name} lang=${lang} text=${text}
                        label=${label} onCopy=${copy} />
          </div>
        </div>`)}

      <div class="grid attach">
        <div class="cell">
          <div class="label mb">OPENAI SDK — ЕСЛИ У ВАС РАЗВЁРНУТ ПРОКСИ</div>
          <div class="foot-note">Это ДРУГАЯ форма развёртывания и другой адрес:
            там Pseudex сам ходит к провайдеру, и ручек <span class="mono">/mask</span>
            и <span class="mono">/unmask</span> на том порту нет. Поле выше сюда
            не подставляется намеренно — подставленный адрес сайдкара выглядел бы
            рабочим и не работал.</div>
          <${Snippet} name="proxy" lang="python" text=${proxySnippet()}
                      label=${label} onCopy=${copy} />
        </div>
      </div>

      <div class="grid attach">
        <div class="cell">
          <div class="label mb">ФРАГМЕНТ СИСТЕМНОГО ПРОМПТА АГЕНТУ — ПО ЖЕЛАНИЮ</div>
          <div class="foot-note">
            <b>Это не требуется для работы</b>, и по умолчанию мы ваши промпты не
            трогаем — так написано в документации по интеграции, и так и есть.
            Фрагмент решает одну измеренную проблему: подстановки для СНИЛС, ИНН
            и карты намеренно НЕ проходят собственную контрольную сумму, чтобы
            подстановка никогда не совпала с чужим настоящим документом. Модель,
            которую попросили «проверь данные перед вызовом», видит невалидную
            сумму и отказывается вызывать инструмент. На нашем замере это
            16 троек из 36 — и это цена решения, а не дефект: движок такое не
            чинит и чинить не должен.
          </div>
          <${Snippet} name="prompt" lang="text" text=${AGENT_PROMPT}
                      label=${label} onCopy=${copy} />
        </div>
      </div>
    </div>`;
}

function Snippet({ name, lang, text, label, onCopy }) {
  return html`
    <div class="snip">
      <div class="snip-head">
        <span class="lang">${lang}</span>
        <button onClick=${() => onCopy(name, text)}>${label(name)}</button>
      </div>
      ${/* textContent, НЕ innerHTML: здесь этого достаточно, потому что htm
            подставляет значение как текстовый узел. Правило то же, что и на
            остальных экранах — они рендерят значения из ЧУЖОГО трафика, и
            склейка строк исполнила бы разметку, приехавшую внутри имени. */ ''}
      <pre>${text}</pre>
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
            : html`<div class="foot-note">Профилирование выключено. Включается <span class="mono">PSEUDEX_PROFILE=1</span>.</div>`}

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

/* ---------- reveals ---------- */

/* WHO LOOKED AT A REAL VALUE, ON A SCREEN.
 *
 * The engine has recorded every reveal since the audit log existed, and the
 * page for the customer's security officer promises exactly this record — but
 * there was no screen for it. Reading it meant curl and the admin token, so at
 * a hand-over an integrator could not open the one artefact the whole promise
 * rests on. The value is never in the record and is not shown here either: who,
 * which token, when, and whether it resolved.
 *
 * A MISS IS SHOWN AS LOUDLY AS A HIT. A sweep of guessed tokens leaves no other
 * trace, and a row that failed is the only sign of one.
 */
function Reveals({ org }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    engineGet('/reveals', { org_id: org, limit: 200 })
      .then((body) => { if (live) { setData(body); setError(''); } })
      .catch(() => { if (live) setError('движок не отвечает'); });
    return () => { live = false; };
  }, [org]);

  const rows = data?.reveals || [];
  return html`
    <div class="page">
      <h1 class="title">Раскрытия</h1>
      <div class="subtitle" style="margin-bottom:16px">
        Кто смотрел настоящие значения. Самого значения здесь нет и не будет —
        иначе журнал доступа стал бы второй копией того, что волт и существует,
        чтобы держать в одном месте.
      </div>
      ${error && html`<div class="foot-note" style="color:var(--pink);margin-bottom:12px">${error}</div>`}
      <div class="sec-meta" style="margin-bottom:14px">
        ${rows.length ? `всего за всё время: ${num(data.total)} · показаны последние ${rows.length}`
                      : 'раскрытий ещё не было'}
      </div>
      ${rows.length > 0 && html`
        <div class="table-wrap">
          <div class="trow head">
            <div>ВРЕМЯ</div><div>КТО</div><div>ТИП</div><div>ТОКЕН</div><div>РЕЗУЛЬТАТ</div>
          </div>
          ${rows.map((row) => html`
            <div class="trow">
              <div class="ts">${stamp(row.ts)}</div>
              <div class="agent">${row.actor || '—'}</div>
              <div class="type">${row.type || '—'}</div>
              <div class="token" title=${row.token}>${row.token}</div>
              <div class=${row.found ? 'prev' : 'prev pink'}>
                ${row.found ? 'значение выдано' : 'токен не найден'}
              </div>
            </div>`)}
        </div>`}
    </div>`;
}

/* ---------- shell ---------- */

const TABS = [
  ['СТАТУС', 'status'], ['ПЕСОЧНИЦА', 'sandbox'], ['ЖУРНАЛ', 'log'],
  ['СТАТИСТИКА', 'stats'], ['РАСКРЫТИЯ', 'reveals'],
  ['ИНТЕГРАЦИЯ', 'integration'],
  ['ПОДПИСКА', 'sub'], ['ДИАГНОСТИКА', 'diag'],
];

function App() {
  const [session, setSession] = useState(SESSION);
  const [org, setOrg] = useState('default');
  const [orgs, setOrgs] = useState([]);
  const [tab, setTab] = useState('status');
  const [status, setStatus] = useState(null);
  const [engineDown, setEngineDown] = useState(false);
  const [reveal, setReveal] = useState(null);
  const [blocked, setBlocked] = useState('');
  const [age, setAge] = useState(0);
  const timer = useRef(null);

  useEffect(() => {
    if (!session) return;
    api('/api/whoami').then((body) => setOrg(body.org_id)).catch(() => {});
    engineGet('/orgs').then((body) => {
      const seen = body.orgs || [];
      setOrgs(seen);
      // Follow the traffic. PSEUDEX_UI_ORG defaults to "default", but a real
      // gateway sends its own org_id, so the configured name is usually NOT one
      // that has any data. The operator then opens the interface, reads
      // "трафика ещё не было" beside a container that has been masking all day,
      // and concludes the product is broken. Selecting an org that exists is
      // the only reading that can be right; the picker still overrides it.
      setOrg((current) => (seen.length && !seen.includes(current) ? seen[0] : current));
    }).catch(() => {});
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
            <div class="brand-name">pseudex</div>
            <div class="chip">ЛОКАЛЬНЫЙ ИНТЕРФЕЙС</div>
          </div>
          <div class="meta">
            <span>org ${orgs.length > 1 || (orgs.length === 1 && orgs[0] !== org)
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
          ${tab === 'status' && html`<${Status} status=${status} engineDown=${engineDown} org=${org}
                                                goSandbox=${() => setTab('sandbox')}
                                                onBlocked=${setBlocked} />`}
          ${tab === 'sandbox' && html`<${Sandbox} org=${org} />`}
          ${tab === 'log' && html`<${Log} org=${org} onReveal=${setReveal} />`}
          ${tab === 'stats' && html`<${Stats} org=${org} />`}
          ${tab === 'reveals' && html`<${Reveals} org=${org} />`}
          ${tab === 'integration' && html`<${Integration} org=${org} />`}
          ${tab === 'sub' && html`<${Subscription} org=${org} />`}
          ${tab === 'diag' && html`<${Diagnostics} org=${org} />`}
        </main>
      </div>

      ${reveal && html`<${RevealModal} event=${reveal} org=${org} onClose=${() => setReveal(null)} />`}
      ${blocked && html`<${BlockedModal} reason=${blocked} onClose=${() => setBlocked('')} />`}
    </div>`;
}

render(html`<${App} />`, document.getElementById('root'));
