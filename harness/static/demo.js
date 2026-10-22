/* Every screen state with fake data in the shapes harness/card.py and /api/home produce.
   /demo shows them all; /demo?state=<id> shows one at full size for screenshots and video. */
const {screen, home, build, weather, tickClocks} = window.GuardianCards;
const now = Date.now();
const tellRahul = {label: 'Tell Rahul', tool: 'alert_family', args: {}};
const startRecovery = {label: 'Start recovery', tool: 'start_incident', args: {}};
const rahul = status => ({kind: 'verify', verify: {id: 'demo', name: 'Rahul', pronoun: 'him', status, started_at: now - 14000}});
const HOME = {
  checks_this_week: 12, mcp_ok: true, verify_ready: true,
  family: [{name: 'Rahul', initial: 'R'}, {name: 'Priya', initial: 'P'}],
  recent: [
    {kind: 'link', level: 'red', title: "Don't open this link", label: 'nordbank-secure-login.com'},
    {kind: 'message', level: 'amber', title: 'Be careful', label: 'A message'},
    {kind: 'link', level: 'grey', title: 'No red flags found', label: 'cozysocks.example'},
  ],
};
const WEATHER = {temp: 8, icon: 'partly', words: 'Partly cloudy'};

const STATES = [
  ['Home screen', 'home', null],
  ['Voice bar: listening', 'listening', null, {voice: 'listening', line: 'Is this link safe? nordbank-secure…'}],
  ['Conversation expanded', 'transcript', null, {sheet: true}],
  ['Link: loading', 'pending', {kind: 'link', pending: true, domain: 'nordbank-secure-login.com', reasons: []}],
  ["Link: Don't open this link", 'red', {
    kind: 'link', level: 'red', title: "Don't open this link", domain: 'nordbank-secure-login.com',
    screenshot_url: '/static/demo/nordbank-login.svg', action: tellRahul,
    reasons: ["The page says it's NordBank, but it isn't on nordbank.example, and it asks for private details.",
              'The page asks for a PIN.', 'This website was only set up 3 days ago.']}],
  ['Link: Be careful', 'amber', {
    kind: 'link', level: 'amber', title: 'Be careful', domain: 'parcel-redelivery.top',
    screenshot_url: '/static/demo/shop-checkout.svg', action: tellRahul,
    reasons: ['The address ends in a domain type often used by scams.', 'The page asks for bank card details.']}],
  ['Link: No red flags found', 'grey', {
    kind: 'link', level: 'grey', title: 'No red flags found', domain: 'cozysocks.example',
    screenshot_url: '/static/demo/shop-checkout.svg', action: null, reasons: []}],
  ['Link: page tried to fool the AI', 'injection', {
    kind: 'link', level: 'red', title: "Don't open this link", domain: 'prize-claim-now.click', injection: true,
    screenshot_url: '/static/demo/prize-page.svg', action: startRecovery,
    // card.py drops the AI-trick reason from the list once the banner shows it
    reasons: ['The page asks for bank card details.', 'This website was only set up 2 days ago.',
              'It pressures you to act quickly.']}],
  ['Message: Be careful', 'message', {
    kind: 'message', level: 'amber', title: 'Be careful', action: tellRahul,
    reasons: ['It pressures you to act quickly.', 'It asks for a security code or PIN. Never share these with anyone.']}],
  ['Caller: waiting', 'verify-waiting', rahul('waiting')],
  ['Caller: confirmed', 'verify-confirmed', rahul('confirmed')],
  ['Caller: denied', 'verify-denied', rahul('denied')],
  ['Caller: no reply', 'verify-no_reply', rahul('no_reply')],
  ['Recovery: clarifying question', 'recovery-question', {kind: 'recovery', recovery: {incident_id: null,
    question: 'Did you share a code, or click a link?',
    choices: [{label: 'I shared a code', tool: 'start_incident', args: {}}, {label: 'I clicked a link', tool: 'start_incident', args: {}}]}}],
  ['Recovery: step 2 of 4', 'recovery', {kind: 'recovery', recovery: {incident_id: 'demo', index: 2, total: 4, done: false,
    text: 'Ask your bank to block your card and any transfers.'}}],
  ['Recovery: step with an action', 'recovery-action', {kind: 'recovery',
    action: {label: 'Ask Rahul for help', tool: 'alert_family', args: {}},
    recovery: {incident_id: 'demo', index: 3, total: 3, done: false,
      text: 'If you use the same password anywhere else, change it there too. Rahul can help you.'}}],
  ['Recovery: done', 'recovery-done', {kind: 'recovery', recovery: {incident_id: 'demo', index: 4, total: 4, done: true, family_told: true}}],
];
const TRANSCRIPT = [
  ['user', 'Is this link safe? https://nordbank-secure-login.com'],
  ['bot', "Please don't open that link. The page says it's NordBank, but it isn't. Never share a code or PIN."],
  ['user', 'Tell Rahul'],
  ['bot', "I've told Rahul."],
];

const flash = (_, b) => { b.animate([{transform: 'scale(.97)'}, {transform: 'none'}], {duration: 180}); };
const handlers = {action: flash, next: flash, repeat: flash, home: flash};

function device(card, opts = {}) {
  const product = document.createElement('div');
  product.className = 'product';
  product.innerHTML = `<main class="device"><div class="cams" aria-hidden="true"><i></i><i></i><i></i></div></main><div class="base" aria-hidden="true"></div>`;
  const s = screen();
  s.classList.toggle('on-home', !card);
  s.querySelector('[data-view]').append(card ? build(card, handlers) : home(HOME));
  const w = s.querySelector('[data-weather]');
  w.hidden = false;
  w.innerHTML = weather(WEATHER);
  if (opts.voice) {
    s.querySelector('[data-voicebar]').classList.add(opts.voice);
    s.querySelector('[data-line]').textContent = opts.line;
  }
  if (opts.sheet) {
    s.classList.add('sheet-open');
    s.querySelector('[data-sheet]').hidden = false;
    s.querySelector('[data-transcript]').innerHTML = TRANSCRIPT.map(([who, t]) => `<div class="msg ${who}"><p class="bubble">${t}</p></div>`).join('');
    s.querySelector('[data-line]').textContent = TRANSCRIPT.at(-1)[1];
  }
  product.querySelector('.device').append(s);
  return product;
}

const root = document.getElementById('root');
const only = new URLSearchParams(location.search).get('state');
const solo = STATES.find(([, id]) => id === only);
if (solo) {
  document.body.classList.add('solo');
  document.title = `Guardian · ${solo[0]}`;
  const stage = document.createElement('div');
  stage.className = 'stage';
  stage.append(device(solo[2], solo[3]));
  root.replaceWith(stage);
} else {
  const page = document.createElement('main');
  page.className = 'demo';
  page.innerHTML = `<header><h1>Guardian screen states</h1>
    <p>Fake data, real renderer (static/cards.js). Open any state full size for screenshots.</p></header><div class="grid"></div>`;
  for (const [label, id, card, opts] of STATES) {
    const fig = document.createElement('figure');
    fig.className = 'state';
    fig.id = id;
    fig.innerHTML = `<figcaption>${label} <a href="/demo?state=${id}">Full size</a></figcaption><div class="shrink"></div>`;
    fig.querySelector('.shrink').append(device(card, opts));
    page.querySelector('.grid').append(fig);
  }
  root.replaceWith(page);
}
tickClocks();
setInterval(() => tickClocks(), 1000);
