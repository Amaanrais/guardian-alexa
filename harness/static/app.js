const $ = id => document.getElementById(id);
const {build, key, idle, tickClocks, svg} = window.GuardianCards;
const sid = (() => { try { return localStorage.guardianSid ||= crypto.randomUUID(); } catch { return crypto.randomUUID(); } })();
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const URL_RE = /(https?:\/\/\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\/\S*)/i;
const DEBUG = new URLSearchParams(location.search).get('debug') === '1';
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)');
const POLL_MS = 3000, VERIFY_GIVE_UP_MS = 120000;
let rec = null, busy = false, current = null, currentKey = null, polling = null, renderSeq = 0;

/* ---------- transcript ---------- */
function addMsg(text, who) {
  const row = document.createElement('div');
  row.className = 'msg ' + who;
  if (who !== 'user') row.innerHTML = `<span class="avatar" aria-hidden="true">${svg('i-shield')}</span>`;
  const p = document.createElement('p');
  p.className = 'bubble';
  p.textContent = text;
  row.append(p);
  $('transcript').append(row);
  row.scrollIntoView({block: 'end', behavior: REDUCED.matches ? 'auto' : 'smooth'});
  return row;
}

function typing(on) {
  document.querySelector('.msg.typing')?.remove();
  if (on) addMsg('', 'bot typing').querySelector('.bubble').innerHTML = '<i></i><i></i><i></i>';
}

function interim(text) {
  let row = document.querySelector('.msg.interim');
  if (!text) { row?.remove(); return; }
  row ||= addMsg('', 'user interim');
  row.querySelector('.bubble').textContent = text;
}

/* ---------- voice: waveform while listening or speaking ---------- */
function voice(state) {
  const v = $('voice');
  v.hidden = !state;
  $('text').hidden = !!state;
  v.className = 'voice' + (state ? ' ' + state : '');
  $('voice-text').textContent = state === 'listening' ? 'Listening…' : 'Guardian is speaking…';
}

function speak(text, row) {
  if (!text || !('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.92;
  const pick = speechSynthesis.getVoices().find(v => /en[-_]US/.test(v.lang) && /Samantha|Google US|Aria|Jenny/.test(v.name));
  if (pick) u.voice = pick;
  const av = row?.querySelector('.avatar');
  u.onstart = () => { av?.classList.add('speaking'); if (!rec) voice('speaking'); };
  u.onend = u.onerror = () => { av?.classList.remove('speaking'); if (!rec) voice(null); };
  speechSynthesis.speak(u);
}

function say(text) { if (text) speak(text, addMsg(text, 'bot')); }

/* ---------- card pane ---------- */
const handlers = {
  action: (card, b) => runAction(card.action, b),
  next: (card, b) => { b.disabled = true; act('next_step', {incident_id: card.recovery.incident_id}).finally(() => { b.disabled = false; }); },
  repeat: card => say(card.recovery.text),
};

function render(card) {
  const pane = $('cardpane');
  const k = key(card);
  const next = card ? build(card, handlers) : idle();
  current = card;
  $('clock').hidden = !card;  // the idle panel already shows a big clock
  const old = pane.firstElementChild;
  const seq = ++renderSeq;
  if (!old || k === currentKey || REDUCED.matches) {
    pane.replaceChildren(next);  // same state (e.g. a button changed): no animation
  } else {
    // 200 ms fade out, then the new card slides in (CSS .enter, 260 ms)
    old.classList.add('leave');
    setTimeout(() => { if (seq === renderSeq) { next.classList.add('enter'); pane.replaceChildren(next); } }, 200);
  }
  currentKey = k;
  watchVerification(card);
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
  if (res.card) render(res.card);
  say(res.reply);
}

async function send(text) {
  text = text.trim();
  if (!text || busy) return;
  busy = true;
  interim('');
  addMsg(text, 'user');
  $('text').value = '';
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
  const res = await act(a.tool, a.args);
  if (!res || res.error) { b.disabled = false; return; }
  b.classList.add('is-done');
  b.innerHTML = `${svg('i-check')}<span>${a.label.replace(/^Tell /, '')} has been told</span>`;
}

/* ---------- inputs ---------- */
$('form').onsubmit = e => { e.preventDefault(); send($('text').value); };
document.querySelectorAll('.suggest').forEach(b => { b.onclick = () => send(b.dataset.say); });

const mic = $('mic');
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
      if (r.isFinal) final = r[0].transcript; else interim(r[0].transcript);
    };
    rec.onend = rec.onerror = () => {
      mic.classList.remove('live');
      mic.setAttribute('aria-pressed', 'false');
      mic.setAttribute('aria-label', 'Tap and speak');
      rec = null;
      voice(null);
      if (final) send(final); else interim('');
    };
    mic.classList.add('live');
    mic.setAttribute('aria-pressed', 'true');
    mic.setAttribute('aria-label', 'Listening. Tap to stop');
    voice('listening');
    rec.start();
  };
}

/* ---------- clocks, timers, debug chips ---------- */
render(null);
setInterval(() => tickClocks(), 1000);

if (DEBUG) {
  $('conn').hidden = false;
  fetch('/api/health').then(r => r.json()).then(h => {
    if (!h.mcp_ok) throw new Error('MCP server unreachable');
    $('conn').classList.add('ok');
    $('conn-text').textContent = `Connected · ${h.tools} tools`;
    $('mode').hidden = false;
    $('mode').textContent = h.mode === 'bedrock' ? 'Bedrock agent' : 'Mock agent';
  }).catch(() => { $('conn').classList.add('down'); $('conn-text').textContent = 'Offline'; });
}

if ('speechSynthesis' in window) speechSynthesis.getVoices();
