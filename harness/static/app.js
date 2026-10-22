const {screen, home, build, key, weather, tickClocks, svg} = window.GuardianCards;
const sid = (() => { try { return localStorage.guardianSid ||= crypto.randomUUID(); } catch { return crypto.randomUUID(); } })();
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const URL_RE = /(https?:\/\/\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\/\S*)/i;
const DEBUG = new URLSearchParams(location.search).get('debug') === '1';
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)');
const POLL_MS = 3000, VERIFY_GIVE_UP_MS = 120000, WEATHER_MS = 15 * 60000;

const root = screen();
document.getElementById('screen-slot').replaceWith(root);
const q = sel => root.querySelector(sel);
const view = q('[data-view]'), input = q('[data-input]'), line = q('[data-line]'), bar = q('[data-voicebar]');

let rec = null, busy = false, current = null, currentKey = null, polling = null, renderSeq = 0, unseen = 0;

/* ---------- transcript sheet and voice bar ---------- */
function addMsg(text, who) {
  const row = document.createElement('div');
  row.className = 'msg ' + who;
  const p = document.createElement('p');
  p.className = 'bubble';
  p.textContent = text;
  row.append(p);
  q('[data-transcript]').append(row);
  row.scrollIntoView({block: 'end', behavior: REDUCED.matches ? 'auto' : 'smooth'});
  if (who === 'bot' || who === 'user') setLine(text, who);
  return row;
}

function setLine(text, who) {
  line.textContent = who === 'user' ? `You: ${text}` : text;
}

function voice(state) {
  bar.classList.toggle('listening', state === 'listening');
  bar.classList.toggle('speaking', state === 'speaking');
  if (state === 'listening') line.textContent = 'Listening…';
}

function sheet(open, focus = false) {
  q('[data-sheet]').hidden = !open;
  q('[data-expand]').setAttribute('aria-expanded', String(open));
  root.classList.toggle('sheet-open', open);
  if (open) q('[data-transcript]').lastElementChild?.scrollIntoView({block: 'end'});
  if (open && focus) input.focus();
}

function speak(text) {
  if (!text || !('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.92;
  const pick = speechSynthesis.getVoices().find(v => /en[-_](US|GB)/.test(v.lang) && /Samantha|Google|Aria|Jenny|Serena|Daniel/.test(v.name));
  if (pick) u.voice = pick;
  u.onstart = () => { if (!rec) voice('speaking'); };
  u.onend = u.onerror = () => { if (!rec) voice(null); };
  speechSynthesis.speak(u);
}

function say(text) { if (text) { addMsg(text, 'bot'); speak(text); } }

/* ---------- view: home screen or a full-screen card ---------- */
const handlers = {
  action: (card, b) => runAction(card.action, b),
  next: (card, b) => { b.disabled = true; act('next_step', {incident_id: card.recovery.incident_id}).finally(() => { b.disabled = false; }); },
  repeat: card => say(card.recovery.text),
  home: () => render(null),
};

async function homeData() {
  try { return await (await fetch('/api/home')).json(); } catch { return {mcp_ok: false}; }
}

function familyChip(d) {
  // "Is it really <name>?" uses the first person in the family circle
  const name = d.family?.[0]?.name;
  const chip = q('[data-verify-chip]');
  if (!name || !chip) return;
  chip.dataset.say = `Is that really ${name} calling?`;
  chip.querySelector('span').textContent = `Is it really ${name}?`;
}

function render(card) {
  const k = key(card);
  const changed = k !== currentKey;
  current = card;
  currentKey = k;
  root.classList.toggle('on-home', !card);
  if (!card) { unseen = 0; bell(); }
  const next = card ? build(card, handlers) : home(lastHome);
  swap(next, changed);
  if (!card) homeData().then(d => { lastHome = d; familyChip(d); if (!current) swap(home(d), false); });
  watchVerification(card);
}
let lastHome = {};

function swap(next, animate) {
  const old = view.firstElementChild;
  const seq = ++renderSeq;
  if (!old || !animate || REDUCED.matches) { view.replaceChildren(next); return; }
  // 200 ms fade out, then the new view slides in (CSS .enter, 260 ms)
  old.classList.add('leave');
  setTimeout(() => { if (seq === renderSeq) { next.classList.add('enter'); view.replaceChildren(next); } }, 200);
}

function bell() {
  const c = q('.bell-count');
  c.hidden = !unseen;
  c.textContent = unseen;
  q('.bell').setAttribute('aria-label', unseen ? `Recent checks, ${unseen} new` : 'Recent checks');
}

function pendingCard(host) {
  render({kind: 'link', pending: true, domain: host, reasons: [], action: null});
}

/* ---------- caller check: poll until the family member answers ---------- */
function watchVerification(card) {
  const v = card?.kind === 'verify' ? card.verify : null;
  if (!v || v.status !== 'waiting') { clearTimeout(polling); polling = null; return; }
  if (polling) return;
  const poll = async () => {
    if (current?.verify?.id !== v.id || current.verify.status !== 'waiting') { polling = null; return; }
    if (Date.now() - v.started_at > VERIFY_GIVE_UP_MS) {
      polling = null;
      render({...current, verify: {...current.verify, status: 'no_reply'}});
      say(`${v.name} didn't answer. Don't send money. Call ${v.pronoun} back on the number you usually use.`);
      return;
    }
    try {
      const res = await post('/api/action', {tool: 'get_verification', args: {id: v.id}});
      if (res.card?.verify?.status && res.card.verify.status !== 'waiting') { polling = null; handle(res); return; }
    } catch { /* keep waiting; the network may come back */ }
    polling = setTimeout(poll, POLL_MS);
  };
  polling = setTimeout(poll, POLL_MS);
}

/* ---------- requests ---------- */
async function post(path, body) {
  const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
                               body: JSON.stringify({session_id: sid, ...body})});
  if (!r.ok) throw new Error('Server error ' + r.status);
  return r.json();
}

function handle(res) {
  typing(false);
  if (res.error && DEBUG) addMsg(res.error, 'err');
  if (res.card) {
    const finished = ['link', 'message'].includes(res.card.kind) && !res.card.pending && key(res.card) !== currentKey;
    if (finished) { unseen++; bell(); }
    render(res.card);
  }
  say(res.reply);
}

function typing(on) {
  q('.msg.typing')?.remove();
  if (on) { addMsg('', 'bot typing').querySelector('.bubble').innerHTML = '<i></i><i></i><i></i>'; line.textContent = 'Thinking…'; }
}

async function send(text) {
  text = text.trim();
  if (!text || busy) return;
  busy = true;
  addMsg(text, 'user');
  input.value = '';
  const url = text.match(URL_RE);
  if (url) {
    let host = '';
    try { host = new URL(/^https?:/i.test(url[0]) ? url[0] : 'http://' + url[0]).hostname; } catch { /* leave blank */ }
    pendingCard(host);
  }
  typing(true);
  try { handle(await post('/api/chat', {message: text})); }
  catch (e) { typing(false); say("I can't reach my safety checks right now. If someone is asking for money, hang up and call family."); if (DEBUG) addMsg(e.message, 'err'); }
  busy = false;
}

async function act(tool, args) {
  try {
    const res = await post('/api/action', {tool, args});
    if (res.error && DEBUG) addMsg(res.error, 'err');
    if (res.card) render(res.card);
    say(res.reply);
    return res;
  } catch (e) { say("Sorry, I couldn't do that just now."); if (DEBUG) addMsg(e.message, 'err'); }
}

async function runAction(a, b) {
  if (!a) return;
  b.disabled = true;
  if (a.tool !== 'alert_family') { await act(a.tool, a.args); return; }
  // The alert doesn't change the card, so mark this button instead of re-rendering it.
  try {
    const res = await post('/api/action', {tool: a.tool, args: a.args});
    say(res.reply);
    const told = res.trace?.[0]?.result;
    if (!told?.sent) { b.disabled = false; return; }
    const names = told.recipients;
    b.classList.add('is-done');
    b.innerHTML = `${svg('i-check')}<span>Told ${names.length === 1 ? names[0] : names.slice(0, -1).join(', ') + ' and ' + names.at(-1)}</span>`;
  } catch (e) { say("Sorry, I couldn't do that just now."); b.disabled = false; if (DEBUG) addMsg(e.message, 'err'); }
}

/* ---------- inputs ---------- */
q('[data-form]').onsubmit = e => { e.preventDefault(); send(input.value); };
root.querySelectorAll('[data-say]').forEach(b => { b.onclick = () => send(b.dataset.say); });
root.querySelectorAll('[data-nav="home"]').forEach(b => { b.onclick = () => { sheet(false); render(null); }; });
q('[data-expand]').onclick = () => sheet(q('[data-sheet]').hidden);
q('[data-type]').onclick = () => sheet(true, true);
q('[data-collapse]').onclick = () => sheet(false);

const mic = q('[data-mic]');
if (!SR) {
  mic.disabled = true;
  mic.title = 'Speaking needs Chrome or Edge. You can type instead.';
} else {
  mic.onclick = () => {
    if (rec) { rec.stop(); return; }
    speechSynthesis.cancel();
    rec = new SR();
    rec.lang = 'en-US';
    rec.interimResults = true;
    let final = '';
    rec.onresult = e => {
      const r = e.results[e.results.length - 1];
      if (r.isFinal) final = r[0].transcript; else line.textContent = r[0].transcript;
    };
    rec.onend = rec.onerror = () => {
      mic.classList.remove('live');
      mic.setAttribute('aria-pressed', 'false');
      mic.setAttribute('aria-label', 'Tap and speak');
      rec = null;
      voice(null);
      if (final) send(final); else line.textContent = 'Tap the mic and ask me anything.';
    };
    mic.classList.add('live');
    mic.setAttribute('aria-pressed', 'true');
    mic.setAttribute('aria-label', 'Listening. Tap to stop');
    voice('listening');
    rec.start();
  };
}

/* ---------- top bar: clock, weather, debug chips ---------- */
render(null);
tickClocks(root);
setInterval(() => tickClocks(root), 1000);

async function loadWeather() {
  try {
    const w = await (await fetch('/api/weather')).json();
    const el = q('[data-weather]');
    el.hidden = !w;
    el.innerHTML = weather(w);
  } catch { /* the top bar simply shows no weather */ }
}
loadWeather();
setInterval(loadWeather, WEATHER_MS);

if (DEBUG) {
  q('[data-conn]').hidden = false;
  fetch('/api/health').then(r => r.json()).then(h => {
    if (!h.mcp_ok) throw new Error('MCP server unreachable');
    q('[data-conn]').classList.add('ok');
    q('[data-conn-text]').textContent = `Connected · ${h.tools} tools`;
    q('[data-mode]').hidden = false;
    q('[data-mode]').textContent = h.mode === 'bedrock' ? 'Bedrock agent' : 'Mock agent';
  }).catch(() => { q('[data-conn]').classList.add('down'); q('[data-conn-text]').textContent = 'Offline'; });
}

if ('speechSynthesis' in window) speechSynthesis.getVoices();
