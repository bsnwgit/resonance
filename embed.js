/* embed.js — the half of an embed that runs in somebody else's page.
   ====================================================================

   A host application adds one tag:

     <script src="https://ai.example.com:9701/embed.js"
             data-code-url="/api/resonance-code"
             data-style="bubble"></script>

   …and this does the rest: asks their own server for a one-use code, frames
   the interface against it, and — for `bubble` — draws the launcher and the
   panel it opens.

   WHY THIS SHIPS FROM HERE rather than being an iframe snippet in the manual.
   Six applications hand-writing the same forty lines is six chances to get
   the microphone permission, the sandbox flags, the origin check on incoming
   messages or the session renewal subtly wrong, and five of those are silent.
   The one that is not silent is the microphone, and it is the single most
   common way an integration fails. This way the tricky parts are written
   once, here, by whoever also wrote the other end of them.

   WHAT IT DELIBERATELY DOES NOT DO is touch the key. The key belongs to the
   host's server and never reaches a browser; what this fetches from them is a
   code that is good once and for a minute. See docs/embedding.md.

   No dependencies, no build, and no globals beyond `window.Resonance`. It is
   going into pages this project has never seen. */

(function () {
  'use strict';

  /* `currentScript` is the tag that is running, which is how the
     configuration is read without the host having to name anything twice. It
     is null when a bundler has re-hosted this inside a module, so there is a
     fallback — by src rather than by position, because a page can have more
     than one script and the last one is not reliably this one. */
  var SELF = document.currentScript ||
    (function () {
      var all = document.querySelectorAll('script[src*="embed.js"]');
      return all.length ? all[all.length - 1] : null;
    })();

  if (!SELF) {
    console.error('[resonance] embed.js cannot find its own script tag, so it ' +
                  'cannot read its configuration. Load it with a plain ' +
                  '<script src="…/embed.js" data-code-url="…"> tag.');
    return;
  }

  var D = SELF.dataset;
  /* Where this server is, taken from the tag that loaded this file rather
     than configured again. Two places to write an address is one place for
     them to disagree, and the disagreement shows up as a frame that will not
     load for reasons the console explains badly. */
  var ORIGIN = new URL(SELF.src, location.href).origin;

  var CFG = {
    codeUrl: D.codeUrl || '',
    style:   (D.style || 'bubble').toLowerCase(),
    target:  D.target || '',
    label:   D.label || 'Ask',
    side:    (D.side || 'right').toLowerCase() === 'left' ? 'left' : 'right',
    width:   parseInt(D.width, 10)  || 400,
    height:  parseInt(D.height, 10) || 620,
    open:    D.open === 'true' || D.open === '',
  };

  if (!CFG.codeUrl) {
    console.error('[resonance] embed.js needs data-code-url — the address on ' +
                  'YOUR server that returns {"code": "…"} for whoever is ' +
                  'signed in. The key must not be in this page.');
    return;
  }

  /* ------------------------------------------------------------ the code */

  /* Their endpoint, on their origin, carrying their login cookie. `include`
     rather than `same-origin` so an application whose API is on a sibling
     host still works — it is their fetch to their server either way, and a
     credential of ours is nowhere near it. */
  function getCode() {
    return fetch(CFG.codeUrl, {
      credentials: 'include',
      cache: 'no-store',
      headers: { 'Accept': 'application/json' },
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok || !j.code) {
          throw new Error(j.error || ('HTTP ' + r.status + ' from ' + CFG.codeUrl));
        }
        return j.code;
      });
    });
  }

  /* ----------------------------------------------------------- the frame */

  var frame = null;         // the iframe, once there is one
  var ready = false;        // …and once it has told us it is up
  var renewAt = 0;          // timer id for the next session renewal

  function makeFrame(code) {
    var f = document.createElement('iframe');
    f.src = ORIGIN + '/embed?c=' + encodeURIComponent(code);
    /* THE ONE EVERYBODY MISSES. Without this the microphone is refused inside
       the frame no matter what the key grants, no matter that the host page
       has permission, and the failure reads as a broken assistant rather than
       as a missing attribute. It is set here so nobody has to remember it. */
    f.setAttribute('allow', 'microphone');
    f.setAttribute('title', CFG.label);
    f.style.cssText = 'width:100%;height:100%;border:0;display:block;' +
                      'background:transparent;color-scheme:normal';
    return f;
  }

  /* --------------------------------------------------------- the renewal */

  /* A session stops at a time the admin chose. Renewing it by reloading the
     frame would be correct and would also throw away the conversation, which
     from the person's side is the assistant forgetting the last ten minutes
     for no reason they can see. So a fresh CODE is posted in instead and the
     frame swaps its token behind the scenes: same session length, same
     expiry, nothing lost.

     Early on purpose. Renewing with a minute to spare means a failure has a
     minute to be retried in, where renewing on the stroke means the first
     thing anybody notices is a question that did not go. */
  function scheduleRenew(seconds) {
    clearTimeout(renewAt);
    var wait = Math.max(30, (seconds || 0) - 60) * 1000;
    renewAt = setTimeout(function () {
      getCode().then(function (code) {
        if (frame && frame.contentWindow) {
          frame.contentWindow.postMessage({ rsn: 1, kind: 'renew', code: code },
                                          ORIGIN);
        }
      }).catch(function (e) {
        /* Said once, plainly. The session is still good for the minute this
           was scheduled ahead of, so this is a warning and not yet a fault. */
        console.warn('[resonance] could not renew the session: ' + e.message);
      });
    }, wait);
  }

  /* Only from our own frame and only from our own origin. A page that embeds
     this also embeds other things, and `event.source` is the half that says
     which of them is talking. */
  window.addEventListener('message', function (e) {
    if (!frame || e.source !== frame.contentWindow) return;
    if (e.origin !== ORIGIN) return;
    var m = e.data;
    if (!m || m.rsn !== 1) return;
    if (m.kind === 'ready' || m.kind === 'renewed') {
      ready = true;
      scheduleRenew(m.expires_in);
    }
  });

  /* ------------------------------------------------------------- mounting */

  var PANEL_CSS = [
    ':host{all:initial}',
    '*{box-sizing:border-box}',
    /* The launcher. Deliberately plain: it is going to sit on top of somebody
       else's design and a widget that arrives with opinions about their brand
       is a widget they turn off. */
    '.launch{position:fixed;bottom:20px;z-index:2147483000;',
    '  width:56px;height:56px;border-radius:50%;border:0;cursor:pointer;',
    '  background:#111;color:#fff;font:600 13px/1 system-ui,sans-serif;',
    '  box-shadow:0 4px 16px rgba(0,0,0,.28);display:grid;place-items:center;',
    '  transition:transform .15s ease}',
    '.launch:hover{transform:scale(1.06)}',
    '.launch:focus-visible{outline:2px solid #4c8dff;outline-offset:3px}',
    '.launch svg{width:24px;height:24px;fill:none;stroke:currentColor;',
    '  stroke-width:2;stroke-linecap:round}',
    '.panel{position:fixed;bottom:88px;z-index:2147483000;',
    '  border-radius:14px;overflow:hidden;background:#0b0b0c;',
    '  box-shadow:0 10px 40px rgba(0,0,0,.35);display:none}',
    '.panel.on{display:block}',
    /* A phone has no room for a floating card, so it stops being one. The
       breakpoint is the panel's own width rather than a device guess. */
    '@media (max-width:520px){',
    '  .panel{inset:0;bottom:0;width:auto!important;height:auto!important;',
    '    border-radius:0}',
    '  .launch{bottom:16px}}',
    '@media (prefers-reduced-motion:reduce){',
    '  .launch{transition:none}.launch:hover{transform:none}}',
  ].join('');

  var api = { open: noop, close: noop, toggle: noop, destroy: noop, frame: null };
  function noop() {}

  function mountInline(code) {
    var host = CFG.target ? document.querySelector(CFG.target) : null;
    if (!host) {
      console.error('[resonance] data-style="inline" needs data-target to name ' +
                    'an element that exists — "' + CFG.target + '" matched ' +
                    'nothing. If the element is created later, load embed.js ' +
                    'after it.');
      return;
    }
    frame = makeFrame(code);
    /* The host sizes the box; this fills it. A widget that decides how tall it
       is inside somebody else's layout is a widget that is the wrong height on
       every page but the one it was tested on. */
    if (!host.style.height && !host.clientHeight) host.style.height = CFG.height + 'px';
    host.appendChild(frame);
    api.frame = frame;
    api.destroy = function () {
      clearTimeout(renewAt);
      if (frame) frame.remove();
      frame = null;
    };
  }

  function mountBubble(code) {
    var root = document.createElement('div');
    /* Shadow DOM, and it is not decoration. This markup lands in a page whose
       CSS this project has never seen: a bare `button{}` rule in their sheet
       would otherwise restyle the launcher, and our rules would leak back out
       over their buttons. A closed root also means their script cannot reach
       in and move the frame somewhere it should not be. */
    var sh = root.attachShadow ? root.attachShadow({ mode: 'closed' }) : null;
    if (!sh) {
      console.error('[resonance] this browser has no shadow DOM, so the bubble ' +
                    'cannot be isolated from the page. Use data-style="inline".');
      return;
    }
    var style = document.createElement('style');
    style.textContent = PANEL_CSS;

    var panel = document.createElement('div');
    panel.className = 'panel';
    panel.style.width  = CFG.width + 'px';
    panel.style.height = CFG.height + 'px';
    panel.style[CFG.side] = '20px';

    var btn = document.createElement('button');
    btn.className = 'launch';
    btn.type = 'button';
    btn.style[CFG.side] = '20px';
    btn.setAttribute('aria-label', CFG.label);
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' +
                    '<path d="M21 12a8 8 0 0 1-8 8H8l-5 3 1.4-4.2A8 8 0 1 1 21 12z"/>' +
                    '</svg>';

    frame = makeFrame(code);
    panel.appendChild(frame);
    sh.appendChild(style);
    sh.appendChild(panel);
    sh.appendChild(btn);
    document.body.appendChild(root);

    function set(on) {
      panel.classList.toggle('on', on);
      btn.setAttribute('aria-expanded', on ? 'true' : 'false');
      /* Focus follows the panel, or a keyboard user opens something they then
         cannot reach. */
      if (on && frame) frame.focus();
    }
    btn.addEventListener('click', function () {
      set(!panel.classList.contains('on'));
    });
    /* Escape closes it, which is what every other overlay on the web does and
       therefore what somebody will try. Bound on the host document because a
       keypress inside the frame is the frame's own business. */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && panel.classList.contains('on')) set(false);
    });

    api.open    = function () { set(true); };
    api.close   = function () { set(false); };
    api.toggle  = function () { set(!panel.classList.contains('on')); };
    api.frame   = frame;
    api.destroy = function () {
      clearTimeout(renewAt);
      root.remove();
      frame = null;
    };
    if (CFG.open) set(true);
  }

  /* ---------------------------------------------------------------- start */

  function start() {
    getCode().then(function (code) {
      if (CFG.style === 'inline') mountInline(code);
      else mountBubble(code);
    }).catch(function (e) {
      /* Loudly, in the console, naming the address that failed. An integrator
         staring at a page with no bubble on it has nothing else to go on, and
         the three things that are actually wrong at this point — the endpoint
         is not there, it is not behind their login, or it refused because the
         key wants a person named — all say so in this line. */
      console.error('[resonance] could not start the embed: ' + e.message);
    });
  }

  /* The bubble needs a body to attach to; inline needs its target to exist.
     Both are satisfied by waiting, and a host that puts the tag in <head> is
     doing the ordinary thing rather than a wrong thing. */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  window.Resonance = api;
})();
