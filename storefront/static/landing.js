/* The landing's two interactions: copy buttons and the demo tabs.
 *
 * The demo examples are BUILT INTO THIS FILE and there is no input anywhere on
 * the page. That is the point rather than a simplification: an input here would
 * mean this server starts receiving other people's personal data, which is the
 * exact thing the product sells not doing. Anyone who wants to try their own
 * text does it in the local interface, inside their own contour.
 *
 * Rendered with DOM nodes, never innerHTML — the strings below are ours today,
 * and a page that builds markup from data is one refactor away from being fed
 * something that isn't.
 */
const DEMOS = [
  {
    orig: [["Здравствуйте! Меня зовут "], ["Иванов Пётр Сергеевич", "pii"], [", заказ №A-4471.\nПерезвоните на "], ["+7 916 214-88-03", "pii"], [", доставку жду по адресу\n"], ["Москва, Ленинский пр-т 42, кв. 118", "pii"], ["."]],
    masked: [["Здравствуйте! Меня зовут "], ["Соколов Игорь Валентинович", "fake"], [", заказ №A-4471.\nПерезвоните на "], ["+7 903 557-19-42", "fake"], [", доставку жду по адресу\n"], ["Москва, Ломоносовский пр-т 17, кв. 64", "fake"], ["."]],
  },
  {
    orig: [['{\n  "order": "A-4471",\n  "customer": "'], ["Иванова Мария Львовна", "pii"], ['",\n  "phone": "'], ["+79162148803", "pii"], ['",\n  "email": "'], ["m.ivanova@acme.ru", "pii"], ['",\n  "total": 12400\n}']],
    masked: [['{\n  "order": "A-4471",\n  "customer": "'], ["Ерёмина Ольга Тимуровна", "fake"], ['",\n  "phone": "'], ["+79035571942", "fake"], ['",\n  "email": "'], ["o.eremina@acme.ru", "fake"], ['",\n  "total": 12400\n}']],
  },
  {
    orig: [["Курьер не нашёл вход. Адрес: "], ["г. Казань, ул. Профсоюзная, д. 17, под. 3, кв. 84", "pii"], [",\nдомофон 84К. Подъезд со стороны "], ["Петербургской", "pii"], ["."]],
    masked: [["Курьер не нашёл вход. Адрес: "], ["г. Казань, ул. Достоевского, д. 41, под. 2, кв. 57", "fake"], [",\nдомофон 57К. Подъезд со стороны "], ["Чистопольской", "fake"], ["."]],
  },
  {
    orig: [["Для оформления: паспорт "], ["4517 № 812345", "pii"], [", СНИЛС "], ["112-233-445 95", "pii"], [",\nИНН "], ["770512345678", "pii"], [". Номер договора 2024/117 — не персональные, остаётся как есть."]],
    masked: [["Для оформления: паспорт "], ["4509 № 337201", "fake"], [", СНИЛС "], ["284-119-703 41", "fake"], [",\nИНН "], ["771903845206", "fake"], [". Номер договора 2024/117 — не персональные, остаётся как есть."]],
  },
];

function paint(target, chunks) {
  target.replaceChildren(...chunks.map(([text, kind]) => {
    const span = document.createElement("span");
    if (kind) span.className = kind === "pii" ? "mark-pii" : "mark-fake";
    span.textContent = text;
    return span;
  }));
}

function showDemo(index) {
  paint(document.getElementById("demo-orig"), DEMOS[index].orig);
  paint(document.getElementById("demo-masked"), DEMOS[index].masked);
  document.querySelectorAll("[data-demo]").forEach((button) => {
    button.setAttribute("aria-selected", String(Number(button.dataset.demo) === index));
  });
}

document.querySelectorAll("[data-demo]").forEach((button) => {
  button.addEventListener("click", () => showDemo(Number(button.dataset.demo)));
});
if (document.getElementById("demo-orig")) showDemo(0);

document.querySelectorAll("[data-copy-btn]").forEach((button) => {
  button.addEventListener("click", () => {
    const source = button.parentElement.querySelector("[data-copy]");
    if (!source) return;
    navigator.clipboard?.writeText(source.dataset.copy);
    const was = button.textContent;
    button.textContent = "СКОПИРОВАНО";
    setTimeout(() => { button.textContent = was; }, 1500);
  });
});
