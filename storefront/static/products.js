/* Synthetic, local-only demonstrations. No engine, filesystem, eval, uploads,
   telemetry, credentials or external request is involved in these examples. */
(function () {
  'use strict';
  const realConsole = document.querySelector('[data-real-console]');
  if (realConsole) {
    const tabs = Array.from(realConsole.querySelectorAll('[data-real-tab]'));
    function positionScreen(panel) {
      const screen = panel.querySelector('.p-real-screen');
      if (screen) { screen.scrollTop = 0; }
    }
    const stage = realConsole.querySelector('[data-real-stage]');
    let animations = [];
    let ghost;
    function selectTab(tab, focus) {
      const panels = Array.from(realConsole.querySelectorAll('[data-real-panel]'));
      const previous = panels.find(panel => !panel.hidden);
      const next = panels.find(panel => panel.dataset.realPanel === tab.dataset.realTab);
      animations.forEach(animation => animation.cancel());
      animations = [];
      if (ghost) { ghost.remove(); ghost = null; }
      const animate = stage && previous && next && previous !== next && !matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (animate) {
        // Only public screenshot markup is copied, never user forms or runtime
        // UI state. Inert ghost has no IDs/hooks and cannot receive focus/clicks.
        ghost = previous.cloneNode(true);
        ghost.removeAttribute('data-real-panel');
        ghost.removeAttribute('id');
        ghost.removeAttribute('role');
        ghost.removeAttribute('aria-labelledby');
        ghost.setAttribute('aria-hidden', 'true');
        ghost.inert = true;
        ghost.classList.add('p-real-ghost');
        ghost.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
        const oldScreen = previous.querySelector('.p-real-screen');
        const copyScreen = ghost.querySelector('.p-real-screen');
        stage.appendChild(ghost);
        if (oldScreen && copyScreen) { copyScreen.scrollTop = oldScreen.scrollTop; }
      }
      tabs.forEach(item => {
        const selected = item === tab;
        item.setAttribute('aria-selected', String(selected));
        item.tabIndex = selected ? 0 : -1;
      });
      panels.forEach(panel => { panel.hidden = panel !== next; });
      if (next) { positionScreen(next); }
      if (animate) {
        const old = ghost;
        const leave = old.animate([{opacity:1}, {opacity:0}], {duration:300, easing:'ease-in-out', fill:'both'});
        const enter = next.animate([{opacity:0}, {opacity:1}], {duration:360, easing:'ease-in-out'});
        animations = [leave, enter];
        leave.finished.then(() => { old.remove(); if (ghost === old) ghost = null; }, () => old.remove());
      }
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
