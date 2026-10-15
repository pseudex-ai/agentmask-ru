/* An illustrative fullstack session adapted from official workflows, not an
 * executed agent run or a general-purpose detector. These fixed mappings expose
 * the security boundary; no command, file, API, MCP or model is actually invoked.
 * Never put real credentials/customer records in this fixture. */
(function () {
  'use strict';
  const root = document.querySelector('[data-coding-session]');
  if (!root) return;
  const mappings = [
    ['anna@customer.example', 'user-17@example.invalid'],
    ['billing.atlas.internal', 'service-01.internal.invalid'],
    ['/Users/marina/work/atlas', '/workspace/project-01'],
    ['sk_test_DEMO_NOT_A_KEY', '[SECRET REMOVED]'],
    ['whsec_DEMO_NOT_A_SECRET', '[SECRET REMOVED]'],
    ['postgresql://demo:demo@db.atlas.internal/billing', '[CONNECTION SECRET REMOVED]']
  ];
  const protect = text => mappings.reduce((out, pair) => out.replaceAll(pair[0], pair[1]), text);
  const frames = [
    {
      tool: 'MCP · Sentry', command: 'get_issue_details({ issueId: "BILLING-42" })',
      agent: 'Сначала сопоставлю событие, повторную доставку и запись в балансе. Запрошу детали ошибки через MCP.',
      local: 'issue: BILLING-42\nerror: duplicate ledger credit\ncustomer: anna@customer.example\nhost: billing.atlas.internal\nsource: /Users/marina/work/atlas/src/billing.ts\nevent: evt_demo_104 · deliveries: 2',
      title: 'MCP приносит не только ошибку, но и данные клиента.',
      detail: 'В сценарии почта, внутренний адрес и личный путь заменены. Тип ошибки, event ID и повторная доставка остаются понятными модели.',
      risk: 'Ответ MCP целиком попал в модельный контекст: вместе со стеком — почта клиента, внутренний хост и путь на вашем компьютере.'
    },
    {
      tool: 'Bash · grep / Read', command: 'rg -n "event.id|creditBalance" src/\n# затем Read: src/app/api/webhooks/stripe/route.ts',
      agent: 'Нашёл webhook и компонент баланса. Подпись проверяется, но повторный event.id не исключён. Сохраню проверку подписи и проверю зачисление.',
      local: '/Users/marina/work/atlas/src/app/api/webhooks/stripe/route.ts:27\nconst rawBody = await request.text();\nconst event = stripe.webhooks.constructEvent(\n  rawBody, signature, process.env.STRIPE_WEBHOOK_SECRET!\n);\nawait creditBalance(event.data.object);\n\nsrc/components/BillingHistory.tsx:48\nreturn <CreditRows items={credits} />;',
      title: 'Модели нужен код. Не имя владельца рабочего каталога.',
      detail: 'Функции, JSX, номера строк и ссылка на переменную окружения сохранены. Подменяется чувствительный префикс пути, а не синтаксис программы.',
      risk: 'Полный grep-вывод и прочитанный код уходят в контекст без проверки. Секрет в комментарии или строковом литерале пошёл бы тем же путём.'
    },
    {
      tool: 'Read · конфигурация', command: 'Read({ file_path: ".env.local" })',
      agent: 'Проверю, какие переменные настроены. Значения секретов модели не нужны: тестовый процесс должен получать их локально из окружения.',
      local: '# .env.local · вымышленные значения\nSTRIPE_SECRET_KEY=sk_test_DEMO_NOT_A_KEY\nSTRIPE_WEBHOOK_SECRET=whsec_DEMO_NOT_A_SECRET\nDATABASE_URL=postgresql://demo:demo@db.atlas.internal/billing\nAPP_ORIGIN=http://127.0.0.1:3000',
      title: 'Ключ не должен пережить этот шаг в транскрипте.',
      detail: 'В примере значения секретов удалены из ответа модели. Имена переменных остаются. Исходный файл не переписан, секрет не превращён в обратимый токен для произвольной команды.',
      risk: 'Ключ, signing secret и пароль БД теперь в истории сессии. Даже когда агент закончит читать конфиг, эти значения могут снова уйти с очередным запросом.'
    },
    {
      tool: 'Bash · локальный API', command: 'pnpm exec tsx scripts/replay-webhook.ts --fixture retry --repeat 2\ncurl -sS http://127.0.0.1:3000/api/billing/demo-account',
      agent: 'Воспроизведу повторную доставку на локальном fixture. Подпись формирует тестовый скрипт; секрет берётся из окружения, не из ответа модели.',
      local: '# Пример вывода локального стенда\nPOST /api/webhooks/stripe → 200\nPOST /api/webhooks/stripe → 200\n{\n  "event": "evt_demo_104",\n  "email": "anna@customer.example",\n  "credits": [{"amount": 4900}, {"amount": 4900}],\n  "debug": {"upstream": "billing.atlas.internal"}\n}',
      title: 'Ответ API — ещё один вход чувствительных данных.',
      detail: 'После локального выполнения ответ снова защищён перед моделью. Две записи по одному событию видны; клиент и внутренний адрес подменены так же, как в MCP.',
      risk: 'Вы не вставляли email в промпт — его напечатал curl. Без проверки tool_result он всё равно оказывается в контексте модели.'
    },
    {
      tool: 'apply_patch · TypeScript', command: 'apply_patch · webhook handler + regression test',
      agent: 'Добавлю атомарную регистрацию event.id в одной транзакции с зачислением. Повтор подтверждаем без второго кредита; проверка raw-body подписи остаётся.',
      localLabel: 'Разрешённая правка · настоящий путь',
      local: '*** Update File: /Users/marina/work/atlas/src/billing.ts\n# Фрагмент правки; duplicate-event обрабатывается отдельно\n- await creditBalance(event.data.object);\n+ await db.$transaction(async tx => {\n+   await tx.webhookEvent.create({\n+     data: { id: event.id } // UNIQUE\n+   });\n+   await creditBalance(event.data.object, tx);\n+ });\n# UI: обновить BillingHistory после успешного ответа',
      title: 'Подмена пути не должна отправить патч в никуда.',
      detail: 'Справа — путь, с которым работает модель. Слева — точный локальный путь для разрешённого инструмента. Это демонстрация проверенного соответствия, не слепая подстановка в shell.',
      risk: 'Агент делает ту же правку, но его контекст уже содержит исходные пути и данные предыдущих инструментов. Исправленный баг не отменяет эту утечку.'
    },
    {
      tool: 'Bash · Vitest / Playwright', command: 'pnpm exec vitest run tests/webhook-idempotency.test.ts\npnpm exec playwright test tests/billing-history.spec.ts',
      agent: 'Проверю retry, одновременную доставку, откат транзакции и неверную подпись. Затем UI: одно зачисление должно отображаться одной строкой.',
      local: '# Иллюстративный вывод тестов\n✓ first delivery → one credit\n✓ sequential retry → one credit\n✓ concurrent retry → one credit\n✓ rollback, then retry → one credit\n✓ invalid signature → rejected\n✓ billing UI → one row\n\nfixture: anna@customer.example\nartifact: /Users/marina/work/atlas/test-results/billing.png',
      title: 'Тест прошёл. Его лог тоже нужно защитить.',
      detail: 'Имена тестов и assertions полезны модели. Email fixture и личный путь к артефакту снова заменены — защита не заканчивается после патча.',
      risk: 'Даже зелёный тест может напечатать PII, дамп запроса или секрет. Тестовый вывод тоже становится частью истории агента.'
    },
    {
      tool: 'Review · история сессии', command: 'git diff --stat\ngit diff -- src/billing.ts src/components/BillingHistory.tsx',
      agent: 'Причина — отсутствие идемпотентности зачисления при повторной доставке события. Подготовлены backend-правка, обновление UI и регрессии. Production не изменён.',
      localLabel: 'Что осталось в локальном проекте',
      local: 'Исходный код + .env.local\ncustomer: anna@customer.example\nSTRIPE_SECRET_KEY=sk_test_DEMO_NOT_A_KEY\nworkspace: /Users/marina/work/atlas\n\nСценарий завершён: правка + тесты, без деплоя.',
      model: 'История для следующего хода:\nMCP issue → user-17@example.invalid\nconfig → [SECRET REMOVED]\nAPI result → service-01.internal.invalid\npatch path → /workspace/project-01/src/billing.ts\ntest fixture → user-17@example.invalid\n\nКонтекст бага и правки сохранён.',
      title: 'Сессия становится длиннее. Секреты не должны копиться вместе с ней.',
      detail: 'Цель coding-беты — защищать подключённые границы на каждом ходе, включая повторную историю. Работа с кодом остаётся полезной; секреты требуют отдельной политики.',
      risk: 'В длинном транскрипте накапливаются ответы MCP, содержимое конфигов, команды и логи. Одной очистки первого промпта для этого недостаточно.'
    }
  ];
  let step = 0;
  let mode = 'protected';
  let animation;
  const field = name => root.querySelector('[data-session-' + name + ']');
  function render(animate) {
    const frame = frames[step];
    const safe = mode === 'protected';
    field('tool').textContent = frame.tool;
    field('command').textContent = frame.command;
    field('agent').textContent = frame.agent;
    field('local-label').textContent = frame.localLabel || 'Ответ инструмента в вашем контуре';
    field('model-label').textContent = safe ? 'Контекст модели · после защиты' : 'Контекст модели · без проверки';
    field('local').textContent = frame.local;
    field('model').textContent = safe ? (frame.model || protect(frame.local)) : frame.local;
    field('title').textContent = safe ? frame.title : 'Без защиты: этот контекст уходит как есть.';
    field('description').textContent = safe ? frame.detail : frame.risk;
    field('counter').textContent = String(step + 1).padStart(2, '0') + ' / 07';
    field('next').textContent = step === frames.length - 1 ? 'Повторить сессию ↺' : 'Следующий шаг →';
    field('edge-result').textContent = '';
    root.classList.toggle('p-session-raw', !safe);
    root.querySelectorAll('[data-session-step]').forEach(button => {
      button.setAttribute('aria-pressed', String(Number(button.dataset.sessionStep) === step));
      button.classList.toggle('is-complete', Number(button.dataset.sessionStep) < step);
    });
    root.querySelectorAll('[data-session-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.sessionMode === mode)));
    if (animation) animation.cancel();
    if (animate && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      animation = field('panes').animate([{opacity:.55, transform:'translateY(3px)'}, {opacity:1, transform:'translateY(0)'}], {duration:150, easing:'ease-out'});
    }
  }
  root.querySelectorAll('[data-session-step]').forEach(button => button.addEventListener('click', () => {step = Number(button.dataset.sessionStep); render(true);}));
  root.querySelectorAll('[data-session-mode]').forEach(button => button.addEventListener('click', () => {mode = button.dataset.sessionMode; render(true);}));
  field('next').addEventListener('click', () => {step = (step + 1) % frames.length; render(true);});
  field('reset').addEventListener('click', () => {step = 0; mode = 'protected'; render(true);});
  field('edge').addEventListener('click', () => {
    field('edge-result').textContent = 'Секрет не восстанавливается в произвольную Bash-команду. В этом сценарии операция остановлена; используйте разрешённый инструмент с локальной подачей credentials. Контроль shell и сети требует отдельного sandbox.';
  });
  render(false);
}());
