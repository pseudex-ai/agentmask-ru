/* Тема страницы.
 *
 * ЖИВЁТ НА <html data-theme> И ЧИТАЕТСЯ ДО ПЕРВОЙ ОТРИСОВКИ. Скрипт подключён в
 * <head> блокирующим тегом именно поэтому: если поставить тему после загрузки,
 * страница успеет мигнуть чужой темой — сначала светлой, потом тёмной. Мигание
 * в первый экран — это то, из-за чего переключатель темы перестают включать.
 *
 * ПОЧЕМУ ОТДЕЛЬНЫЙ ФАЙЛ, А НЕ В landing.js. Шапка общая для всего сайта, а
 * landing.js подключён только к маркетинговым страницам. Тема, работающая на
 * лендинге и не работающая в кабинете, — это не половина функции, а баг.
 *
 * ПЕРЕКЛЮЧЕНИЕ — МАСКА, ИСХОДЯЩАЯ ОТ КНОПКИ, и это не украшение: продукт
 * маскирует значения и меняет их на другие, поэтому смена темы устроена так же.
 *
 * ДВЕ ВЕЩИ, КОТОРЫЕ ЗДЕСЬ ЛЕГКО ИСПОРТИТЬ, И ОБЕ УЖЕ БЫЛИ ИСПОРЧЕНЫ:
 *
 * 1. ТОЧКА ОДНА. Центр маски сначала гулял на ±14 px, и свет выходил из разных
 *    мест кнопки — это читается не как приём, а как небрежность. Случайность
 *    здесь ничего не покупала, поэтому её нет.
 * 2. КРУГ НАЧИНАЕТСЯ СНАРУЖИ КНОПКИ. Радиус старта — описанный вокруг неё круг,
 *    так кнопка целиком получает новый цвет первой, и только потом свет идёт
 *    наружу. Круг меньше кнопки давал обратное: новую тему, проступающую ВНУТРИ
 *    кнопки, будто её подтачивают.
 *
 * Направление тоже значимо: к светлому свет расходится ОТ кнопки, к тёмному —
 * сходится К ней и гаснет на самой кнопке. Подробности у самой анимации.
 */
(function () {
  "use strict";

  const KEY = "pseudex-theme";
  const root = document.documentElement;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const read = () => {
    try { return localStorage.getItem(KEY); } catch (error) { return null; }
  };
  const write = (value) => {
    try { localStorage.setItem(KEY, value); } catch (error) { /* приватный режим */ }
  };

  const stored = read();
  /* ТЁМНАЯ ПО УМОЛЧАНИЮ, И ЭТО РЕШЕНИЕ, А НЕ ЛЕНЬ. Фирменная палитра — ночная,
     весь макет и демо героя нарисованы для неё; светлая — осознанная опция для
     тех, кому так удобнее (и для документов). Отдать выбор системе значило бы
     показать большинству посетителей не тот продукт, который мы рисовали, — и
     сделать это молча, на первом экране. */
  const initial = stored === "light" || stored === "dark" ? stored : "dark";
  root.dataset.theme = initial;

  /* ПОДПИСЬ ГОВОРИТ, ЧТО БУДЕТ, А НЕ ЧТО ЕСТЬ. Кнопка «СВЕТ» в тёмной теме
     означает «нажми — станет светло»; кнопка, называющая текущее состояние,
     заставляет человека решать задачу вместо того, чтобы просто нажать. */
  const label = (theme) => (theme === "light" ? "ТЬМА" : "СВЕТ");
  const hint = (theme) => (theme === "light" ? "Включить тёмную тему" : "Включить светлую тему");

  const wire = () => {
    const button = document.querySelector("[data-theme-toggle]");
    if (!button) return;
    button.textContent = label(root.dataset.theme);
    button.setAttribute("aria-label", hint(root.dataset.theme));

    /* КНОПКА ПОКАЗЫВАЕТ ЦЕЛЕВУЮ ТЕМУ, А НЕ ТЕКУЩУЮ. Тот же атрибут `data-theme`
       на самой кнопке — и её цвет резолвится в палитру той темы, в которую мы
       переключимся (см. `.theme-toggle` в site.css). Ставится на наведение и
       снимается на уход; с клавиатуры — на фокус. */
    const target = (theme) => (theme === "light" ? "dark" : "light");
    const showTarget = (on) => {
      if (on) button.dataset.theme = target(root.dataset.theme);
      else delete button.dataset.theme;
    };
    button.addEventListener("mouseenter", () => showTarget(true));
    button.addEventListener("mouseleave", () => showTarget(false));
    button.addEventListener("focus", () => showTarget(true));
    button.addEventListener("blur", () => showTarget(false));

    button.addEventListener("click", (event) => {
      const next = root.dataset.theme === "light" ? "dark" : "light";
      const apply = () => {
        root.dataset.theme = next;
        write(next);
      };
      button.textContent = label(next);
      button.setAttribute("aria-label", hint(next));

      if (!document.startViewTransition || reduceMotion) {
        apply();
        return;
      }
      const box = event.currentTarget.getBoundingClientRect();
      /* ТОЧКА ОДНА — ЦЕНТР КНОПКИ, БЕЗ ДРОЖИ. Раньше центр гулял на ±14 px, и
         маска выходила из РАЗНЫХ МЕСТ кнопки: это читалось не как приём, а как
         неаккуратность. Случайность здесь ничего не покупала. */
      const x = box.left + box.width / 2;
      const y = box.top + box.height / 2;
      const radius = Math.hypot(
        Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));

      /* КРУГ НАЧИНАЕТСЯ СНАРУЖИ КНОПКИ, А НЕ ВНУТРИ НЕЁ. Радиус старта — до
         самого дальнего угла кнопки: тогда кнопка ЦЕЛИКОМ попадает внутрь круга
         с первого кадра, то есть первой получает новый цвет, и только потом
         свет идёт наружу, на остальную страницу. Круг меньше кнопки давал бы
         обратное — новую тему, проступающую внутри кнопки, — и это выглядело
         так, будто кнопку подтачивают изнутри. */
      const buttonRadius = Math.hypot(box.width / 2, box.height / 2) + 2;

      /* ФОРМА КНОПКИ И ФОРМА КРУГА — ОБЕ ПОЛИГОНАМИ, И ЭТО НЕ КАПРИЗ.
         Круг и прямоугольник в `clip-path` не интерполируются между собой:
         разные функции формы дают дискретный переход, то есть рывок. Полигон
         же морфится в полигон, если у них ОДНО ЧИСЛО ТОЧЕК и точки стоят в
         одном порядке. Поэтому круг мы тоже задаём многоугольником: 48 вершин
         на радиусе 1500 px дают отклонение хорды от дуги в 3 px — на глаз это
         круг. Точки берём под одним и тем же углом, тогда морф идёт «по
         радиусу»: круг плавно подбирает углы и становится прямоугольником. */
      const SHAPE_POINTS = 48;
      const poly = (points) => `polygon(${points})`;
      const circleShape = (cx, cy, r) => {
        const pts = [];
        for (let i = 0; i < SHAPE_POINTS; i += 1) {
          const a = (2 * Math.PI * i) / SHAPE_POINTS;
          pts.push(`${(cx + r * Math.cos(a)).toFixed(1)}px ${(cy + r * Math.sin(a)).toFixed(1)}px`);
        }
        return poly(pts.join(","));
      };
      /* Точка прямоугольника под тем же углом: пересечение луча с его границей. */
      const boxShape = (cx, cy, halfW, halfH) => {
        const pts = [];
        for (let i = 0; i < SHAPE_POINTS; i += 1) {
          const a = (2 * Math.PI * i) / SHAPE_POINTS;
          const cos = Math.cos(a), sin = Math.sin(a);
          const t = Math.min(
            cos === 0 ? Infinity : halfW / Math.abs(cos),
            sin === 0 ? Infinity : halfH / Math.abs(sin));
          pts.push(`${(cx + t * cos).toFixed(1)}px ${(cy + t * sin).toFixed(1)}px`);
        }
        return poly(pts.join(","));
      };
      const cx = box.left + box.width / 2;
      const cy = box.top + box.height / 2;
      const buttonShape = boxShape(cx, cy, box.width / 2 + 1, box.height / 2 + 1);
      /* МЕДЛЕННЕЕ И ПЛАВНЕЕ. Прежняя кривая (.22,.61,.24,1) — это ease-out: она
         выстреливала радиусом в первые 200 мс, и глаз читал это как рывок, а не
         как раскрытие. Замер новой кривой: 10% времени — 1% радиуса, четверть —
         9%, половина — 69%, 90% — 99%. То есть маска разворачивается, а не
         щёлкает. Длина 1350–1600 мс вместо 900. */
      const duration = 1350 + Math.round(Math.random() * 250);

      /* СЦЕНА ГЕРОЯ ТОЖЕ ВСТАЁТ. Пока идёт маска, реплики героя продолжают
         меняться (у каждой свой CSS-переход), и два потока перерисовки делят
         кадр. Пауза на время перехода — это ровно то, что видно как «дёргается
         через раз». */
      /* КООРДИНАТЫ МАСКИ СТАВЯТСЯ ДО ЗАПУСКА ПЕРЕХОДА. Начальный клип объявлен в
         CSS (`site.css`, `::view-transition-new(root)`) и берёт их отсюда.
         Без этого новая тема успевала мелькнуть во весь экран, пока браузер
         снимает снимки, — то самое мигание ПЕРЕД анимацией: клип появлялся
         вместе с движением, то есть на ~100 мс позже, чем был нужен. */
      root.style.setProperty("--theme-x", `${x}px`);
      root.style.setProperty("--theme-y", `${y}px`);
      root.style.setProperty("--theme-r", `${radius}px`);
      root.style.setProperty("--theme-r0", `${buttonRadius}px`);
      /* Тот же прямоугольник кладём в переменную: начальный клип объявлен в CSS,
         и он обязан совпадать с первым кадром анимации, иначе на стыке «до
         анимации / в анимации» будет видно подмену формы. */
      root.style.setProperty("--theme-shape-start", buttonShape);

      /* К СВЕТЛОМУ — РАСХОДИТСЯ, К ТЁМНОМУ — СХОДИТСЯ. Свет наступает от
         кнопки; тьма приходит тем, что свет уходит в неё обратно, как гаснущая
         лампа. Роль снимка от этого меняется: в обратную сторону сворачивается
         СТАРАЯ тема (светлая), а новая (тёмная) просто ждёт под ней. Направление
         ставится ДО перехода — по той же причине, что и координаты: CSS по нему
         выбирает, какой снимок сверху и с какого клипа начинать.

      */
      /* ДО ЗАПУСКА ПЕРЕХОДА КНОПКА УЖЕ ЦВЕТА ЦЕЛЕВОЙ ТЕМЫ. Снимок «до» берётся
         в момент `startViewTransition`, поэтому перекраска кнопки попадает в
         него — и она меняет цвет МГНОВЕННО, вместе с нажатием, а круг лишь
         продолжает то, что уже началось. Иначе выходило наоборот: сначала
         ~100 мс ничего, потом появлялся круг, и только потом кнопка светлела.
         С клавиатуры наведения нет, поэтому ставим здесь явно. */
      showTarget(true);

      const toDark = next === "dark";
      if (toDark) {
        root.dataset.themeDirection = "to-dark";
      } else {
        delete root.dataset.themeDirection;
      }

      root.dataset.themeBusy = "1";
      const transition = document.startViewTransition(apply);
      /* К СВЕТЛОМУ: свет ВЫХОДИТ из прямоугольника кнопки и, разворачиваясь,
         становится кругом — то есть форма идёт от предмета, а не от абстракции.
         К ТЁМНОМУ: круг сжимается до круга вокруг кнопки, затем ПРИНИМАЕТ ЕЁ
         ФОРМУ и лишь потом гаснет. Раньше он просто исчезал кругом — резко;
         теперь последние 7% времени свет растворяется уже прямоугольником
         кнопки, поэтому «уход» читается как растворение, а не как обрыв. */
      const keyframes = toDark
        ? {
            clipPath: [circleShape(cx, cy, radius), circleShape(cx, cy, buttonRadius),
                       buttonShape, buttonShape],
            opacity: [1, 1, 1, 0],
            offset: [0, 0.72, 0.93, 1],
            easing: ["cubic-bezier(.5,0,.3,1)", "cubic-bezier(.5,0,.4,1)",
                     "cubic-bezier(.4,0,.6,1)"],
          }
        : {
            clipPath: [buttonShape, circleShape(cx, cy, radius)],
            offset: [0, 1],
            easing: ["cubic-bezier(.5,0,.3,1)"],
          };
      const target = toDark ? "::view-transition-old(root)" : "::view-transition-new(root)";
      transition.ready.then(() => root.animate(
        keyframes,
        {
          duration,
          /* `forwards` — не мелочь: без него после анимации снова действовал бы
             клип из CSS (нулевой радиус) и новая тема исчезла бы в конце. */
          fill: "forwards",
          pseudoElement: target,
        }).finished).catch(() => { /* браузер не дал анимировать — тема применена */
      }).finally(() => { delete root.dataset.themeBusy; });
      /* Направление снимается только когда переход завершён целиком: пока жив
         хотя бы один снимок, CSS обязан знать, какой из них сверху. */
      transition.finished.catch(() => {}).finally(() => {
        delete root.dataset.themeDirection;
        /* Если курсор всё ещё на кнопке, атрибут оставляем: снять его значило бы
           мигнуть кнопкой в момент, когда человек её не двигал. Он обновится на
           следующем наведении. */
        if (!button.matches(":hover") && document.activeElement !== button) showTarget(false);
      });
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
