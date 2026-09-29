(() => {
  'use strict';

  const SOURCE = 'bygdebladet-lokalfotball-v1';
  const ALLOWED_ORIGIN = 'https://leffernan.github.io';
  const PATH_MARKER = '/bygdebladet-lokalfotball/';
  let active = null;

  function findFrame(sourceWindow) {
    return [...document.querySelectorAll('iframe')].find(frame => {
      try {
        const url = new URL(frame.src, location.href);
        return frame.contentWindow === sourceWindow &&
          url.origin === ALLOWED_ORIGIN &&
          url.pathname.includes(PATH_MARKER);
      } catch {
        return false;
      }
    }) || null;
  }

  function lockHost(frame) {
    if (active) return;

    const body = document.body;
    const html = document.documentElement;
    const scrollY = window.scrollY;
    active = {
      frame,
      frameStyle: frame.getAttribute('style'),
      bodyStyle: body.getAttribute('style'),
      htmlStyle: html.getAttribute('style'),
      scrollY
    };

    html.style.overflow = 'hidden';
    body.style.position = 'fixed';
    body.style.top = `-${scrollY}px`;
    body.style.left = '0';
    body.style.right = '0';
    body.style.width = '100%';
    body.style.overflow = 'hidden';

    Object.assign(frame.style, {
      position: 'fixed',
      inset: '0',
      width: '100vw',
      height: '100dvh',
      maxWidth: 'none',
      maxHeight: 'none',
      margin: '0',
      border: '0',
      zIndex: '2147483646',
      background: '#F7F3E9'
    });

    frame.contentWindow?.postMessage({ source: SOURCE, type: 'match-activated' }, ALLOWED_ORIGIN);
  }

  function restoreAttribute(el, name, value) {
    if (value == null) el.removeAttribute(name);
    else el.setAttribute(name, value);
  }

  function unlockHost(frame) {
    if (!active || active.frame !== frame) return;
    const state = active;
    active = null;

    restoreAttribute(state.frame, 'style', state.frameStyle);
    restoreAttribute(document.body, 'style', state.bodyStyle);
    restoreAttribute(document.documentElement, 'style', state.htmlStyle);

    const previousBehavior = document.documentElement.style.scrollBehavior;
    document.documentElement.style.scrollBehavior = 'auto';
    window.scrollTo(0, state.scrollY);
    document.documentElement.style.scrollBehavior = previousBehavior;
  }

  window.addEventListener('message', event => {
    if (event.origin !== ALLOWED_ORIGIN || event.data?.source !== SOURCE) return;
    const frame = findFrame(event.source);
    if (!frame) return;

    if (event.data.type === 'match-open') lockHost(frame);
    if (event.data.type === 'match-close') unlockHost(frame);
  });
})();