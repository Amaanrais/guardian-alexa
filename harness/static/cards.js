/* Guardian cards: one renderer shared by the live page (app.js) and /demo (demo.js).
   Card shapes come from harness/card.py. Every state carries an icon and words, never colour alone. */
(() => {
  const SPRITE = `
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <symbol id="i-shield" viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10v-6l-8-3Z"/></symbol>
  <symbol id="i-shield-check" viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10v-6l-8-3Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/></symbol>
  <symbol id="i-octagon" viewBox="0 0 24 24"><path d="M8 2.5h8l5.5 5.5v8L16 21.5H8L2.5 16V8Z"/><path d="M12 7.5v5.5M12 16.5h.01"/></symbol>
  <symbol id="i-triangle" viewBox="0 0 24 24"><path d="M10.3 3.9 2.2 18a2 2 0 0 0 1.7 3h16.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4.5M12 17h.01"/></symbol>
  <symbol id="i-info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></symbol>
  <symbol id="i-mic" viewBox="0 0 24 24"><rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3.5"/></symbol>
  <symbol id="i-send" viewBox="0 0 24 24"><path d="M4 12h15M13 6l6 6-6 6"/></symbol>
  <symbol id="i-link" viewBox="0 0 24 24"><path d="M10 13.5a4.5 4.5 0 0 0 6.4.4l2.9-2.9a4.5 4.5 0 0 0-6.4-6.4L11.5 6"/><path d="M14 10.5a4.5 4.5 0 0 0-6.4-.4L4.7 13a4.5 4.5 0 0 0 6.4 6.4l1.4-1.4"/></symbol>
  <symbol id="i-phone" viewBox="0 0 24 24"><path d="M21 16.5v3a2 2 0 0 1-2.2 2A19.5 19.5 0 0 1 2.5 5.2 2 2 0 0 1 4.5 3h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.4 10.9a16 16 0 0 0 4.7 4.7l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/></symbol>
  <symbol id="i-phone-off" viewBox="0 0 24 24"><path d="M21 16.5v3a2 2 0 0 1-2.2 2A19.5 19.5 0 0 1 2.5 5.2 2 2 0 0 1 4.5 3h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.4 10.9a16 16 0 0 0 4.7 4.7l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/><path d="m15 3 6 6M21 3l-6 6"/></symbol>
  <symbol id="i-lifebuoy" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.5"/><circle cx="12" cy="12" r="4"/><path d="m5.3 5.3 3.9 3.9M14.8 14.8l3.9 3.9M14.8 9.2l3.9-3.9M5.3 18.7l3.9-3.9"/></symbol>
  <symbol id="i-lock" viewBox="0 0 24 24"><rect x="4.5" y="10.5" width="15" height="11" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/></symbol>
  <symbol id="i-users" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20.5a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14.3a6.5 6.5 0 0 1 3 6.2"/></symbol>
  <symbol id="i-box" viewBox="0 0 24 24"><path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="m3 8 9 5 9-5M12 13v8"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></symbol>
  <symbol id="i-globe" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.6 2.7 4 6 4 9.5s-1.4 6.8-4 9.5c-2.6-2.7-4-6-4-9.5s1.4-6.8 4-9.5Z"/></symbol>
  <symbol id="i-volume" viewBox="0 0 24 24"><path d="M11 5 6 9H3v6h3l5 4Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/></symbol>
  <symbol id="i-arrow" viewBox="0 0 24 24"><path d="M4 12h15M13 6l6 6-6 6"/></symbol>
  <symbol id="i-mask" viewBox="0 0 24 24"><path d="M3 6.5c3-1.5 6-2 9-2s6 .5 9 2c0 6.5-3.5 12-9 13-5.5-1-9-6.5-9-13Z"/><path d="M7.5 11c.8-.8 2.2-.8 3 0M13.5 11c.8-.8 2.2-.8 3 0M9.5 15.5c1.5 1 3.5 1 5 0"/></symbol>
  <symbol id="i-message" viewBox="0 0 24 24"><path d="M20.5 12a8.5 8.5 0 0 1-12.4 7.5L3.5 21l1.5-4.4A8.5 8.5 0 1 1 20.5 12Z"/></symbol>
</defs></svg>`;
  document.body.insertAdjacentHTML('afterbegin', SPRITE);

  const svg = id => `<svg aria-hidden="true"><use href="#${id}"/></svg>`;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const wave = () => '<span class="wave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>';
  const elapsed = ms => { const s = Math.max(0, Math.floor(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };

  const LEVEL_ICON = {red: 'i-octagon', amber: 'i-triangle', grey: 'i-info'};
  const EYEBROW = {link: 'Link check', message: 'Message check', verify: 'Caller check', recovery: 'Recovery'};
  const LOADING = 'Checking it safely… about 10 seconds';

  function head(tone, icon, eyebrow, title) {
    return `<header class="card-head">
      <span class="badge">${svg(icon)}</span>
      <div><p class="eyebrow">${esc(eyebrow)}</p><h2 class="card-title">${title}</h2></div>
    </header>`;
  }

  function button(label, icon, cls, data) {
    return `<button type="button" class="btn ${cls}" data-do="${data}">${svg(icon)}<span>${esc(label)}</span></button>`;
  }

  /* ---------- link and message verdicts ---------- */
  function verdict(c) {
    const pending = !!c.pending;
    const tone = pending ? 'calm' : c.level;
    const parts = [];
    if (c.injection && !pending) {
      parts.push(`<div class="ai-banner" role="alert">${svg('i-mask')}<div>
        <strong>This page tried to fool the AI</strong>
        <span>Guardian ignored its hidden instructions.</span></div></div>`);
    }
    parts.push(head(tone, pending ? 'i-shield' : LEVEL_ICON[c.level] || 'i-info',
      EYEBROW[c.kind] || 'Check', esc(pending ? 'Checking this link' : c.title)));
    parts.push('<div class="card-body">');
    if (c.kind === 'link' && (pending || c.screenshot_url)) {
      const img = c.screenshot_url
        ? `<img src="${esc(c.screenshot_url)}" alt="Picture of ${esc(c.domain || 'the page')}, taken in a sealed sandbox">` : '';
      parts.push(`<figure class="browser">
        <div class="browser-bar"><span class="lights" aria-hidden="true"><i></i><i></i><i></i></span>
          <span class="address">${svg('i-globe')}<span class="address-text">${esc(c.domain || 'Unknown website')}</span></span></div>
        <div class="browser-view">${img}<div class="scan" aria-hidden="true"></div>
          <figcaption class="sandbox-tag">${svg('i-box')}Opened in a sealed sandbox</figcaption></div>
      </figure>`);
    }
    if (pending) {
      parts.push(`<p class="loading" role="status">${wave()}<span>${LOADING}</span></p>`);
    } else if (c.reasons?.length) {
      parts.push(`<ol class="reasons">${c.reasons.slice(0, 3).map(r => `<li>${esc(r)}</li>`).join('')}</ol>`);
    } else if (c.level === 'grey') {
      parts.push(`<p class="calm-note">${svg('i-info')}Nothing worrying turned up. Still, never share a code or PIN.</p>`);
    }
    parts.push('</div>');
    if (!pending && c.action) {
      const icon = c.action.tool === 'start_incident' ? 'i-lifebuoy' : 'i-users';
      parts.push(`<footer class="card-foot">${button(c.action.label, icon, 'btn-primary', 'action')}</footer>`);
    }
    return {tone, html: parts.join('')};
  }

  /* ---------- verify caller ---------- */
  function verify(c) {
    const v = c.verify, name = esc(v.name), obj = esc(v.pronoun || 'them');
    const s = {
      waiting: {tone: 'calm', icon: 'i-phone', title: `Asking ${name}… <span class="timer" data-start="${v.started_at}">${elapsed(Date.now() - v.started_at)}</span>`,
                lead: "Stay calm. Don't share any codes or send money while we wait."},
      confirmed: {tone: 'green', icon: 'i-check', title: `${name} confirmed it's ${obj}.`,
                  lead: 'Even so, never share a code or PIN.'},
      denied: {tone: 'red', icon: 'i-x', title: `${name} says it isn't ${obj}.`, lead: '<strong>Hang up now.</strong>'},
      no_reply: {tone: 'amber', icon: 'i-phone-off', title: `${name} didn't answer.`,
                 lead: `<strong>Don't send money.</strong> Call ${obj} back on the number you usually use.`},
    }[v.status] || {};
    return {tone: s.tone, html: `
      <div class="card-body verify-body">
        <p class="eyebrow">${EYEBROW.verify}</p>
        <div class="verify-mark ${v.status === 'waiting' ? 'is-waiting' : ''}">
          <span class="pulse" aria-hidden="true"></span><span class="pulse" aria-hidden="true"></span>
          <span class="verify-icon">${svg(s.icon)}</span>
        </div>
        <h2 class="card-title">${s.title}</h2>
        <p class="lead">${s.lead}</p>
      </div>`};
  }

  /* ---------- recovery ---------- */
  function recovery(c) {
    const r = c.recovery;
    const dots = r.total ? `<ol class="dots" aria-hidden="true">${Array.from({length: r.total}, (_, i) =>
      `<li class="${i + 1 < r.index || r.done ? 'done' : i + 1 === r.index ? 'current' : ''}"></li>`).join('')}</ol>` : '';
    if (r.done) {
      const foot = !r.family_told && c.action ? `<footer class="card-foot">${button(c.action.label, 'i-users', 'btn-primary', 'action')}</footer>` : '';
      return {tone: 'green', html: `${head('green', 'i-check', EYEBROW.recovery, "You've done everything on the list.")}
        <div class="card-body">${dots}${r.family_told ? `<p class="step-text">${svg('i-users')}Your family has been told.</p>` : ''}</div>${foot}`};
    }
    const label = `Step ${r.index}${r.total ? ` of ${r.total}` : ''}`;
    return {tone: 'calm', html: `${head('calm', 'i-lifebuoy', EYEBROW.recovery, esc(label))}
      <div class="card-body">${dots}<p class="step-text">${esc(r.text)}</p></div>
      <footer class="card-foot">
        ${button('Done, next step', 'i-check', 'btn-primary', 'next')}
        ${button('Say it again', 'i-volume', 'btn-secondary', 'repeat')}
      </footer>`};
  }

  /** Build a card element. `on` = {action(card, btn), next(card, btn), repeat(card, btn)}. */
  function build(card, on = {}) {
    const kind = card.kind || 'link';
    const {tone, html} = kind === 'verify' ? verify(card) : kind === 'recovery' ? recovery(card) : verdict(card);
    const el = document.createElement('article');
    el.className = `card tone-${tone} kind-${kind}${card.pending ? ' is-pending' : ''}`;
    el.innerHTML = html;
    el.querySelectorAll('[data-do]').forEach(b => {
      const fn = on[b.dataset.do];
      b.onclick = () => fn && fn(card, b);
    });
    return el;
  }

  /** A stable identity for a card's visible state, so re-renders of the same state don't re-animate. */
  function key(c) {
    if (!c) return 'idle';
    return JSON.stringify([c.kind, c.level, c.pending, c.title, c.verify?.status, c.recovery?.index, c.recovery?.done]);
  }

  function idle() {
    const el = document.createElement('div');
    el.className = 'idle';
    el.innerHTML = `<time class="idle-clock" data-clock><span data-hm></span><span class="ampm" data-ampm></span></time><p class="idle-date" data-date></p>
      <p class="idle-line">Ask me about anything that feels off.</p>`;
    tickClocks(el);
    return el;
  }

  /** Update every live clock and verify timer inside `root`. */
  function tickClocks(root = document) {
    const now = new Date();
    const parts = new Intl.DateTimeFormat([], {hour: 'numeric', minute: '2-digit'}).formatToParts(now);
    const hm = parts.filter(p => p.type !== 'dayPeriod').map(p => p.value).join('').trim();
    const ampm = parts.find(p => p.type === 'dayPeriod')?.value || '';
    root.querySelectorAll('[data-clock]').forEach(t => {
      const h = t.querySelector('[data-hm]');
      if (h) { h.textContent = hm; t.querySelector('[data-ampm]').textContent = ampm; } else t.textContent = `${hm} ${ampm}`.trim();
      t.dateTime = now.toISOString();
    });
    root.querySelectorAll('[data-date]').forEach(d => { d.textContent = now.toLocaleDateString([], {weekday: 'long', day: 'numeric', month: 'long'}); });
    root.querySelectorAll('.timer[data-start]').forEach(t => { t.textContent = elapsed(Date.now() - Number(t.dataset.start)); });
  }

  window.GuardianCards = {build, key, idle, tickClocks, svg, wave};
})();
