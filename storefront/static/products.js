/* Synthetic, local-only demonstrations. No engine, filesystem, eval, uploads,
   telemetry, credentials or external request is involved in these examples. */
(function () {
  'use strict';
  const realConsole = document.querySelector('[data-real-console]');
  if (realConsole) {
    const tabs = Array.from(realConsole.querySelectorAll('[data-real-tab]'));
    function positionScreen(panel) {
      const screen = panel.querySelector('.p-real-screen');
      if (screen) { screen.scrollTop = screen.hasAttribute('data-screen-bottom') ? screen.scrollHeight : 0; }
    }
    function selectTab(tab, focus) {
      tabs.forEach(item => {
        const selected = item === tab;
        item.setAttribute('aria-selected', String(selected));
        item.tabIndex = selected ? 0 : -1;
      });
      realConsole.querySelectorAll('[data-real-panel]').forEach(panel => {
        panel.hidden = panel.dataset.realPanel !== tab.dataset.realTab;
        if (!panel.hidden) { positionScreen(panel); }
      });
      if (focus) { tab.focus(); }
    }
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => selectTab(tab, false));
      tab.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') { next = (index + 1) % tabs.length; }
        if (event.key === 'ArrowLeft') { next = (index + tabs.length - 1) % tabs.length; }
        if (event.key === 'Home') { next = 0; }
        if (event.key === 'End') { next = tabs.length - 1; }
        if (next !== undefined) { event.preventDefault(); selectTab(tabs[next], true); }
      });
    });
    realConsole.querySelectorAll('[data-real-panel] img').forEach(image => {
      image.addEventListener('load', () => {
        const panel = image.closest('[data-real-panel]');
        if (!panel.hidden) { positionScreen(panel); }
      });
    });
  }

  document.querySelectorAll('[data-select-harness]').forEach(link => link.addEventListener('click', () => {
    const field = document.querySelector('[name="harness"]');
    if (field) { field.value = link.dataset.selectHarness; }
  }));
}());
