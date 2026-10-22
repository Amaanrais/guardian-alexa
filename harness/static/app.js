const $ = id => document.getElementById(id);
const sid = (() => { try { return localStorage.guardianSid ||= crypto.randomUUID(); } catch { return crypto.randomUUID(); } })();
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const URL_RE = /(https?:\/\/\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\/\S*)/i;
let rec = null, busy = false, lastHost = '';

const ICON = {red: 'i-octagon', amber: 'i-triangle', grey: 'i-info'};
const EYEBROW = {
  link: {red: 'High risk', amber: 'Caution', grey: 'Link checked'},
  message: {red: 'High risk', amber: 'Caution', grey: 'Message checked'},
  verify: {red: 'Caller check', amber: 'Caller check', grey: 'Caller check'},
  recovery: {red: 'Recovery', amber: 'Recovery', grey: 'Recovery'},
};

const svg = id => `<svg aria-hidden="true"><use href="#${id}"/></svg>`;

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
  row.scrollIntoView({block: 'end', behavior: 'smooth'});
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

function speak(text, row) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.92;
  const voice = speechSynthesis.getVoices().find(v => /en[-_]US/.test(v.lang) && /Samantha|Google US|Aria|Jenny/.test(v.name));
  if (voice) u.voice = voice;
  const av = row?.querySelector('.avatar');
  u.onstart = () => av?.classList.add('speaking');
  u.onend = u.onerror = () => av?.classList.remove('speaking');
  speechSynthesis.speak(u);
}

/* ---------- card ---------- */
function render(card) {
  $('empty').hidden = !!card;
  $('card').hidden = !card;
  if (!card) return;
  const kind = card.kind || 'link';
  const el = $('card');
  el.className = `card ${card.level} ${kind}` + (card.pending ? ' is-pending' : '');
  el.style.animation = 'none'; void el.offsetWidth; el.style.animation = '';

  $('badge-icon').innerHTML = `<use href="#${kind === 'recovery' ? 'i-lifebuoy' : kind === 'verify' ? 'i-phone' : ICON[card.level]}"/>`;
  $('eyebrow').textContent = card.eyebrow || EYEBROW[kind]?.[card.level] || '';
  $('title').textContent = card.title;

  const showShot = kind === 'link' && (card.screenshot_url || card.pending);
  $('shotwrap').hidden = !showShot;
  $('shot-label').textContent = lastHost ? `Sandbox · ${lastHost}` : 'Sandbox';
  const img = $('shot');
  if (card.screenshot_url) img.src = card.screenshot_url; else img.removeAttribute('src');

  $('pending').hidden = !card.pending;
  $('reasons').replaceChildren(...(card.reasons || []).slice(0, 3).map(r =>
    Object.assign(document.createElement('li'), {textContent: r})));

  const hint = $('hint');
  hint.hidden = kind !== 'recovery' || card.level === 'grey';
  hint.textContent = 'Say "next" when you have done this, or "repeat" to hear it again.';

  const b = $('action');
  b.hidden = !card.action;
  b.disabled = false;
  b.classList.remove('done');
  b.querySelector('svg').innerHTML = `<use href="#${card.action?.tool === 'start_incident' ? 'i-lifebuoy' : 'i-users'}"/>`;
  if (card.action) {
    $('action-label').textContent = card.action.label;
    b.onclick = () => runAction(card.action);
  }
}

function pendingCard() {
  render({level: 'grey', kind: 'link', pending: true, eyebrow: 'Checking', title: 'Looking at this link…',
          reasons: [], action: null});
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
  if (res.error) addMsg(res.error, 'err');
  render(res.card);
  speak(res.reply, addMsg(res.reply, 'bot'));
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
    try { lastHost = new URL(/^https?:/i.test(url[0]) ? url[0] : 'http://' + url[0]).hostname; } catch { lastHost = ''; }
    pendingCard();
  }
  typing(true);
  try { handle(await post('/api/chat', {message: text})); }
  catch (e) { typing(false); addMsg('Something went wrong: ' + e.message, 'err'); }
  busy = false;
}

async function runAction(a) {
  const b = $('action');
  b.disabled = true;
  try {
    if (a.tool === 'start_incident' || a.tool === 'next_step') { await send(a.label); return; }
    const res = await post('/api/action', {tool: a.tool, args: a.args});
    if (res.error) { addMsg(res.error, 'err'); b.disabled = false; return; }
    speak(res.reply, addMsg(res.reply, 'bot'));
    b.classList.add('done');
    b.querySelector('svg').innerHTML = '<use href="#i-check"/>';
    $('action-label').textContent = a.tool === 'alert_family' ? 'Family told' : 'Done';
  } catch (e) { addMsg('Something went wrong: ' + e.message, 'err'); b.disabled = false; }
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
      if (final) send(final); else interim('');
    };
    mic.classList.add('live');
    mic.setAttribute('aria-pressed', 'true');
    mic.setAttribute('aria-label', 'Listening. Tap to stop');
    rec.start();
  };
}

/* ---------- status bar ---------- */
function tick() { $('clock').textContent = new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}); }
tick(); setInterval(tick, 15000);

fetch('/api/health').then(r => r.json()).then(h => {
  if (!h.mcp_ok) throw new Error('MCP server unreachable');
  $('conn').classList.add('ok');
  $('conn-text').textContent = `Connected · ${h.tools} tools`;
  $('mode').hidden = false;
  $('mode').textContent = h.mode === 'bedrock' ? 'Bedrock agent' : 'Mock agent';
}).catch(() => { $('conn').classList.add('down'); $('conn-text').textContent = 'Offline'; });

if ('speechSynthesis' in window) speechSynthesis.getVoices();
