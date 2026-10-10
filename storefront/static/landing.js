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
const HERO_STEPS = ["", "КЛИЕНТ", "НАХОДИМ", "ПОДМЕНЯЕМ",
                    "МОДЕЛЬ", "СИСТЕМА", "ГОТОВО"];

const HERO_CASES = [
  {
    source: "КЛИЕНТ ПИШЕТ",
    text: [["здрасте! это "], ["волков дмитрий", "шилов виктор"],
           [", заказ 4471\nпривезти завтра? адрес "],
           ["мончгорская 12 кв 84", "чистопольская 41 кв 57"],
           ["\nтел "], ["89178347030", "89035571942"]],
    decision: "Перенести доставку на завтра.",
    system: "ЗАЯВКА НА ПЕРЕНОС",
    record: [["Клиент", "Волков Дмитрий"], ["Адрес", "Мончегорская 12, кв. 84"]],
    done: "Опечатку в улице исправил словарь — до CRM.",
  },
  {
    source: "ЗВОНОК · РАСШИФРОВКА",
    text: [["звонила "], ["ерёмина ольга", "соколова марина"], [", адрес "],
           ["фруктовая сто двадцать шесть", "грушевая шестьдесят три"],
           [", кв. "], ["тридцать четыре", "пятьдесят семь"]],
    decision: "Создать обращение, предупредить курьера.",
    system: "ОБРАЩЕНИЕ В CRM",
    record: [["Клиент", "Ерёмина Ольга"], ["Адрес", "Фруктовая 126, кв. 34"]],
    done: "Числа словами легли в базу цифрами.",
  },
  {
    source: "ОПЕРАТОР · ФОРМА",
    text: [["полис на "], ["BITYUKOVA E. A.", "SOKOLOVA M. I."], ["\nв паспорте "],
           ["Битюкова Елена Андреевна", "Соколова Марина Игоревна"]],
    decision: "Заполнить черновик: имя пришло в двух видах.",
    system: "ЧЕРНОВИК ПОЛИСА",
    record: [["Страхователь", "Битюкова Елена Андреевна"],
             ["Телефон", "+7 916 214-88-03"]],
    done: "Латиница и паспорт — один человек.",
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
    heroBubble("МОДЕЛЬ", "accent", node("span", "hero-prose", example.decision)),
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

/* ВЫДЕРЖКА У КАЖДОГО ШАГА СВОЯ, И ЭТО И ЕСТЬ «КИНО». Ровный интервал читается
   как слайд-шоу: сообщение, подсветка и подмена пролетают с одной скоростью, и
   глаз не успевает заметить, ЧТО произошло. Здесь сообщение читается дольше,
   подмена — самый короткий и резкий кадр, финал держится дольше всех. */
const HERO_DWELL = { 1: 1650, 2: 1150, 3: 1250, 4: 1750, 5: 1850, 6: 2300, 0: 900 };

function heroStart() {
  const stage = document.getElementById("hero-dialog");
  const phaseLabel = document.getElementById("hero-phase");
  const rail = document.getElementById("hero-rail");
  const panel = document.getElementById("hero-panel");
  if (!stage) return;

  let index = 0;
  let phase = reduceMotion ? 6 : 1;
  let parts = heroBuild(index);
  let timer = 0;
  let idle = 0;
  let paused = false;
  stage.replaceChildren(parts.dialog);

  /* ШКАЛА-ТАЙМЛАЙН: шесть сегментов, по одному на шаг. Она отвечает на вопрос
     «сколько это ещё будет идти» — без неё панель читается как бесконечная
     карусель, и человек уходит раньше самого интересного кадра. */
  const segments = rail ? Array.from({ length: 6 }, () => {
    const seg = node("i");
    rail.appendChild(seg);
    return seg;
  }) : [];

  const paint = () => {
    if (phaseLabel) {
      phaseLabel.textContent = phase === 0
        ? "СЛЕДУЮЩАЯ ЗАЯВКА"
        : `${phase}/6 · ${HERO_STEPS[phase]}`;
    }
    segments.forEach((seg, i) => {
      seg.classList.toggle("is-on", phase > i + 1);
      seg.classList.toggle("is-current", phase === i + 1);
    });
  };

  /* БЕЗ ДВИЖЕНИЯ — СРАЗУ ФИНАЛ, А НЕ ПУСТАЯ ПАНЕЛЬ. Человек, который попросил
     систему не двигать картинку, просил об этом, а не о том, чтобы остаться без
     содержимого. */
  if (reduceMotion) {
    heroApply(parts, phase);
    paint();
    return;
  }
  /* Класс, включающий переход, нельзя ставить в том же тике, где узел только
     что вставлен в DOM: браузер ещё не отрисовал скрытое начальное состояние
     (opacity:0) и просто перескочит к финалу без анимации. Два кадра растра
     дают ему этот кадр. */
  requestAnimationFrame(() => requestAnimationFrame(() => { heroApply(parts, phase); paint(); }));

  const schedule = (ms) => { clearTimeout(timer); timer = setTimeout(step, ms); };

  function step() {
    if (paused) return;
    /* СМЕНА ТЕМЫ ЗАБИРАЕТ СЦЕНУ СЕБЕ. Пока идёт маска, реплики не меняются:
       две анимации в одном кадре — это и есть та дёрганность, которую видно
       «через раз». Просто ждём и возвращаемся, ничего не пропуская. */
    if (document.documentElement.dataset.themeBusy) {
      schedule(220);
      return;
    }
    phase = (phase + 1) % 7;
    if (phase === 0) {
      /* Расходимся: сначала гасим реплики, ждём затухание и только потом меняем
         пример — иначе узлы исчезают вместе со сменой разметки, минуя переход, и
         смена заявки выглядит рывком, а не затуханием. */
      heroApply(parts, phase);
      paint();
      setTimeout(() => {
        index = (index + 1) % HERO_CASES.length;
        parts = heroBuild(index);
        stage.replaceChildren(parts.dialog);
        phase = 1;
        requestAnimationFrame(() => requestAnimationFrame(() => {
          heroApply(parts, phase);
          paint();
        }));
        schedule(HERO_DWELL[1]);
      }, 750);
      return;
    }
    heroApply(parts, phase);
    paint();
    schedule(HERO_DWELL[phase] || 1700);
  }

  /* НАВЕДЕНИЕ ОСТАНАВЛИВАЕТ ПОКАЗ. Панель — не баннер, её читают: тот, кто вёл
     курсором к строке с подменой, не должен ловить её уже подменённой обратно.
     Ушли — показ продолжается сам. */
  if (panel) {
    panel.addEventListener("mouseenter", () => { paused = true; clearTimeout(timer); });
    panel.addEventListener("mouseleave", () => { if (paused) { paused = false; schedule(500); } });
  }

  /* ШАГ НАЗАД И ВПЕРЁД. Показ идёт сам, но панель не телевизор: тот, кто хочет
     разглядеть кадр — или показать его коллеге, — должен мочь к нему вернуться.
     Переход через край идёт в соседнюю заявку (назад с первого шага — финал
     предыдущей), иначе стрелка упиралась бы в невидимую стену. После ручного
     шага показ сам не возобновляется сразу: шесть секунд панель стоит, чтобы
     её успели прочитать, и только потом едет дальше. */
  const controls = Array.from(document.querySelectorAll("[data-hero-step]"));
  const go = (delta) => {
    clearTimeout(timer);
    clearTimeout(idle);
    paused = true;
    let next = phase + delta;
    let rebuilt = false;
    if (next < 1) {
      index = (index - 1 + HERO_CASES.length) % HERO_CASES.length;
      next = 6;
      rebuilt = true;
    } else if (next > 6) {
      index = (index + 1) % HERO_CASES.length;
      next = 1;
      rebuilt = true;
    }
    phase = next;
    if (rebuilt) {
      parts = heroBuild(index);
      stage.replaceChildren(parts.dialog);
      requestAnimationFrame(() => requestAnimationFrame(() => { heroApply(parts, phase); paint(); }));
    } else {
      heroApply(parts, phase);
      paint();
    }
    idle = setTimeout(() => { paused = false; schedule(HERO_DWELL[phase] || 1700); }, 6000);
  };
  controls.forEach((button) => button.addEventListener("click", () => go(Number(button.dataset.heroStep))));

  schedule(HERO_DWELL[phase]);
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
 * КАСКАДНОЕ ПОЯВЛЕНИЕ КАРТОЧЕК
 *
 * Обычный `[data-reveal]` поднимает блок ЦЕЛИКОМ. Для сеток это скучно: шесть
 * карточек появляются одним клином. Здесь появляются ПО ОДНОЙ, с нарастающей
 * задержкой 70 мс (до 420 мс), — страница читается как очередь, а не как плитка.
 * ──────────────────────────────────────────────────────────────────────────── */
const staggerGroups = Array.from(document.querySelectorAll("[data-reveal-stagger]"));
if (!("IntersectionObserver" in window)) {
  staggerGroups.forEach((group) =>
    Array.from(group.children).forEach((child) => child.classList.add("is-in")));
} else {
  const st = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      Array.from(entry.target.children).forEach((child) => child.classList.add("is-in"));
      st.unobserve(entry.target);
    });
  }, { rootMargin: "-40px 0px -8% 0px" });
  staggerGroups.forEach((group) => {
    Array.from(group.children).forEach((child, i) => {
      child.classList.add("reveal-item");
      child.style.transitionDelay = `${Math.min(i * 70, 420)}ms`;
    });
    st.observe(group);
  });
}

/* ────────────────────────────────────────────────────────────────────────────
 * СВОП ПО СКРОЛЛУ
 *
 * Разметка та же, что у hero-token (настоящее поверх подмены в одной ячейке),
 * но узел стоит прямо в шаблоне и помечен `data-swap`. Когда он попадает в кадр,
 * сначала подсвечивается (нашёл), затем значение перетекает в подмену (подменил).
 * ──────────────────────────────────────────────────────────────────────────── */
const swapables = Array.from(document.querySelectorAll("[data-swap]"));
if (!("IntersectionObserver" in window)) {
  swapables.forEach((el) => el.classList.add("is-found", "is-swapped"));
} else {
  const so = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-found");
      setTimeout(() => entry.target.classList.add("is-swapped"), 280);
      so.unobserve(entry.target);
    });
  }, { threshold: 0.65 });
  swapables.forEach((el) => so.observe(el));
}

/* ────────────────────────────────────────────────────────────────────────────
 * ЛЁГКИЙ ПАРАЛЛАКС
 *
 * Панель едет навстречу скроллу на ±16 px. Только translateY, только когда
 * элемент в кадре, с rAF-троттлингом; при reduced-motion не подключается вовсе.
 * ──────────────────────────────────────────────────────────────────────────── */
const parallaxEls = Array.from(document.querySelectorAll("[data-parallax]"));
if (parallaxEls.length && !reduceMotion && "IntersectionObserver" in window) {
  let ticking = false;
  const drift = () => {
    parallaxEls.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight) return;
      const center = r.top + r.height / 2 - window.innerHeight / 2;
      const shift = Math.max(-1, Math.min(1, center / window.innerHeight)) * 16;
      el.style.transform = `translateY(${shift.toFixed(1)}px)`;
    });
    ticking = false;
  };
  window.addEventListener("scroll", () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(drift);
  }, { passive: true });
  drift();
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
  button.addEventListener("click", async () => {
    // Preserve the existing nearest-scope source lookup, including private
    // cabinet/welcome copies; only the explicitly public prompt can emit a goal.
    const scope = button.closest("[data-copy-scope]") || button.parentElement;
    const source = scope.querySelector("[data-copy]");
    if (!source || button.disabled) return;
    let consentAtClick = false;
    try { consentAtClick = localStorage.getItem("pseudex.analytics.consent") === "yes"; } catch {}
    const was = button.textContent;
    button.disabled = true;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(source.dataset.copy);
      button.textContent = "СКОПИРОВАНО";
      // Never emit the copied text or buffer a pre-consent action, even if the
      // clipboard promise resolves after the visitor subsequently accepts.
      if (consentAtClick && source.matches('#start [data-integration-copy="agent_prompt"]')) {
        source.dispatchEvent(new Event("pseudex:integration-copy", { bubbles: true }));
      }
    } catch {
      button.textContent = "НЕ СКОПИРОВАЛОСЬ";
    } finally {
      setTimeout(() => { button.textContent = was; button.disabled = false; }, 1500);
    }
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
/* КНОПКА И ПОДПИСЬ ГОВОРЯТ ТО, ЧТО СЛУЧИТСЯ. Бесплатный тариф — «получить
   ключ», платный — «зарегистрироваться и оплатить»: ключ на платном выпускается
   после денег, и обещать его кнопкой значило бы обещать то, чего форма не
   делает. Без JS остаётся бесплатная подпись — она же выбрана по умолчанию. */
/* ВЫБОР ТАРИФА — РАДИОКНОПКИ В НАШЕМ СПИСКЕ, А НЕ СИСТЕМНЫЙ `<select>`.
   Скрытый `<option data-paid>` держал признак «платный», и на нём висела
   подпись кнопки; теперь тот же признак лежит на радиокнопке, а сводку списка
   рисует общий код `.planpick` ниже. Без JS форма отправляет выбранное радио и
   обе подписи остаются неверными только в одном направлении — как и раньше. */
const signupPlanRadios = document.querySelectorAll('#signup-form input[name="plan"]');
function reflectSignupPlan() {
  const radio = document.querySelector('#signup-form input[name="plan"]:checked');
  if (!radio) return;
  const paid = radio.dataset.paid === "1";
  const button = document.querySelector('#signup-form button[type="submit"]');
  if (button) button.textContent = paid ? button.dataset.labelPaid : button.dataset.labelFree;
  document.querySelectorAll('#signup-form [data-when]').forEach((note) => {
    note.hidden = (note.dataset.when === "paid") !== paid;
  });
}
signupPlanRadios.forEach((radio) => radio.addEventListener("change", reflectSignupPlan));
if (signupPlanRadios.length) reflectSignupPlan();

/* ОБЩИЙ СПИСОК `.planpick` — НА ОБЕИХ СТРАНИЦАХ. Живёт здесь, а не в шаблонах:
   кабинет и лендинг грузят этот файл, и вторая копия разъехалась бы с первой.
   Без JS ничего не ломается — список раскрывается силами <details>. */
document.querySelectorAll('.planpick').forEach((box) => {
  const name = box.querySelector('.pp-name'), meta = box.querySelector('.pp-meta');
  box.querySelectorAll('input[type=radio]').forEach((radio) => {
    radio.addEventListener('change', () => {
      const item = radio.closest('.pp-item');
      box.querySelectorAll('.pp-item').forEach((i) => i.classList.toggle('on', i === item));
      if (name) name.textContent = item.dataset.name;
      if (meta) meta.textContent = item.dataset.meta;
      box.open = false;
    });
  });
});
document.addEventListener('click', (event) => {
  document.querySelectorAll('.planpick[open]').forEach((box) => {
    if (!box.contains(event.target)) box.open = false;
  });
});

document.querySelectorAll("[data-plan]").forEach((link) => {
  link.addEventListener("click", () => {
    const radio = document.querySelector(`#signup-form input[name="plan"][value="${link.dataset.plan}"]`);
    if (radio) { radio.checked = true; radio.dispatchEvent(new Event("change")); }
    reflectSignupPlan();
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


/* ────────────────────────────────────────────────────────────────────────────
 * МОБИЛЬНАЯ РЕДАКЦИЯ: ЧТО НА ТЕЛЕФОНЕ СВЁРНУТО, А ЧТО ОСТАВЛЕНО РАЗВЁРНУТЫМ
 *
 * ЗАЧЕМ ЭТО, А НЕ ОЧЕРЕДНОЕ СУЖЕНИЕ ПОЛЕЙ. Замерено на 390 px: страница целиком
 * — 15 113 px, 17.9 экранов, и она весит не шрифтами, а ОБЪЁМОМ: запись экрана
 * на четыре минуты, шесть метрик, шестнадцать ячеек покрытия, раздел 152-ФЗ,
 * база знаний, FAQ и пошаговое подключение. На большом экране это архив, по
 * которому ходят глазами; на телефоне это ровно то, что читатель называет
 * «перегружено» — потому что путь к кнопке «начать» длиной в восемнадцать
 * экранов, и на каждом что-то есть.
 *
 * ЧТО ОСТАЁТСЯ РАЗВЁРНУТЫМ: первый экран с демонстрацией подмены, доказательство
 * («99,7%»), ядро покрытия, цены и форма. Всё остальное — под свёрткой с
 * внятным заголовком: содержание на месте, но его ВИДНО, только если оно нужно.
 *
 * ПОЧЕМУ ЭТО НЕ ЛОМАЕТ ДЕСКТОП И НЕ ЛОМАЕТ ПОИСК: свёртка строится скриптом и
 * только при `max-width: 760px`, поэтому на большом экране в разметке не
 * появляется ни одного `<details>`, а в HTML для робота контент лежит в
 * исходном виде — он никуда не девается и при свёртке, `<details>` не скрывает
 * содержимое от индексации.
 *
 * ПОЧЕМУ НЕ В РАЗМЕТКЕ: восемь свёрток руками — это восемь копий одного решения
 * в шаблоне, и первая же правка секции разойдётся с ними. Здесь список один.
 */
const mobileFoldQuery = window.matchMedia("(max-width: 760px)");

/* `move: true` — свёртка ОБОРАЧИВАЕТ сам узел (сетка покрытия, сетка метрик):
   оставить её внутри сетки значило бы сломать сетку. `move: false` — свёртка
   встаёт ВНУТРЬ секции на месте её содержимого, поэтому заголовок раздела
   остаётся на виду и ведёт к содержимому. */
const mobileFolds = [
  { sel: "#top .cards--n6", title: "Цифры", move: true },
  { sel: "#coverage .cards", title: "Все отрасли списком", move: true },
  { sel: "#video", title: "Запись экрана, 4 минуты", move: false },
  { sel: "#how", title: "Как это работает", move: false },
  { sel: "#setup", title: "Подключение, шаг за шагом", move: false },
  { sel: "#legal", title: "152-ФЗ", move: false },
  { sel: "#znaniya", title: "База знаний", move: false },
  { sel: "#faq", title: "Вопросы", move: false }
];

const builtFolds = [];

function buildFolds() {
  for (const { sel, title, move } of mobileFolds) {
    const host = document.querySelector(sel);
    if (!host || host.closest(".m-fold")) continue;
    const box = document.createElement("details");
    box.className = "m-fold";
    const sum = document.createElement("summary");
    sum.textContent = title;
    box.appendChild(sum);
    if (move) {
      host.parentNode.insertBefore(box, host);
      box.appendChild(host);
    } else {
      while (host.firstChild) box.appendChild(host.firstChild);
      host.appendChild(box);
    }
    /* РАСКРЫТИЕ ОБЯЗАНО ПОКАЗАТЬ СОДЕРЖИМОЕ, А НЕ ПУСТОЕ МЕСТО. Блоки внутри
       закрытой свёртки не попадали в кадр, поэтому `IntersectionObserver` не
       ставил им `is-in` — и человек, раскрыв «Все отрасли списком», видел
       свёртку и ничего под ней (замерено: `opacity: 0` у содержимого двух
       свёрток из трёх). Здесь появление ставится явно, при раскрытии: это тот
       же класс, что ставит наблюдатель, и задержки каскада сохраняются. */
    box.addEventListener("toggle", () => {
      if (!box.open) return;
      box.querySelectorAll("[data-reveal]").forEach((el) => el.classList.add("is-in"));
      box.querySelectorAll("[data-reveal-stagger]").forEach((group) =>
        Array.from(group.children).forEach((child) => child.classList.add("is-in")));
    });
    builtFolds.push({ host, box, move });
  }
}

/* РАЗВОРАЧИВАНИЕ ОБРАТНО, ЕСЛИ ЭКРАН СТАЛ ШИРОКИМ. Планшет, повёрнутый в
   альбомную, — тот же документ, и оставлять в нём свёртки от узкого вида значит
   показать большому экрану телефонную редакцию. Узлы возвращаются на свои
   места, `<details>` исчезает: разметка приходит в исходный вид. */
function dropFolds() {
  while (builtFolds.length) {
    const { host, box, move } = builtFolds.pop();
    if (move) {
      box.parentNode.insertBefore(host, box);
      box.remove();
    } else {
      const parent = box.parentNode;
      while (box.firstChild) {
        const child = box.firstChild;
        box.removeChild(child);
        if (child.nodeName !== "SUMMARY") parent.appendChild(child);
      }
      box.remove();
    }
  }
}

function syncFolds() {
  if (mobileFoldQuery.matches) {
    if (!builtFolds.length) buildFolds();
  } else if (builtFolds.length) {
    dropFolds();
  }
}

syncFolds();
mobileFoldQuery.addEventListener("change", syncFolds);
