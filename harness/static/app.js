const $ = id => document.getElementById(id);
const sid = (() => { try { return localStorage.guardianSid ||= crypto.randomUUID(); } catch { return crypto.randomUUID(); } })();
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, busy = false;

function say(text, cls) {
  const d = document.createElement('div');
  d.className = 'msg ' + cls; d.textContent = text;
  $('transcript').append(d); d.scrollIntoView({block: 'end'});
}

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.9; speechSynthesis.speak(u);
}

function render(card) {
  $('empty').hidden = !!card; $('card').hidden = !card;
  if (!card) return;
  const el = $('card');
  el.className = 'card ' + card.level;
  $('icon').textContent = card.icon;
  $('title').textContent = card.title;
  $('pending').hidden = !card.pending;
  const shot = $('shot');
  shot.hidden = !card.screenshot_url;
  if (card.screenshot_url) shot.src = card.screenshot_url;
  $('reasons').replaceChildren(...(card.reasons || []).slice(0, 3).map(r => Object.assign(document.createElement('li'), {textContent: r})));
  const b = $('action');
  b.hidden = !card.action; b.disabled = false;
  if (card.action) { b.textContent = card.action.label; b.onclick = () => runAction(card.action); }
}

async function post(path, body) {
  const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({session_id: sid, ...body})});
  if (!r.ok) throw new Error('Server error ' + r.status);
  return r.json();
}

function handle(res) {
  if (res.error) say(res.error, 'err');
  render(res.card);
  say(res.reply, 'bot'); speak(res.reply);
}

async function send(text) {
  text = text.trim();
  if (!text || busy) return;
  busy = true; say(text, 'user'); $('text').value = '';
  try { handle(await post('/api/chat', {message: text})); }
  catch (e) { say('Something went wrong: ' + e.message, 'err'); }
  busy = false;
}

async function runAction(a) {
  $('action').disabled = true;
  try {
    if (a.tool === 'start_incident' || a.tool === 'next_step') { await send(a.label); return; }
    handle(await post('/api/action', {tool: a.tool, args: a.args}));
  } catch (e) { say('Something went wrong: ' + e.message, 'err'); $('action').disabled = false; }
}

$('form').onsubmit = e => { e.preventDefault(); send($('text').value); };

const mic = $('mic');
if (!SR) { mic.disabled = true; mic.title = 'Speech input needs Chrome or Edge'; }
else {
  mic.onclick = () => {
    if (rec) { rec.stop(); return; }
    speechSynthesis.cancel();
    rec = new SR(); rec.lang = 'en-US'; rec.interimResults = false;
    rec.onresult = e => send(e.results[0][0].transcript);
    rec.onend = rec.onerror = () => { mic.classList.remove('live'); rec = null; };
    mic.classList.add('live'); rec.start();
  };
}

fetch('/api/health').then(r => r.json()).then(h => { $('mode').textContent = h.mode + ' mode'; }).catch(() => {});
