/* Paint-only navigation enhancement. Real browser links, POSTs, history and
 * redirects stay native: no preventDefault, fetched HTML, router or load delay.
 * A one-shot timestamp (no URL/contact data) marks ordinary same-origin links.
 * The incoming fade is prepared before first paint without a native transition API.
 * Storage denied / JS disabled => ordinary navigation. */
(function () {
  'use strict';
  const root = document.documentElement;
  const key = 'pseudex-page-arrival';
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  let arrival = 0;
  try {
    arrival = Number(sessionStorage.getItem(key));
    sessionStorage.removeItem(key);
  } catch (_) {}
  if (!reduced() && arrival && Date.now() - arrival < 15000) {
    root.classList.add('ps-nav-enter');
  }
  document.addEventListener('click', event => {
    if (reduced() || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest && event.target.closest('a[href]');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !/^https?:$/.test(url.protocol)) return;
    if (url.pathname === location.pathname && url.search === location.search) return;
    // Do not animate downloads, files, or special links without this page shell.
    if (/\.(pdf|zip|png|jpe?g|webp|svg|csv|json|xml|txt)$/i.test(url.pathname)) return;
    try { sessionStorage.setItem(key, String(Date.now())); } catch (_) { return; }
    root.classList.remove('ps-nav-enter');
    root.classList.add('ps-nav-leave');
    // If navigation is cancelled/stopped, never leave the old page dimmed.
    setTimeout(() => root.classList.remove('ps-nav-leave'), 1200);
  });
  // A BFCache restore can retain the outgoing opacity. Clear it synchronously
  // and replay the fade only for actual history restoration, never hash changes.
  addEventListener('pageshow', event => {
    root.classList.remove('ps-nav-leave');
    if (event.persisted && !reduced()) {
      root.classList.remove('ps-nav-enter');
      void root.offsetWidth;
      root.classList.add('ps-nav-enter');
    }
  });
  addEventListener('pagehide', () => {
    root.classList.remove('ps-nav-leave');
  });
}());
