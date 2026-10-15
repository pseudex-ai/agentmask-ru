/* Illustrative fullstack session, not a live run or a general detector.
 * Fixed fictional pairs preserve useful shapes; no credential was issued by a
 * vendor. Secret-shaped substitutes must NEVER be used as working credentials.
 * vault._fake_secret preserves vendor prefixes/character classes; coverage and
 * execution-side permissions still require acceptance for each coding adapter. */
(function () {
  'use strict';
  const root = document.querySelector('[data-coding-session]');
  if (!root) return;
  const mappings = [
    ['anna@customer.example', 'elena.volkova@contact.example'],
    ['billing.atlas.internal', 'billing.orion.internal'],
    ['/Users/marina/work/atlas', '/Users/elena/work/orion'],
    ['sk_test_51Pn8m4Q7v2K9r6T3x5B0c8D1e4F7g2H', 'sk_test_84Wu1t7X0c5R2y9A6e8I3j1K4l7M0n5O'],
    ['ghp_A7m9K2p4R8v1T6x3B5n0C9d2F4g7H1j6L8q5', 'ghp_H0t2R5w7Y1c4A9e6I8u3J2k5M7n0O4q9S1x8'],
    ['postgresql://billing:Q7m4Rv9K@db.atlas.internal/billing', 'postgresql://finance:N4t8Lp2R@db.orion.internal/finance'],
    ['atlas-payments', 'orion-payments']
  ];
  const protect = text => mappings.reduce((out, pair) => out.replaceAll(pair[0], pair[1]), text);
  const frames = [
    {
      tool: 'MCP · Sentry', command: 'get_issue_details({ issueId: "BILLING-42" })',
      agent: 'Сначала сопоставлю ошибку, клиента и повторное событие. MCP вернёт стек и детали запроса — проверю их перед отправкой модели.',
      local: 'issue: BILLING-42\nerror: duplicate ledger credit\ncustomer: anna@customer.example\nhost: billing.atlas.internal\ntenant: atlas-payments\nevent: evt_demo_104 · deliveries: 2',
      title: 'Та же форма данных. Другая личность.',
      detail: 'Клиент, хост и внутренний tenant получают стабильные подмены. Модель видит обычные значения и связи между ними; тип ошибки и повтор события не теряются. Свои хосты и tenant требуют настроенных правил.',
      risk: 'Вы не вставляли данные клиента в чат — их принёс MCP. Без проверки ответа инструмента вместе со стеком к модели уходят почта и внутренняя инфраструктура.'
    },
    {
      tool: 'Bash · grep / Read', command: 'rg -n "event.id|creditBalance|tenant" src/\n# Read: src/app/api/webhooks/stripe/route.ts',
      agent: 'Нашёл webhook и BillingHistory. Сохраню raw-body проверку подписи. Условие tenant и данные из стека должны согласоваться, хотя их оригиналы модели не нужны.',
      local: '/Users/marina/work/atlas/src/app/api/webhooks/stripe/route.ts:27\nconst rawBody = await request.text();\nconst event = stripe.webhooks.constructEvent(\n  rawBody, signature, process.env.STRIPE_WEBHOOK_SECRET!\n);\nconst tenant = "atlas-payments";\nawait creditBalance(event.data.object, tenant);\n\nsrc/components/BillingHistory.tsx:48\nreturn <CreditRows items={credits} />;',
      title: 'Подменить значение внутри кода. Не сам код.',
      detail: 'Строковый литерал остаётся строкой, ссылка на переменную окружения — ссылкой. Функции, JSX и структура программы видны модели; внутренний tenant совпадает с подменой из MCP. Личный префикс пути тоже заменён.',
      risk: 'Скрыть весь фрагмент — потерять логику бага. Заменить только промпт — оставить чувствительные литералы и комментарии в grep/Read. Нужна защита значений внутри полезного кода.'
    },
    {
      tool: 'Read · конфигурация', command: 'Read({ file_path: ".env.local" })',
      agent: 'Модель должна понимать, что здесь Stripe, GitHub и PostgreSQL. Но ей не нужны настоящие credentials. Для выполнения запросов будем брать секреты локально из окружения.',
      local: '# .env.local · фрагмент · значения вымышлены\nSTRIPE_SECRET_KEY=sk_test_51Pn8m4Q7v2K9r6T3x5B0c8D1e4F7g2H\nGITHUB_TOKEN=ghp_A7m9K2p4R8v1T6x3B5n0C9d2F4g7H1j6L8q5\nDATABASE_URL=postgresql://billing:Q7m4Rv9K@db.atlas.internal/billing\nAPP_ORIGIN=http://127.0.0.1:3000',
      title: 'Похож на ключ. Но это не ваш ключ.',
      detail: 'Сохраняются префиксы sk_test_ и ghp_, длина и класс символов тела; DSN остаётся читаемым URI. Это правдоподобные подмены для модельного контекста, не рабочие credentials. Нестандартные DSN и секреты требуют своих правил; политика может вместо подмены запретить передачу.',
      risk: 'Ключ API, токен репозитория и пароль БД остаются в транскрипте. Замена на [SECRET] скрыла бы значение, но сломала бы форму; правдоподобная подмена сохраняет полезную структуру без оригинала.'
    },
    {
      tool: 'Bash · локальный API', command: 'pnpm exec tsx scripts/replay-webhook.ts --fixture retry --repeat 2\ncurl -sS http://127.0.0.1:3000/api/billing/demo-account \\\n  -H "Authorization: Bearer $BILLING_API_TOKEN"',
      agent: 'Воспроизведу retry локальным скриптом. Подпись и Authorization формируются в вашем контуре из окружения — не из фейкового ключа, который увидела модель.',
      local: '# Иллюстративный ответ локального API\nPOST /api/webhooks/stripe → 200\nPOST /api/webhooks/stripe → 200\n{\n  "event": "evt_demo_104",\n  "email": "anna@customer.example",\n  "tenant": "atlas-payments",\n  "credits": [{"amount": 4900}, {"amount": 4900}],\n  "debug": {"upstream": "billing.atlas.internal"}\n}',
      title: 'Model-view можно менять. Подписанный запрос — нельзя.',
      detail: 'Фейковый ключ не авторизует запрос, а подпись над изменённым payload не совпадёт. Секреты подаются локально только разрешённой операции. Ответ API снова защищается перед моделью: подмены те же, JSON и две записи зачисления сохранены.',
      risk: 'Слепая замена прямо в curl или подписанном теле может сломать авторизацию. А возврат настоящего секрета в произвольную Bash-команду может открыть новый путь утечки — даже если промпт был очищен.'
    },
    {
      tool: 'apply_patch · TypeScript', command: 'apply_patch · webhook handler + regression test',
      agent: 'Добавлю атомарную регистрацию event.id и зачисление в одной транзакции. Контекст патча содержит тот же внутренний tenant — перед разрешённым применением нужно восстановить точный литерал.',
      localLabel: 'Разрешённый патч · оригинальные литералы',
      local: '*** Update File: src/billing.ts\n@@\n const tenant = "atlas-payments";\n- await creditBalance(event.data.object, tenant);\n+ await db.$transaction(async tx => {\n+   await tx.webhookEvent.create({\n+     data: { id: event.id } // UNIQUE\n+   });\n+   await creditBalance(event.data.object, tenant, tx);\n+ });\n# duplicate-event обрабатывается отдельно\n# UI: обновить BillingHistory после ответа',
      title: 'В патче должны совпасть не только скобки.',
      detail: 'Модель строит diff со строкой "orion-payments". В настоящем файле — "atlas-payments": без точного обратного соответствия контекст патча не совпадёт. Восстанавливаются разрешённые значения, а не переписывается вся программа. Вычисленную производную от подмены нельзя просто «развернуть» обратно.',
      risk: 'Обычное обезличивание ломает точный контекст diff. Агент начинает угадывать или переписывать больший кусок кода. Слепой unmask любого текста опасен: строка может оказаться исполняемой командой, а не литералом.'
    },
    {
      tool: 'Bash · Vitest / Playwright', command: 'pnpm exec vitest run tests/webhook-idempotency.test.ts\npnpm exec playwright test tests/billing-history.spec.ts',
      agent: 'Проверю последовательный и конкурентный retry, откат и неверную подпись. Затем UI — одна строка зачисления. Ответы тестов и артефакты тоже проходят проверку.',
      local: '# Иллюстративный вывод тестов\n✓ sequential retry → one credit\n✓ concurrent retry → one credit\n✓ rollback, then retry → one credit\n✓ invalid signature → rejected\n✓ billing UI → one row\n\nfixture={"email":"anna@customer.example","tenant":"atlas-payments"}\n# Диагностический дамп не должен раскрыть конфиг:\nGITHUB_TOKEN=ghp_A7m9K2p4R8v1T6x3B5n0C9d2F4g7H1j6L8q5',
      title: 'Даже зелёный тест может заново напечатать секрет.',
      detail: 'Почта, tenant и токен повторно подменяются перед возвратом к модели. Подмены стабильны между MCP, API и тестами. Проверить только чтение .env недостаточно: его значение может всплыть в дампе ошибки через несколько ходов.',
      risk: 'Тесты прошли, но диагностический дамп вынес токен и fixture в историю агента. Защита одного файла не закрывает терминал и повторные tool results.'
    },
    {
      tool: 'Review · история сессии', command: 'git diff --stat\ngit diff -- src/billing.ts src/components/BillingHistory.tsx',
      agent: 'Подготовлены backend-правка, обновление UI и регрессии; production не изменён. На следующем ходе нужно передать защищённую историю, а не снова приложить исходные ответы инструментов.',
      localLabel: 'Исходные данные в вашем контуре',
      local: 'MCP customer: anna@customer.example\nAPI upstream: billing.atlas.internal\ncode tenant: atlas-payments\nconfig key: sk_test_51Pn8m4Q7v2K9r6T3x5B0c8D1e4F7g2H\ntest token: ghp_A7m9K2p4R8v1T6x3B5n0C9d2F4g7H1j6L8q5\n\nИстория для следующего хода:\nMCP → код → конфиг → API → patch → тесты',
      title: 'Одна сущность — одна подмена на протяжении сессии.',
      detail: 'Модель продолжает связывать клиента, tenant и события по согласованным подменам. Новые логи и повторная история защищаются снова; оригиналы не должны вернуться на следующем ходе. Это целевой сценарий coding-беты, не обещание поддержки любого harness.',
      risk: 'В повторную историю легко вернуть исходный MCP-ответ или старый дамп .env. Очистка одного хода не защищает длинную сессию и её последующие инструменты.'
    }
  ];
  let step = 0, mode = 'protected';
  let animations = [], ghost;
  const field = name => root.querySelector('[data-session-' + name + ']');
  function render(animate) {
    animations.forEach(a => a.cancel()); animations = [];
    if (ghost) { ghost.remove(); ghost = null; }
    const stage = field('stage'), view = field('view');
    const moving = animate && stage && view && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    const oldHeight = stage ? stage.offsetHeight : 0;
    if (moving) {
      ghost = view.cloneNode(true);
      [ghost, ...ghost.querySelectorAll('*')].forEach(node => {
        Array.from(node.attributes).forEach(attr => {
          if (attr.name.startsWith('data-session-') || ['id','role','aria-live'].includes(attr.name)) node.removeAttribute(attr.name);
        });
      });
      ghost.inert = true; ghost.setAttribute('aria-hidden', 'true');
      ghost.classList.add('p-session-ghost'); stage.appendChild(ghost);
    }
    const frame = frames[step], safe = mode === 'protected';
    field('tool').textContent = frame.tool;
    field('command').textContent = frame.command;
    field('agent').textContent = frame.agent;
    field('local-label').textContent = frame.localLabel || 'Ответ инструмента в вашем контуре';
    field('model-label').textContent = safe ? 'Контекст модели · правдоподобные подмены' : 'Контекст модели · без проверки';
    field('local').textContent = frame.local;
    field('model').textContent = safe ? protect(frame.local) : frame.local;
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
    if (moving) {
      const old = ghost;
      const leave = old.animate([{opacity:1}, {opacity:0}], {duration:280,easing:'ease-in-out',fill:'both'});
      const enter = view.animate([{opacity:0}, {opacity:1}], {duration:320,easing:'ease-in-out'});
      const resize = stage.animate([{height:oldHeight+'px'}, {height:view.offsetHeight+'px'}], {duration:320,easing:'ease-in-out'});
      animations = [leave,enter,resize];
      leave.finished.then(() => {old.remove();if (ghost===old) ghost=null;}, () => old.remove());
    }
  }
  root.querySelectorAll('[data-session-step]').forEach(button => button.addEventListener('click', () => {step=Number(button.dataset.sessionStep);render(true);}));
  root.querySelectorAll('[data-session-mode]').forEach(button => button.addEventListener('click', () => {mode=button.dataset.sessionMode;render(true);}));
  field('next').addEventListener('click', () => {step=(step+1)%frames.length;render(true);});
  field('reset').addEventListener('click', () => {step=0;mode='protected';render(true);});
  field('edge').addEventListener('click', () => {
    field('edge-result').textContent = 'Правдоподобная подмена — не разрешение на использование секрета. Оригинал не восстанавливается в произвольную Bash-команду: операция остановлена. Credentials подаются локально только разрешённой операции; shell и сеть требуют отдельного sandbox.';
  });
  render(false);
}());
