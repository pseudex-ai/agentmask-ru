/* Интерактив главной страницы.
 *
 * ПРИМЕРЫ ЖИВУТ ЗДЕСЬ, И НА СТРАНИЦЕ НЕТ НИ ОДНОГО ПОЛЯ ВВОДА ДЛЯ ТЕКСТА. Это
 * не упрощение: поле «попробуйте на своём тексте» означало бы, что наш сервер
 * начинает принимать чужие персональные данные — ровно то, что продукт продаёт
 * НЕ делать. Кто хочет свой текст, делает это в локальном интерфейсе, внутри
 * своего контура.
 *
 * Всё рисуется узлами DOM, никогда `innerHTML`. Строки ниже наши сегодня, но
 * страница, которая собирает разметку из данных, на один рефакторинг отстоит от
 * страницы, которую кормят данными, написанными не нами.
 *
 * Оформление узлов, созданных здесь, лежит классами в `landing.css`: этих узлов
 * нет в разметке, поэтому второй копии стиля не возникает.
 */

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ────────────────────────────────────────────────────────────────────────────
 * ГЕРОЙ: ОДИН ЗАКАЗ ЦЕЛИКОМ
 *
 * Три разные заявки, а не одна по кругу: подмена везде своя — имя, документы,
 * контакты. `text` — куски реплики; пара из двух строк это «настоящее» и
 * «подмена» одного значения, одиночная строка — обычный текст.
 * ──────────────────────────────────────────────────────────────────────────── */
const HERO_STEPS = ["", "СООБЩЕНИЕ КЛИЕНТА", "НАХОДИМ", "ПОДМЕНЯЕМ",
                    "МОДЕЛЬ ПОНЯЛА ЗАДАЧУ", "ВАША СИСТЕМА ПОЛУЧИЛА", "ГОТОВО"];

const HERO_CASES = [
  {
    source: "МЕССЕНДЖЕР · КЛИЕНТ ПИШЕТ САМ",
    text: [["здрасте! это "], ["волков дмитрий", "шилов виктор"],
           [", заказ 4471\nможно завтра привезти? адрес "],
           ["мончгорская 12 кв 84", "чистопольская 41 кв 57"],
           ["\nтел "], ["89178347030", "89035571942"], [", он же в заказе"]],
    decision: "Клиент просит перенести доставку на завтра и даёт адрес с телефоном.",
    system: "ЗАЯВКА НА ПЕРЕНОС",
    record: [["Клиент", "Волков Дмитрий"], ["Телефон", "+7 917 834-70-30"],
             ["Адрес", "Мончегорская 12, кв. 84"]],
    done: "Опечатка в улице исправлена до того, как адрес ушёл в CRM. Модель видела другую улицу.",
  },
  {
    source: "ЗВОНОК · РАСШИФРОВКА ОПЕРАТОРА",
    text: [["звонила "], ["ерёмина ольга", "соколова марина"], [", адрес записал со слов\n"],
           ["фруктовая сто двадцать шесть", "грушевая шестьдесят три"], [", "],
           ["тридцать четвёртая квартира", "пятьдесят седьмая квартира"],
           ["\nдомофон не работает, звонить в дверь"]],
    decision: "Создать обращение и предупредить курьера про домофон.",
    system: "ОБРАЩЕНИЕ В CRM",
    record: [["Клиент", "Ерёмина Ольга Тимуровна"], ["Адрес", "Фруктовая 126, кв. 34"],
             ["Примечание", "домофон не работает"]],
    done: "Числа словами легли в базу цифрами — в том виде, в каком их ждёт CRM.",
  },
  {
    source: "ОПЕРАТОР · КОПИЯ ИЗ ФОРМЫ",
    text: [["оформляем полис\n"], ["BITYUKOVA E. A.", "SOKOLOVA M. I."], [" (в паспорте "],
           ["Битюкова Елена Андреевна", "Соколова Марина Игоревна"], [")\nснилс "],
           ["112-233-445 95", "284-119-703 41"], [" инн "],
           ["770512345678", "771903845206"]],
    decision: "Заполнить черновик полиса — имя пришло в двух видах, но человек один.",
    system: "ЧЕРНОВИК ПОЛИСА",
    record: [["Страхователь", "Битюкова Елена Андреевна"], ["СНИЛС", "112-233-445 95"],
             ["ИНН", "770512345678"]],
    done: "Латиница из формы и имя из паспорта опознаны как один человек, контрольные суммы сошлись.",
  },
];

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

/* Токен, который перетекает из настоящего значения в подмену. Обе версии лежат
   в одной ячейке grid: ширина берётся по длинной, поэтому строка не дёргается
   при разной длине настоящего и подменённого значения. */
function heroToken(real, fake) {
  const token = node("span", "hero-token");
  token.append(node("span", "hero-token-real", real), node("span", "hero-token-fake", fake));
  return token;
}

function heroBubble(label, tone, body) {
  const bubble = node("div", `hero-bubble hero-bubble--${tone}`);
  bubble.append(node("div", "hero-bubble-label", label));
  const wrap = node("div", "hero-bubble-body");
  wrap.appendChild(body);
  bubble.appendChild(wrap);
  return bubble;
}

function heroRecord(rows) {
  const card = node("div", "hero-record");
  rows.forEach(([label, value], index) => {
    const row = node("div", "hero-record-row");
    row.style.transitionDelay = `${index * 0.12}s`;
    row.append(node("span", "hero-record-label", label),
               node("span", "hero-record-value", value));
    card.appendChild(row);
  });
  return card;
}

function heroBuild(index) {
  const example = HERO_CASES[index];
  const said = node("span", "hero-said");
  example.text.forEach(([real, fake]) => {
    said.appendChild(fake ? heroToken(real, fake) : document.createTextNode(real));
  });
  const dialog = node("div", "hero-dialog");
  const bubbles = [
    heroBubble(example.source, "muted", said),
    heroBubble("МОДЕЛЬ ПОНЯЛА", "accent", node("span", "hero-prose", example.decision)),
    heroBubble(example.system, "green", heroRecord(example.record)),
    heroBubble("ГОТОВО", "green", node("span", "hero-prose hero-prose--dim", example.done)),
  ];
  bubbles.forEach((bubble) => dialog.appendChild(bubble));
  return { dialog, bubbles, tokens: Array.from(dialog.querySelectorAll(".hero-token")) };
}

/* Фаза — единственное состояние героя, и каждый шаг ставит ровно один класс.
   Поэтому «перемотать» историю в любую точку можно одним вызовом: это и делает
   первый кадр, и он же показывает финал, когда движение выключено. */
function heroApply(parts, phase) {
  parts.bubbles.forEach((bubble, i) => {
    const at = [1, 4, 5, 6][i];
    bubble.classList.toggle("is-shown", phase >= at);
    bubble.classList.toggle("is-lit", phase >= (i === 0 ? 3 : at));
  });
  parts.tokens.forEach((token) => {
    token.classList.toggle("is-found", phase >= 2);
    token.classList.toggle("is-swapped", phase >= 3);
  });
  parts.dialog.classList.toggle("is-filed", phase >= 5);
}

function heroStart() {
  const stage = document.getElementById("hero-dialog");
  const phaseLabel = document.getElementById("hero-phase");
  if (!stage) return;

  let index = 0;
  let phase = reduceMotion ? 6 : 1;
  let parts = heroBuild(index);
  stage.replaceChildren(parts.dialog);
  if (phaseLabel) phaseLabel.textContent = HERO_STEPS[phase];
  /* БЕЗ ДВИЖЕНИЯ — СРАЗУ ФИНАЛ, А НЕ ПУСТАЯ ПАНЕЛЬ. Человек, который попросил
     систему не двигать картинку, просил об этом, а не о том, чтобы остаться без
     содержимого. */
  if (reduceMotion) {
    heroApply(parts, phase);
    return;
  }
  /* Класс, включающий переход, нельзя ставить в том же тике, где узел только
     что вставлен в DOM: браузер ещё не отрисовал скрытое начальное состояние
     (opacity:0) и просто перескочит к финалу без анимации. Два кадра растра
     дают ему этот кадр — иначе самое первое сообщение появляется не плавно, а
     сразу целиком. */
  requestAnimationFrame(() => requestAnimationFrame(() => heroApply(parts, phase)));

  const FADE_MS = 750; // = длительность .hero-bubble transition в landing.css
  setInterval(() => {
    phase = (phase + 1) % 7;
    if (phaseLabel) phaseLabel.textContent = HERO_STEPS[phase];
    /* Кадр 0 — пауза между заявками. Сначала гасим текущие реплики и ждём,
       пока затухание доиграет, и только потом подменяем DOM на следующий
       пример — иначе узлы исчезают вместе со сменой разметки, минуя переход,
       и смена примера выглядит как рывок, а не как затухание. */
    if (phase === 0) {
      heroApply(parts, phase);
      setTimeout(() => {
        index = (index + 1) % HERO_CASES.length;
        parts = heroBuild(index);
        stage.replaceChildren(parts.dialog);
      }, FADE_MS);
      return;
    }
    heroApply(parts, phase);
  }, 1700);
}

heroStart();


/* ────────────────────────────────────────────────────────────────────────────
 * ПОЛОСА ПРОЧИТАННОГО И ПОЯВЛЕНИЕ БЛОКОВ
 * ──────────────────────────────────────────────────────────────────────────── */
const header = document.querySelector("header.top");
if (header) {
  const line = node("div", "scroll-line");
  header.appendChild(line);
  const onScroll = () => {
    const root = document.documentElement;
    const max = root.scrollHeight - root.clientHeight;
    line.style.width = `${max > 0 ? Math.min(1, root.scrollTop / max) * 100 : 0}%`;
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

const revealable = document.querySelectorAll("[data-reveal]");
if (!("IntersectionObserver" in window)) {
  /* Страховка на случай, когда наблюдателя нет: блоки начинают прозрачными, и
     без того, кто снимет прозрачность, половина страницы просто не видна. */
  revealable.forEach((element) => element.classList.add("is-in"));
} else {
  const shower = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-in");
      shower.unobserve(entry.target);
    });
  }, { rootMargin: "-40px 0px -10% 0px" });
  revealable.forEach((element) => shower.observe(element));
}


/* ────────────────────────────────────────────────────────────────────────────
 * СЧЁТЧИКИ
 *
 * Значение уже напечатано сервером — скрипт лишь досчитывает его на глазах,
 * один раз, когда полоса попала в кадр. Поэтому без скриптов и до их запуска на
 * странице стоит правильное число, а не ноль.
 * ──────────────────────────────────────────────────────────────────────────── */
function runCounters(cells) {
  const started = performance.now();
  const tick = (now) => {
    const passed = Math.min(1, (now - started) / 1100);
    const eased = 1 - Math.pow(1 - passed, 3);
    cells.forEach((cell) => {
      const target = Number(cell.dataset.countTo);
      const digits = Number(cell.dataset.countDec || 0);
      const shown = (target * eased).toFixed(digits).replace(".", ",");
      cell.textContent = `${cell.dataset.countPrefix || ""}${shown}${cell.dataset.countSuffix || ""}`;
    });
    if (passed < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

const counters = Array.from(document.querySelectorAll("[data-count-to]"));
if (counters.length && !reduceMotion && "IntersectionObserver" in window) {
  const band = counters[0].closest("[data-counters]") || counters[0];
  const watcher = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      runCounters(counters);
      watcher.disconnect();
    });
  }, { rootMargin: "-80px 0px" });
  watcher.observe(band);
}


/* ────────────────────────────────────────────────────────────────────────────
 * ДЕМО: ТРУДНЫЕ ФОРМЫ, А НЕ ПОКАЗАТЕЛЬНЫЕ
 *
 * Каждая — из тех, на которых детекция спотыкается: строчные без запятых, числа
 * словами, латинская раскладка, значение, размазанное по репликам, речь после
 * распознавания.
 * ──────────────────────────────────────────────────────────────────────────── */
const DEMOS = [
  {
    hint: "Ни заглавных, ни запятых, ни слова «адрес». Опечатка в улице: так её пишет клиент, а не реестр.",
    orig: [["клиент "], ["волков дмитрий", "pii"], [" адрес "], ["мончгорская 12 кв 84", "pii"],
           ["\nтел "], ["89178347030", "pii"], [" перезвоните после шести"]],
    masked: [["клиент "], ["шилов виктор", "fake"], [" адрес "], ["чистопольская 41 кв 57", "fake"],
             ["\nтел "], ["89035571942", "fake"], [" перезвоните после шести"]],
  },
  {
    hint: "Цифр в тексте нет вообще — адрес и квартира записаны словами, как в расшифровке звонка.",
    orig: [["записал со слов: "], ["фруктовая сто двадцать шесть", "pii"], [", второй подъезд,\n"],
           ["тридцать четвёртая квартира", "pii"], [", домофон не работает"]],
    masked: [["записал со слов: "], ["грушевая шестьдесят три", "fake"], [", второй подъезд,\n"],
             ["пятьдесят седьмая квартира", "fake"], [", домофон не работает"]],
  },
  {
    hint: "Одна и та же женщина в трёх видах: латиницей из формы, инициалами и полным именем. Все три — один человек и одна подмена.",
    orig: [["в форме "], ["BITYUKOVA E. A.", "pii"], [", в заявке "], ["Т. О.", "pii"],
           [",\nв письме "], ["Битюкова Елена", "pii"], [" — это один клиент?"]],
    masked: [["в форме "], ["SOKOLOVA M. I.", "fake"], [", в заявке "], ["С. М.", "fake"],
             [",\nв письме "], ["Соколова Марина", "fake"], [" — это один клиент?"]],
  },
  {
    hint: "Фамилия, имя и адрес приходят в разных репликах. По одной реплике нечего искать — значение собирается из диалога.",
    orig: [["— моя фамилия "], ["волков", "pii"], ["\n— а имя и адрес?\n— "], ["дмитрий", "pii"],
           [", живу на "], ["ленина 5", "pii"], [", кв. 12"]],
    masked: [["— моя фамилия "], ["шилов", "fake"], ["\n— а имя и адрес?\n— "], ["виктор", "fake"],
             [", живу на "], ["грушевой 63", "fake"], [", кв. 57"]],
  },
  {
    hint: "Самая частая в отрасли форма опознания клиента — «фамилия имя дата рождения». Рядом СНИЛС и ИНН: у обоих сходится контрольная сумма, и у подмены тоже.",
    orig: [["Оформляем: "], ["Тарасова Ольга 14.03.1985", "pii"], ["\nСНИЛС "],
           ["112-233-445 95", "pii"], [", ИНН "], ["770512345678", "pii"],
           ["\nдоговор 2024/117 — не персональные, остаётся как есть"]],
    masked: [["Оформляем: "], ["Соколова Марина 22.07.1983", "fake"], ["\nСНИЛС "],
             ["284-119-703 41", "fake"], [", ИНН "], ["771903845206", "fake"],
             ["\nдоговор 2024/117 — не персональные, остаётся как есть"]],
  },
];

function paint(target, chunks) {
  if (!target) return;
  /* Новый узел, а не правка старого: смена примера должна читаться как смена
     примера, а подмена текста на месте выглядит как глитч. */
  const swap = node("div", "demo-swap");
  chunks.forEach(([text, kind]) => {
    const piece = node("span", kind === "pii" ? "mark-pii" : kind === "fake" ? "mark-fake" : null, text);
    swap.appendChild(piece);
  });
  target.replaceChildren(swap);
  /* БЕЗ ДВИЖЕНИЯ — СРАЗУ ФИНАЛ, А НЕ ПУСТАЯ ПАНЕЛЬ. `is-in` снимает
     `opacity: 0`, и ветка «меньше движения» обязана его поставить: она
     отключает ПЕРЕХОД, а не содержимое. Без этой строки демо-примеры
     оставались невидимыми ровно у тех, кто попросил поменьше движения. */
  if (reduceMotion) {
    swap.classList.add("is-in");
    return;
  }
  /* Класс, включающий переход, нельзя ставить в том же тике, где узел только
     что вставлен: браузер ещё не отрисовал скрытое начальное состояние и
     перескочит к финалу без анимации — тот же приём, что и в heroStart. */
  requestAnimationFrame(() => requestAnimationFrame(() => swap.classList.add("is-in")));
}

const DEMO_FADE_MS = 500; // = длительность .demo-swap transition в landing.css

function showDemo(index) {
  const example = DEMOS[index];
  const origTarget = document.getElementById("demo-orig");
  const maskedTarget = document.getElementById("demo-masked");
  const hint = document.getElementById("demo-hint");
  if (hint) hint.textContent = example.hint;
  document.querySelectorAll("[data-demo]").forEach((button) => {
    button.setAttribute("aria-selected", String(Number(button.dataset.demo) === index));
  });

  const current = origTarget && origTarget.querySelector(".demo-swap");
  if (!current || reduceMotion) {
    paint(origTarget, example.orig);
    paint(maskedTarget, example.masked);
    return;
  }
  /* Сначала гасим текущий текст и ждём, пока затухание доиграет, и только
     потом подменяем DOM на следующий пример — иначе старая реплика исчезает
     вместе со сменой разметки, минуя переход, и смена вкладки выглядит как
     рывок, а не как затухание. */
  document.querySelectorAll("#demo-orig .demo-swap, #demo-masked .demo-swap")
    .forEach((el) => el.classList.remove("is-in"));
  setTimeout(() => {
    paint(origTarget, example.orig);
    paint(maskedTarget, example.masked);
  }, DEMO_FADE_MS);
}

document.querySelectorAll("[data-demo]").forEach((button) => {
  button.addEventListener("click", () => showDemo(Number(button.dataset.demo)));
});
if (document.getElementById("demo-orig")) showDemo(0);


/* ────────────────────────────────────────────────────────────────────────────
 * КОПИРОВАНИЕ
 * ──────────────────────────────────────────────────────────────────────────── */
document.querySelectorAll("[data-copy-btn]").forEach((button) => {
  button.addEventListener("click", () => {
    /* Источник обычно сосед кнопки, но блок может объявить область шире —
       у промпта для агента кнопка стоит в шапке блока, а не рядом с текстом. */
    const scope = button.closest("[data-copy-scope]") || button.parentElement;
    const source = scope.querySelector("[data-copy]");
    if (!source) return;
    navigator.clipboard?.writeText(source.dataset.copy);
    const was = button.textContent;
    button.textContent = "СКОПИРОВАНО";
    setTimeout(() => { button.textContent = was; }, 1500);
  });
});


/* ────────────────────────────────────────────────────────────────────────────
 * УСТАНОВКА: ВЫБРАЛ ПРОВАЙДЕРА — ПОЛУЧИЛ ГОТОВЫЕ КОМАНДЫ
 *
 * Деление на «прямых» и остальных честное, а не косметическое. Провайдер
 * «прямой», только если он говорит в ФОРМАТЕ ЗАПРОСА OpenAI, потому что именно
 * эту форму мы разбираем, чтобы найти, что маскировать. Anthropic и Gemini
 * кладут текст пользователя в другое место; GigaChat выглядит OpenAI-совместимым,
 * но авторизуется в два шага на другом хосте; YandexGPT использует
 * `messages[].text` вместо `content`. Назвать любого из них «просто поменяйте
 * URL» — это ложь, которая вскроется при интеграции, то есть в худший момент.
 * ──────────────────────────────────────────────────────────────────────────── */
const PROVIDERS = [
  { upstream: "https://openrouter.ai/api/v1", key: "sk-or-v1-…", direct: true },
  { upstream: "https://api.openai.com/v1", key: "sk-proj-…", direct: true },
  { upstream: "https://api.deepseek.com/v1", key: "sk-…", direct: true },
  { upstream: "http://vllm:8000/v1", key: "любой", direct: true },
  { direct: false },
];

const NOTES = {
  direct: "Ключ провайдера остаётся вашим: он идёт в заголовке запроса и пересылается наверх нетронутым. Мы его не храним и не выдаём свой. Сюда же подходит любой другой OpenAI-совместимый провайдер — меняется только адрес.",
  litellm: "У этих провайдеров другой формат запроса — текст пользователя лежит не там, где у OpenAI, а GigaChat ещё и авторизуется в два шага. Ставится LiteLLM, который приводит их к общему виду, pseudex подключается к нему сайдкаром.",
};

function setBlock(id, text) {
  const target = document.getElementById(id);
  if (!target) return;
  target.textContent = text;
  target.dataset.copy = text;
}

function showProvider(index) {
  const provider = PROVIDERS[index];
  const setup = document.getElementById("setup");
  if (!setup) return;
  const image = setup.dataset.image;

  document.querySelectorAll("[data-provider]").forEach((button) => {
    button.setAttribute("aria-selected", String(Number(button.dataset.provider) === index));
  });
  const note = document.getElementById("provider-note");
  if (note) note.textContent = provider.direct ? NOTES.direct : NOTES.litellm;

  const title2 = document.getElementById("step2-title");
  const title3 = document.getElementById("step3-title");
  if (provider.direct) {
    if (title2) title2.textContent = "Поднять контейнер";
    if (title3) title3.textContent = "Направить приложение к нам";
    /* `PSEUDEX_ROLE=proxy` — не украшение: без него образ поднимается сайдкаром
       и на `/v1/chat/completions` не отвечает. Команда со страницы обязана
       работать дословно, иначе первый же шаг установки заканчивается ошибкой. */
    setBlock("step2-code",
      "docker run -d --name pseudex \\\n" +
      "  -p 8000:8000 -p 127.0.0.1:8081:8081 \\\n" +
      "  -v pseudex-data:/data \\\n" +
      "  -e PSEUDEX_ROLE=proxy \\\n" +
      `  -e PSEUDEX_UPSTREAM=${provider.upstream} \\\n` +
      "  -e PSEUDEX_LICENSE_KEY=ps_live_… \\\n" +
      `  ${image}`);
    setBlock("step3-code",
      `# было\nOPENAI_BASE_URL=${provider.upstream}\n\n` +
      "# стало — одна строка\nOPENAI_BASE_URL=http://pseudex:8000/v1\n" +
      `OPENAI_API_KEY=${provider.key}  # как был`);
  } else {
    if (title2) title2.textContent = "Поднять контейнер рядом с LiteLLM";
    if (title3) title3.textContent = "Добавить callback в LiteLLM";
    setBlock("step2-code",
      "docker run -d --name pseudex \\\n" +
      "  -p 8000:8000 -p 127.0.0.1:8081:8081 \\\n" +
      "  -v pseudex-data:/data \\\n" +
      "  -e PSEUDEX_LICENSE_KEY=ps_live_… \\\n" +
      `  ${image}`);
    setBlock("step3-code",
      'masked = post("http://pseudex:8000/mask",\n' +
      '  {"org_id": org, "messages": messages})\n' +
      "# → модель → обратно через /unmask");
  }
}

document.querySelectorAll("[data-provider]").forEach((button) => {
  button.addEventListener("click", () => showProvider(Number(button.dataset.provider)));
});
if (document.getElementById("setup")) showProvider(0);


/* ────────────────────────────────────────────────────────────────────────────
 * ВЫБОР ТАРИФА ИЗ ПРАЙСА
 *
 * Форма на странице ОДНА, и кнопка в карточке приводит к ней с уже выбранным
 * тарифом. Раньше форма стояла в каждой карточке, и три из четырёх не могли
 * отправиться — они собирали одно согласие из двух. С одной формой этот класс
 * ошибки исчезает: сломать нечего, дублировать нечего.
 * ──────────────────────────────────────────────────────────────────────────── */
document.querySelectorAll("[data-plan]").forEach((link) => {
  link.addEventListener("click", () => {
    const select = document.querySelector('#signup-form select[name="plan"]');
    if (select) select.value = link.dataset.plan;
    const email = document.querySelector('#signup-form input[name="email"]');
    /* Фокус — после прокрутки: поставленный сразу, он прокручивает страницу сам
       и спорит с якорем. */
    if (email) setTimeout(() => email.focus({ preventScroll: true }), 400);
  });
});


/* ────────────────────────────────────────────────────────────────────────────
 * КОНФИГУРАТОР: «ЧТО У ВАС В ПЕРЕПИСКЕ»
 *
 * Своего текста мы не просим и не примем — отмечаются ГРУППЫ. Наружу уходят
 * только коды групп: ни текста, ни адреса, ни кто вы. Подробности — в докстринге
 * `views.demand`.
 * ──────────────────────────────────────────────────────────────────────────── */
const cfg = document.getElementById("cfg");

function cfgSelected() {
  return Array.from(cfg.querySelectorAll("input[type=checkbox]")).filter((box) => box.checked);
}

function cfgRender() {
  const chosen = cfgSelected();
  const out = document.getElementById("cfg-out");
  if (!chosen.length) {
    out.hidden = true;
    return;
  }
  out.hidden = false;

  const verdicts = document.getElementById("cfg-verdicts");
  verdicts.textContent = "";
  chosen.forEach((box) => {
    const covered = box.dataset.covered === "1";
    const row = node("div", "cfg-verdict");
    row.append(
      node("span", covered ? "cfg-mark yes" : "cfg-mark no", covered ? "НАХОДИМ" : "В РАЗРАБОТКЕ"),
      node("b", null, box.closest("label").querySelector(".cfg-label").textContent),
      /* textContent, не innerHTML: строка приезжает из шаблона, но правило одно
         на всю страницу — склейка разметки из данных однажды получит данные,
         которых мы не писали. */
      node("span", null, box.dataset.verdict || ""));
    verdicts.appendChild(row);
  });

  const gaps = chosen.filter((box) => box.dataset.covered !== "1");
  const note = document.getElementById("cfg-note");
  const send = document.getElementById("cfg-send");
  if (!gaps.length) {
    /* ТЗ вертикалей §2: ритейл мы покрываем ПОЛНОСТЬЮ, и это надо показать как
       выполненную работу, а не спрятать. */
    note.textContent = "Всё отмеченное мы находим сегодня — докупать ничего не нужно.";
    send.hidden = true;
  } else {
    note.textContent = gaps.length === 1
      ? "Одна группа в разработке. Отправьте отметку — она попадёт в счётчик спроса, по которому строится очередь работ."
      : `Групп в разработке: ${gaps.length}. Отправьте отметки — они попадут в счётчик спроса, по которому строится очередь работ.`;
    send.hidden = false;
  }
}

function cfgCookie(name) {
  const found = document.cookie.split("; ").find((part) => part.startsWith(`${name}=`));
  return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
}

async function cfgSend() {
  const send = document.getElementById("cfg-send");
  const note = document.getElementById("cfg-note");
  const groups = cfgSelected()
    .filter((box) => box.dataset.covered !== "1")
    .map((box) => box.dataset.group);
  if (!groups.length) return;
  send.disabled = true;
  try {
    const response = await fetch("/demand", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cfgCookie("csrftoken") },
      body: JSON.stringify({ groups }),
    });
    /* ОТКАЗ НАЗЫВАЕТСЯ ОТКАЗОМ. Кнопка, говорящая «спасибо» на 429, учит не
       верить кнопкам — тот же промах, что уже был на «СКОПИРОВАНО» в локальном
       интерфейсе, когда буфер обмена недоступен. */
    note.textContent = response.ok
      ? "Записали. Это меняет очередь работ — спасибо."
      : "Не отправилось. Попробуйте позже.";
    send.hidden = response.ok;
  } catch {
    note.textContent = "Не отправилось: нет связи.";
  } finally {
    send.disabled = false;
  }
}

if (cfg) {
  cfg.addEventListener("change", cfgRender);
  document.getElementById("cfg-send").addEventListener("click", cfgSend);
  /* ВЕРДИКТ РИСУЕТСЯ И НА ЗАГРУЗКЕ. Браузер восстанавливает отмеченные галочки
     при перезагрузке и при возврате «назад», а `#cfg-out` при этом оставался
     спрятанным: отмечено три группы, вердикта нет. Соседние блоки в этом файле
     тоже задают начальное состояние — `showDemo(0)`, `showProvider(0)`. */
  cfgRender();
}

/* ────────────────────────────────────────────────────────────────────────────
 * ВОПРОСЫ: ОТВЕТ РАСКРЫВАЕТСЯ, А НЕ ПОЯВЛЯЕТСЯ РЫВКОМ
 *
 * `<details>` сам переключает `display` — свойство, которое CSS не умеет
 * анимировать. Поэтому клик перехватывается здесь: высота ответа ставится по
 * `scrollHeight` и меняется на 0, переход делает `.faq-a` в landing.css, а
 * `details.open` выставляется уже ПОСЛЕ анимации закрытия — иначе `display:none`
 * обрубил бы её на середине. */
document.querySelectorAll("#faq details").forEach((details) => {
  const summary = details.querySelector("summary");
  const answer = details.querySelector(".faq-a");
  if (!summary || !answer) return;

  summary.addEventListener("click", (event) => {
    event.preventDefault();
    /* БЕЗ ПЕРЕХОДА НЕ БЫВАЕТ `transitionend`, И ОТВЕТ НЕ ЗАКРЫЛСЯ БЫ ВООБЩЕ.
       При «уменьшить движение» CSS гасит переход, поэтому закрытие, которое
       ждёт окончания анимации, не наступает никогда. Здесь состояние
       переключается напрямую — без анимации, но и без залипания. */
    if (reduceMotion) {
      details.open = !details.open;
      answer.style.maxHeight = details.open ? "none" : "0px";
      return;
    }
    if (details.open) {
      // Сначала переводим max-height из "none" в текущую высоту пикселями —
      // без этого шага браузер не видит, ОТКУДА анимировать, и прыгает сразу
      // в ноль.
      answer.style.maxHeight = `${answer.scrollHeight}px`;
      void answer.offsetHeight; // форсируем реflow между двумя присвоениями
      answer.style.maxHeight = "0px";
      answer.addEventListener("transitionend", function onClose(event) {
        if (event.propertyName !== "max-height") return;
        details.open = false;
        answer.removeEventListener("transitionend", onClose);
      });
    } else {
      details.open = true;
      answer.style.maxHeight = "0px";
      void answer.offsetHeight;
      answer.style.maxHeight = `${answer.scrollHeight}px`;
      answer.addEventListener("transitionend", function onOpen(event) {
        if (event.propertyName !== "max-height") return;
        // "none", а не пиксели: иначе перенос строки при ресайзе окна обрежет
        // текст рамкой высоты, посчитанной для другой ширины.
        answer.style.maxHeight = "none";
        answer.removeEventListener("transitionend", onOpen);
      });
    }
  });
});
