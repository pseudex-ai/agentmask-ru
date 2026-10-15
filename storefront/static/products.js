/* Synthetic, local-only demonstrations. No engine, filesystem, eval, uploads,
   telemetry, credentials or external request is involved in these examples. */
(function () {
  'use strict';
  const consoleDemo = document.querySelector('[data-enterprise-demo]');
  if (consoleDemo) {
    const samples = {
      support: ['Помоги клиенту Марине Соколовой.\nПочта: marina@client.example', 'Помоги клиенту Елене Волковой.\nПочта: elena@contact.example'],
      hr: ['Подготовь ответ кандидату Анне Орловой.\nПочта: anna@candidate.example', 'Подготовь ответ кандидату Ирине Лебедевой.\nПочта: irina@profile.example']
    };
    function updatePolicy() {
      const app = consoleDemo.querySelector('[data-demo-app]').value;
      const block = consoleDemo.querySelector('[data-demo-policy]').value === 'block';
      const sample = samples[app] || samples.support;
      consoleDemo.querySelector('[data-original-text]').textContent = sample[0];
      consoleDemo.querySelector('[data-protected-text]').textContent = block ? 'Запрос не передан.\nПравило: персональные данные → блокировать.' : sample[1];
      consoleDemo.querySelector('[data-preview-label]').textContent = block ? 'ПЕРЕДАЧА ОСТАНОВЛЕНА' : 'НА СТОРОНЕ МОДЕЛИ';
      const outcome = consoleDemo.querySelector('[data-policy-outcome]');
      outcome.textContent = block ? '× Модель не получила запрос' : '✓ Запрос продолжен с подменами';
      outcome.classList.toggle('p-cross', block);
    }
    consoleDemo.querySelectorAll('[data-console-tab]').forEach(button => {
      button.addEventListener('click', () => {
        const selected = button.dataset.consoleTab;
        consoleDemo.querySelectorAll('[data-console-tab]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
        consoleDemo.querySelectorAll('[data-console-panel]').forEach(panel => { panel.hidden = panel.dataset.consolePanel !== selected; });
      });
    });
    consoleDemo.querySelector('[data-demo-app]').addEventListener('change', updatePolicy);
    consoleDemo.querySelector('[data-demo-policy]').addEventListener('change', updatePolicy);
    consoleDemo.querySelector('[data-demo-reveal]').addEventListener('click', () => {
      consoleDemo.querySelector('[data-reveal-result]').textContent = 'Доступ закрыт: необходимо отдельное право reveal. В демо оригинал не раскрывается.';
    });
    updatePolicy();
  }

  const coding = document.querySelector('[data-coding-demo]');
  if (coding) {
    // Both arms use the same fixture and task; only boundary restoration differs.
    const original = 'anna@example.test';
    const token = 'user-17@example.invalid';
    const fixture = { ticket: 'SR-104', email: original, status: 'retry' };
    let mode = 'roundtrip', step = 0;
    const literal = value => 'ticket: ' + fixture.ticket + '\nemail: ' + value + '\nstatus: ' + fixture.status;
    function render() {
      const restored = mode === 'roundtrip';
      const executionQuery = restored ? original : token;
      const hit = fixture.email === executionQuery;
      const frames = [
        { leftLabel: 'В ВАШЕМ ФАЙЛЕ', rightLabel: 'В КОНТЕКСТЕ МОДЕЛИ', left: literal(original), right: literal(token), title: 'Смысл задачи — тот же. Личность — другая.', description: 'Модель видит статус и номер заявки. Почта клиента заменена; исходный файл не меняется.', next: 'Проверить поиск →' },
        { leftLabel: 'МОДЕЛЬ ПРОСИТ НАЙТИ', rightLabel: 'ЛОКАЛЬНЫЙ ПОИСК ПОЛУЧАЕТ', left: 'search({\n  email: "' + token + '"\n})', right: 'search({\n  email: "' + executionQuery + '"\n})', title: restored ? 'Для инструмента восстанавливается точное значение.' : 'Поиск получил фейк. В исходном файле его нет.', description: restored ? 'Подмена распознана в разрешённом параметре поиска. Это не строковая замена внутри произвольной shell-команды.' : 'Одного маскирования недостаточно: инструмент не знает соответствия и ищет строку, которой не существует.', next: 'Посмотреть результат →' },
        { leftLabel: 'РЕЗУЛЬТАТ ЛОКАЛЬНОГО ПОИСКА', rightLabel: 'РЕЗУЛЬТАТ ДЛЯ МОДЕЛИ', left: hit ? 'Найдена 1 запись\n' + literal(original) : 'Найдено 0 записей\nСовпадений нет.', right: hit ? 'Найдена 1 запись\n' + literal(token) : 'Найдено 0 записей\nСовпадений нет.', title: hit ? 'Нашли нужную заявку. Оригинал снова скрыт.' : 'Данные скрыты, но задача не решена.', description: hit ? 'Результат инструмента повторно маскируется до возвращения в модель. Подмена та же, связь с заявкой сохранена.' : 'Модель получает пустой результат. Это цена фильтра, который защитил вход, но забыл обратную подстановку.', next: 'Итог для пользователя →' },
        { leftLabel: 'ОТВЕТ МОДЕЛИ', rightLabel: 'ОТВЕТ ДЛЯ ВАС', left: hit ? 'Заявка SR-104 найдена.\nКлиент: ' + token + '\nПричина: повторная обработка.' : 'Заявка не найдена.\nПроверьте email клиента.', right: hit ? 'Заявка SR-104 найдена.\nКлиент: ' + original + '\nПричина: повторная обработка.' : 'Заявка не найдена.\nПроверьте email клиента.', title: hit ? 'Полезный результат — без оригинала в model-view.' : 'Корректный фильтр — ещё не работающий агент.', description: hit ? 'В разрешённом пользовательском ответе вернулась исходная почта. Это синтетическая демонстрация механизма, а не измерение качества живой модели.' : 'Переключитесь на полный цикл и повторите поиск на том же файле. Задача и исходные данные не меняются.', next: 'Повторить цикл ↻' }
      ];
      const frame = frames[step];
      ['leftLabel','rightLabel','left','right'].forEach(key => {
        const selector = {leftLabel:'[data-code-left-label]',rightLabel:'[data-code-right-label]',left:'[data-code-left]',right:'[data-code-right]'}[key];
        coding.querySelector(selector).textContent = frame[key];
      });
      coding.querySelector('[data-hop-title]').textContent = frame.title;
      coding.querySelector('[data-hop-description]').textContent = frame.description;
      coding.querySelector('[data-hop-next]').textContent = frame.next;
      coding.querySelectorAll('[data-hop]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.hop) === step)));
      coding.querySelectorAll('[data-coding-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.codingMode === mode)));
      coding.querySelector('[data-edge-result]').textContent = '';
    }
    coding.querySelectorAll('[data-hop]').forEach(button => button.addEventListener('click', () => { step = Number(button.dataset.hop); render(); }));
    coding.querySelectorAll('[data-coding-mode]').forEach(button => button.addEventListener('click', () => { mode = button.dataset.codingMode; render(); }));
    coding.querySelector('[data-hop-next]').addEventListener('click', () => { step = (step + 1) % 4; render(); });
    coding.querySelector('[data-edge-case]').addEventListener('click', () => {
      coding.querySelector('[data-edge-result]').textContent = 'Операция остановлена: соответствие не найдено. Поиск не выполняется, значение не угадывается.';
    });
    render();
  }
  document.querySelectorAll('[data-select-harness]').forEach(link => link.addEventListener('click', () => {
    const field = document.querySelector('[name="harness"]');
    if (field) { field.value = link.dataset.selectHarness; }
  }));
}());
