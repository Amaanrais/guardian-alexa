/* Guardian screen and cards: one renderer shared by the live page (app.js) and /demo (demo.js).
   Card shapes come from harness/card.py. Every state carries an icon and words, never colour alone. */
(() => {
  const SPRITE = `
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <symbol id="i-shield" viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10v-6l-8-3Z"/></symbol>
  <symbol id="i-shield-check" viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10v-6l-8-3Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/></symbol>
  <symbol id="i-shield-alert" viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10v-6l-8-3Z"/><path d="M12 8v4.5M12 16h.01"/></symbol>
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
  <symbol id="i-mask" viewBox="0 0 24 24"><path d="M3 6.5c3-1.5 6-2 9-2s6 .5 9 2c0 6.5-3.5 12-9 13-5.5-1-9-6.5-9-13Z"/><path d="M7.5 11c.8-.8 2.2-.8 3 0M13.5 11c.8-.8 2.2-.8 3 0M9.5 15.5c1.5 1 3.5 1 5 0"/></symbol>
  <symbol id="i-menu" viewBox="0 0 24 24"><path d="M5 7h14M5 12h10M5 17h7"/></symbol>
  <symbol id="i-bell" viewBox="0 0 24 24"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15Z"/><path d="M10 20.5a2 2 0 0 0 4 0"/></symbol>
  <symbol id="i-home" viewBox="0 0 24 24"><path d="M3.5 11 12 4l8.5 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5.5h4V20"/></symbol>
  <symbol id="i-keyboard" viewBox="0 0 24 24"><rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7.5 14h9"/></symbol>
  <symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"/></symbol>
  <symbol id="i-cloud" viewBox="0 0 24 24"><path d="M7 18.5a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.4 1.6A4 4 0 0 1 17.5 18.5Z"/></symbol>
  <symbol id="i-partly" viewBox="0 0 24 24"><path d="M8 3v1.5M3 8h1.5M4.5 4.5l1 1M11.5 4.5l-1 1"/><path d="M5.6 10.2A3.5 3.5 0 0 1 11 6.6"/><path d="M9 19.5a3.8 3.8 0 0 1-.5-7.6 5 5 0 0 1 9.6 1.4 3.2 3.2 0 0 1-.6 6.2Z"/></symbol>
  <symbol id="i-rain" viewBox="0 0 24 24"><path d="M7 15.5a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.4 1.6A4 4 0 0 1 17.5 15.5Z"/><path d="M8 18.5l-1 2.5M12 18.5l-1 2.5M16 18.5l-1 2.5"/></symbol>
  <symbol id="i-snow" viewBox="0 0 24 24"><path d="M7 15.5a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.4 1.6A4 4 0 0 1 17.5 15.5Z"/><path d="M8 19h.01M12 20.5h.01M16 19h.01"/></symbol>
  <symbol id="i-fog" viewBox="0 0 24 24"><path d="M4 9h16M3 13h18M5 17h14"/></symbol>
  <symbol id="i-storm" viewBox="0 0 24 24"><path d="M7 15.5a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.4 1.6A4 4 0 0 1 17.5 15.5Z"/><path d="m12.5 14-2 3.5h3l-2 3.5"/></symbol>
  <symbol id="i-chevron-up" viewBox="0 0 24 24"><path d="m6 15 6-6 6 6"/></symbol>
  <symbol id="i-arrow" viewBox="0 0 24 24"><path d="M4 12h15M13 6l6 6-6 6"/></symbol>
</defs></svg>`;
  document.body.insertAdjacentHTML('afterbegin', SPRITE);

  const svg = id => `<svg aria-hidden="true"><use href="#${id}"/></svg>`;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const wave = () => '<span class="wave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>';
  const elapsed = ms => { const s = Math.max(0, Math.floor(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  const html = s => { const t = document.createElement('template'); t.innerHTML = s.trim(); return t.content.firstElementChild; };

  const LEVEL_ICON = {red: 'i-octagon', amber: 'i-triangle', grey: 'i-info'};
  const SHORT = {red: "Don't open", amber: 'Be careful', grey: 'No red flags'};
  const EYEBROW = {link: 'Link check', message: 'Message check', verify: 'Caller check', recovery: 'Recovery'};
  const LOADING = 'Checking it safely… about 10 seconds';

  /* ---------- the screen: top bar, view, suggestions, voice bar, transcript sheet ---------- */
  function screen() {
    return html(`<div class="screen">
      <header class="topbar">
        <div class="topbar-left">
          <button type="button" class="round" data-nav="home" aria-label="Home">${svg('i-menu')}</button>
          <button type="button" class="round bell" data-nav="home" aria-label="Recent checks">${svg('i-bell')}<span class="bell-count" hidden></span></button>
        </div>
        <div class="topbar-right">
          <span class="chip debug" data-conn hidden><span class="dot"></span><span data-conn-text>Connecting…</span></span>
          <span class="chip debug" data-mode hidden></span>
          <span class="weather" data-weather hidden></span>
          <time class="clock" data-clock></time>
        </div>
      </header>
      <div class="view" data-view></div>
      <div class="suggestions" data-suggestions aria-label="Things you can say">
        <button type="button" class="suggest" data-say="Is this a scam? http://secure-bank.example/login">${svg('i-link')}Check a link</button>
        <button type="button" class="suggest" data-say="Is that really Rahul calling?" data-verify-chip>${svg('i-phone')}<span>Is it really Rahul?</span></button>
        <button type="button" class="suggest" data-say="I gave someone my bank code">${svg('i-lifebuoy')}I shared a code</button>
      </div>
      <div class="voicebar" data-voicebar>
        <button type="button" class="vb-mic" data-mic aria-label="Tap and speak" aria-pressed="false">${svg('i-mic')}</button>
        <button type="button" class="vb-line" data-expand aria-expanded="false" aria-controls="sheet">
          ${wave()}<span class="vb-text" data-line>Tap the mic and ask me anything.</span>${svg('i-chevron-up')}
        </button>
        <button type="button" class="vb-type" data-type>${svg('i-keyboard')}<span>Type</span></button>
      </div>
      <section class="sheet" id="sheet" data-sheet aria-label="Conversation" hidden>
        <header class="sheet-head"><h2>Conversation</h2>
          <button type="button" class="btn btn-quiet" data-collapse>${svg('i-x')}<span>Close</span></button></header>
        <div class="transcript" data-transcript role="log" aria-live="polite" aria-relevant="additions"></div>
        <form class="composer" data-form>
          <label class="sr-only" for="text">Type or paste a message</label>
          <input id="text" data-input type="text" autocomplete="off" placeholder="Type or paste a message">
          <button type="submit" class="send" aria-label="Send">${svg('i-send')}</button>
        </form>
      </section>
    </div>`);
  }

  /* ---------- home: three glass cards ---------- */
  function home(d = {}) {
    const n = d.checks_this_week ?? 0;
    const ok = d.mcp_ok !== false;
    const guardian = ok
      ? `<span class="home-mark">${svg('i-shield-check')}</span><h2 class="home-title">You're protected</h2>
         <p class="home-sub">${n === 1 ? '1 check' : `${n} checks`} this week</p>`
      : `<span class="home-mark warn">${svg('i-shield-alert')}</span><h2 class="home-title">Checks are offline</h2>
         <p class="home-sub">If someone asks for money, hang up and call family.</p>`;
    const family = (d.family || []).length
      ? `<ul class="family">${d.family.map(p => `<li><span class="avatar-initial" aria-hidden="true">${esc(p.initial)}</span><span>${esc(p.name)}</span></li>`).join('')}</ul>`
      : '<p class="home-empty">No one has joined yet. Family members join by messaging the Guardian bot.</p>';
    const ready = d.verify_ready
      ? `${svg('i-phone')}Ready to verify calls` : `${svg('i-info')}Call checks aren't set up yet`;
    const recent = (d.recent || []).length
      ? `<ul class="recent">${d.recent.map(r => `<li class="lvl-${esc(r.level)}">${svg(LEVEL_ICON[r.level] || 'i-info')}
          <span><b>${esc(SHORT[r.level] || r.title)}</b><span>${esc(r.label)}</span></span></li>`).join('')}</ul>`
      : '<p class="home-empty">No checks yet. Ask me about a link or a message.</p>';
    return html(`<div class="home">
      <div class="home-cards">
        <article class="glass home-card home-guardian"><p class="home-label">Guardian</p>${guardian}</article>
        <article class="glass home-card"><p class="home-label">Family circle</p>${family}
          <p class="home-foot ${d.verify_ready ? '' : 'muted'}">${ready}</p></article>
        <article class="glass home-card"><p class="home-label">Recent checks</p>${recent}</article>
      </div>
      <div class="page-dots" aria-hidden="true"><i class="on"></i><i></i></div>
    </div>`);
  }

  /* ---------- result cards ---------- */
  const homeButton = () => `<button type="button" class="btn btn-quiet btn-home" data-do="home">${svg('i-home')}<span>Home</span></button>`;
  const button = (label, icon, cls, data) => `<button type="button" class="btn ${cls}" data-do="${data}">${svg(icon)}<span>${esc(label)}</span></button>`;
  const head = (icon, eyebrow, title) => `<header class="card-head">
      <span class="badge">${svg(icon)}</span>
      <div class="card-heading"><p class="eyebrow">${esc(eyebrow)}</p><h2 class="card-title">${title}</h2></div>
      ${homeButton()}
    </header>`;

  function verdict(c) {
    const pending = !!c.pending;
    const tone = pending ? 'calm' : c.level;
    const banner = c.injection && !pending ? `<div class="ai-banner" role="alert">${svg('i-mask')}<div>
        <strong>This page tried to fool the AI</strong><span>Guardian ignored its hidden instructions.</span></div></div>` : '';
    const shot = c.kind === 'link' && (pending || c.screenshot_url);
    const browser = shot ? `<figure class="browser">
        <div class="browser-bar"><span class="lights" aria-hidden="true"><i></i><i></i><i></i></span>
          <span class="address">${svg('i-globe')}<span class="address-text">${esc(c.domain || 'Unknown website')}</span></span></div>
        <div class="browser-view">${c.screenshot_url ? `<img src="${esc(c.screenshot_url)}" alt="Picture of ${esc(c.domain || 'the page')}, taken in a sealed sandbox">` : ''}
          <div class="scan" aria-hidden="true"></div>
          <figcaption class="sandbox-tag">${svg('i-box')}Opened in a sealed sandbox</figcaption></div>
      </figure>` : '';
    let side;
    if (pending) side = `<p class="loading" role="status">${wave()}<span>${LOADING}</span></p>`;
    else if (c.reasons?.length) side = `<ol class="reasons">${c.reasons.slice(0, 3).map(r => `<li>${esc(r)}</li>`).join('')}</ol>`;
    else side = `<p class="calm-note">${svg('i-info')}Nothing worrying turned up. Still, never share a code or PIN.</p>`;
    const action = !pending && c.action
      ? button(c.action.label, c.action.tool === 'start_incident' ? 'i-lifebuoy' : 'i-users', 'btn-primary', 'action') : '';
    return {tone, body: `${banner}${head(pending ? 'i-shield' : LEVEL_ICON[c.level] || 'i-info', EYEBROW[c.kind] || 'Check',
      esc(pending ? 'Checking this link' : c.title))}
      <div class="card-body ${shot ? 'split' : ''}">${browser}<div class="card-side">${side}${action ? `<div class="card-actions">${action}</div>` : ''}</div></div>`};
  }

  function verify(c) {
    const v = c.verify, name = esc(v.name), obj = esc(v.pronoun || 'them');
    const s = {
      waiting: {tone: 'calm', icon: 'i-phone', title: `Asking ${name}… <span class="timer" data-start="${v.started_at}">${elapsed(Date.now() - v.started_at)}</span>`,
                lead: "Stay calm. Don't share any codes or send money while we wait."},
      confirmed: {tone: 'green', icon: 'i-check', title: `${name} confirmed it's ${obj}.`, lead: 'Even so, never share a code or PIN.'},
      denied: {tone: 'red', icon: 'i-x', title: `${name} says it isn't ${obj}.`, lead: '<strong>Hang up now.</strong>'},
      no_reply: {tone: 'amber', icon: 'i-phone-off', title: `${name} didn't answer.`,
                 lead: `<strong>Don't send money.</strong> Call ${obj} back on the number you usually use.`},
    }[v.status] || {};
    return {tone: s.tone, body: `<div class="card-corner">${homeButton()}</div>
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

  function recovery(c) {
    const r = c.recovery;
    if (r.question) {
      // step_number 0: one clarifying question, answered by voice or with a button
      const choices = (r.choices || []).map((a, i) =>
        `<button type="button" class="btn ${i ? 'btn-secondary' : 'btn-primary'}" data-choice="${i}">${svg(i ? 'i-link' : 'i-lifebuoy')}<span>${esc(a.label)}</span></button>`).join('');
      return {tone: 'calm', body: `${head('i-lifebuoy', EYEBROW.recovery, esc(r.question))}
        <div class="card-body recovery-body"><p class="step-hint">${svg('i-mic')}Tap an answer, or just tell me what happened.</p>
          <div class="card-actions two">${choices}</div></div>`};
    }
    const dots = r.total ? `<ol class="dots" aria-hidden="true">${Array.from({length: r.total}, (_, i) =>
      `<li class="${i + 1 < r.index || r.done ? 'done' : i + 1 === r.index ? 'current' : ''}"></li>`).join('')}</ol>` : '';
    if (r.done) {
      const told = r.family_told ? `<p class="step-text">${svg('i-users')}Your family has been told.</p>` : '';
      const act = !r.family_told && c.action ? `<div class="card-actions">${button(c.action.label, 'i-users', 'btn-primary', 'action')}</div>` : '';
      return {tone: 'green', body: `${head('i-check', EYEBROW.recovery, "You've done everything on the list.")}
        <div class="card-body recovery-body">${dots}${told}${act}</div>`};
    }
    return {tone: 'calm', body: `${head('i-lifebuoy', EYEBROW.recovery, esc(`Step ${r.index}${r.total ? ` of ${r.total}` : ''}`))}
      <div class="card-body recovery-body">${dots}<p class="step-text">${esc(r.text)}</p>
        <div class="card-actions two">
          ${c.action ? `<div class="span-2">${button(c.action.label, c.action.tool === 'alert_family' ? 'i-users' : 'i-arrow', 'btn-secondary', 'action')}</div>` : ''}
          ${button('Done, next step', 'i-check', 'btn-primary', 'next')}
          ${button('Say it again', 'i-volume', 'btn-secondary', 'repeat')}
        </div></div>`};
  }

  /** Build a full-screen card. `on` = {action, next, repeat, home} handlers, each (card, button). */
  function build(card, on = {}) {
    const kind = card.kind || 'link';
    const {tone, body} = kind === 'verify' ? verify(card) : kind === 'recovery' ? recovery(card) : verdict(card);
    const el = document.createElement('article');
    el.className = `card glass tone-${tone} kind-${kind}${card.pending ? ' is-pending' : ''}`;
    el.innerHTML = body;
    el.querySelectorAll('[data-do]').forEach(b => {
      const fn = on[b.dataset.do];
      b.onclick = () => fn && fn(card, b);
    });
    el.querySelectorAll('[data-choice]').forEach(b => {
      const choice = card.recovery.choices[Number(b.dataset.choice)];
      b.onclick = () => on.action && on.action({...card, action: choice}, b);
    });
    return el;
  }

  /** A stable identity for a card's visible state, so re-renders of the same state don't re-animate. */
  function key(c) {
    if (!c) return 'home';
    return JSON.stringify([c.kind, c.level, c.pending, c.title, c.verify?.status, c.recovery?.index, c.recovery?.done, c.recovery?.question]);
  }

  function weather(w) {
    if (!w) return '';
    return `${svg('i-' + w.icon)}<span class="temp">${w.temp}°</span><span class="sr-only">${esc(w.words)}</span>`;
  }

  /** Update every clock and caller-check timer inside `root`. */
  function tickClocks(root = document) {
    const now = new Date();
    const hm = new Intl.DateTimeFormat([], {hour: 'numeric', minute: '2-digit'}).formatToParts(now)
      .filter(p => p.type !== 'dayPeriod').map(p => p.value).join('').trim();
    root.querySelectorAll('[data-clock]').forEach(t => { t.textContent = hm; t.dateTime = now.toISOString(); });
    root.querySelectorAll('.timer[data-start]').forEach(t => { t.textContent = elapsed(Date.now() - Number(t.dataset.start)); });
  }

  window.GuardianCards = {screen, home, build, key, weather, tickClocks, svg, wave};
})();
