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


/* The setup tutorial: pick a provider, get commands that are ready to paste.
 *
 * Built from data rather than written out six times, because the variants
 * differ in exactly one string — and a page where five of six code blocks are
 * copies is a page where five of them go stale.
 *
 * Two groups, and the split is honest rather than cosmetic. A provider is
 * "direct" only if it speaks the OpenAI REQUEST shape, because that is the
 * shape we parse to find what to mask. Anthropic and Gemini put the user's
 * text somewhere else entirely; GigaChat looks OpenAI-shaped but authenticates
 * through a two-hop OAuth exchange against a different host; YandexGPT uses
 * `messages[].text` instead of `content`. Listing any of those as "just change
 * the URL" would be a lie the customer discovers at integration time, which is
 * the worst possible moment to discover it.
 */
const PROVIDERS = [
  { label: "OPENROUTER", upstream: "https://openrouter.ai/api/v1", key: "sk-or-v1-\u2026", direct: true },
  { label: "OPENAI", upstream: "https://api.openai.com/v1", key: "sk-proj-\u2026", direct: true },
  { label: "DEEPSEEK", upstream: "https://api.deepseek.com/v1", key: "sk-\u2026", direct: true },
  { label: "\u0421\u0412\u041e\u0419 VLLM", upstream: "http://vllm:8000/v1", key: "\u043b\u044e\u0431\u043e\u0439", direct: true },
  { label: "\u0414\u0420\u0423\u0413\u041e\u0419 OPENAI-\u0421\u041e\u0412\u041c\u0415\u0421\u0422\u0418\u041c\u042b\u0419", upstream: "https://\u0432\u0430\u0448-\u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440/v1", key: "\u0432\u0430\u0448 \u043a\u043b\u044e\u0447", direct: true },
  { label: "ANTHROPIC \u00b7 GEMINI \u00b7 GIGACHAT \u00b7 YANDEXGPT", direct: false },
];

const NOTES = {
  direct: "\u041a\u043b\u044e\u0447 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u0430 \u043e\u0441\u0442\u0430\u0451\u0442\u0441\u044f \u0432\u0430\u0448\u0438\u043c \u2014 \u043e\u043d \u0438\u0434\u0451\u0442 \u0432 \u0437\u0430\u0433\u043e\u043b\u043e\u0432\u043a\u0435 \u0437\u0430\u043f\u0440\u043e\u0441\u0430 \u0438 \u043f\u0435\u0440\u0435\u0441\u044b\u043b\u0430\u0435\u0442\u0441\u044f \u043d\u0430\u0432\u0435\u0440\u0445 \u043d\u0435\u0442\u0440\u043e\u043d\u0443\u0442\u044b\u043c. \u041c\u044b \u0435\u0433\u043e \u043d\u0435 \u0445\u0440\u0430\u043d\u0438\u043c \u0438 \u043d\u0435 \u0432\u044b\u0434\u0430\u0451\u043c \u0441\u0432\u043e\u0439.",
  litellm: "\u0423 \u044d\u0442\u0438\u0445 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u043e\u0432 \u0434\u0440\u0443\u0433\u043e\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u0437\u0430\u043f\u0440\u043e\u0441\u0430: \u0442\u0435\u043a\u0441\u0442 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u043b\u0435\u0436\u0438\u0442 \u043d\u0435 \u0442\u0430\u043c, \u0433\u0434\u0435 \u0443 OpenAI, \u0430 GigaChat \u0435\u0449\u0451 \u0438 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0443\u0435\u0442\u0441\u044f \u0432 \u0434\u0432\u0430 \u0448\u0430\u0433\u0430. \u0421\u0442\u0430\u0432\u0438\u0442\u0441\u044f LiteLLM, \u043a\u043e\u0442\u043e\u0440\u044b\u0439 \u043f\u0440\u0438\u0432\u043e\u0434\u0438\u0442 \u0438\u0445 \u043a \u043e\u0431\u0449\u0435\u043c\u0443 \u0432\u0438\u0434\u0443, \u0430 pseudex \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0430\u0435\u0442\u0441\u044f \u043a \u043d\u0435\u043c\u0443 \u0441\u0430\u0439\u0434\u043a\u0430\u0440\u043e\u043c \u2014 \u0442\u043e\u0433\u0434\u0430 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u044b \u043b\u044e\u0431\u044b\u0435.",
};

function setBlock(id, text) {
  const node = document.getElementById(id);
  if (!node) return;
  node.textContent = text;
  node.dataset.copy = text;
}

function showProvider(index) {
  const p = PROVIDERS[index];
  const image = document.getElementById("setup").dataset.image;
  document.getElementById("provider-note").textContent = p.direct ? NOTES.direct : NOTES.litellm;
  document.querySelectorAll("[data-provider]").forEach((button) => {
    button.setAttribute("aria-selected", String(Number(button.dataset.provider) === index));
  });

  const T = {
    up: "\u041f\u043e\u0434\u043d\u044f\u0442\u044c \u043a\u043e\u043d\u0442\u0435\u0439\u043d\u0435\u0440",
    upLite: "\u041f\u043e\u0434\u043d\u044f\u0442\u044c \u043a\u043e\u043d\u0442\u0435\u0439\u043d\u0435\u0440 \u0440\u044f\u0434\u043e\u043c \u0441 LiteLLM",
    point: "\u041d\u0430\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u043a \u043d\u0430\u043c",
    cb: "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c callback \u0432 LiteLLM",
    noCode: "\u043a\u043e\u0434 \u043d\u0435 \u043c\u0435\u043d\u044f\u0435\u0442\u0441\u044f",
    both: "\u043c\u0430\u0441\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u0434\u043e \u043c\u043e\u0434\u0435\u043b\u0438 \u0438 \u0432\u043e\u0437\u0432\u0440\u0430\u0442 \u043f\u043e\u0441\u043b\u0435",
    was: "# \u0431\u044b\u043b\u043e",
    now: "# \u0441\u0442\u0430\u043b\u043e \u2014 \u043c\u0435\u043d\u044f\u0435\u0442\u0441\u044f \u043e\u0434\u043d\u0430 \u0441\u0442\u0440\u043e\u043a\u0430",
    yours: "   # \u0432\u0430\u0448 \u043a\u043b\u044e\u0447, \u043a\u0430\u043a \u0431\u044b\u043b",
    ui: "# \u2192 http://localhost:8081/?token=9f3c1a\u2026",
    uiGrep: "docker logs pseudex | grep '\u043b\u043e\u043a\u0430\u043b\u044c\u043d\u044b\u0439 \u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441' -A2",
  };

  if (p.direct) {
    document.getElementById("step2-title").textContent = T.up;
    document.getElementById("step3-title").textContent = T.point;
    document.getElementById("step3-note").textContent = T.noCode;
    setBlock("step2-code",
      "docker run -d --name pseudex -p 8000:8000 -p 127.0.0.1:8081:8081 \\\n" +
      "  -v pseudex-data:/data \\\n" +
      "  -e PSEUDEX_ROLE=proxy \\\n" +
      "  -e PSEUDEX_UPSTREAM=" + p.upstream + " \\\n" +
      "  -e PSEUDEX_LICENSE_KEY=ps_live_\u2026 \\\n" +
      "  " + image);
    setBlock("step3-code",
      T.was + "\n" +
      "OPENAI_BASE_URL=" + p.upstream + "\n" +
      "OPENAI_API_KEY=" + p.key + "\n\n" +
      T.now + "\n" +
      "OPENAI_BASE_URL=http://pseudex:8000/v1\n" +
      "OPENAI_API_KEY=" + p.key + T.yours);
  } else {
    document.getElementById("step2-title").textContent = T.upLite;
    document.getElementById("step3-title").textContent = T.cb;
    document.getElementById("step3-note").textContent = T.both;
    setBlock("step2-code",
      "docker run -d --name pseudex -p 8000:8000 -p 127.0.0.1:8081:8081 \\\n" +
      "  -v pseudex-data:/data \\\n" +
      "  -e PSEUDEX_LICENSE_KEY=ps_live_\u2026 \\\n" +
      "  " + image);
    setBlock("step3-code",
      "masked = post(\"http://pseudex:8000/mask\",\n" +
      "              {\"org_id\": org, \"messages\": messages})\n" +
      "# \u2192 \u043c\u043e\u0434\u0435\u043b\u044c \u2192 \u043e\u0431\u0440\u0430\u0442\u043d\u043e \u0447\u0435\u0440\u0435\u0437 /unmask");
  }
  setBlock("step4-code", "curl localhost:8000/health\n" + T.uiGrep + "\n" + T.ui);
}

const tabs = document.getElementById("provider-tabs");
if (tabs) {
  PROVIDERS.forEach((provider, index) => {
    const button = document.createElement("button");
    button.setAttribute("role", "tab");
    button.dataset.provider = String(index);
    button.textContent = provider.label;
    button.addEventListener("click", () => showProvider(index));
    tabs.appendChild(button);
  });
  showProvider(0);
}
