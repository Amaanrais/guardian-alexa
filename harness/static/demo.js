/* Every card state with fake data in the shapes harness/card.py produces. Buttons only flash. */
const {build, idle, tickClocks} = window.GuardianCards;
const now = Date.now();
const tellRahul = {label: 'Tell Rahul', tool: 'alert_family', args: {}};
const startRecovery = {label: 'Start recovery', tool: 'start_incident', args: {}};
const rahul = status => ({kind: 'verify', verify: {id: 'demo', name: 'Rahul', pronoun: 'him', status, started_at: now - 14000}});
const steps = (index, total, text) => ({kind: 'recovery', recovery: {incident_id: 'demo', index, total, text, done: false}});

const STATES = [
  ['Idle', 'idle', null],
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
  ['Recovery: step 1 of 4', 'recovery-1', steps(1, 4, 'Call your bank using the number on the back of your card.')],
  ['Recovery: step 3 of 4', 'recovery-3', steps(3, 4, 'Change the password of the account you were using.')],
  ['Recovery: done', 'recovery-done', {kind: 'recovery', recovery: {incident_id: 'demo', index: 4, total: 4, done: true, family_told: true}}],
];

const flash = (_, b) => { b.animate([{transform: 'scale(.97)'}, {transform: 'none'}], {duration: 180}); };
const handlers = {action: flash, next: flash, repeat: flash};

const grid = document.getElementById('grid');
for (const [label, id, card] of STATES) {
  const fig = document.createElement('figure');
  fig.className = 'state';
  fig.id = id;
  fig.innerHTML = `<figcaption>${label} <code>#${id}</code></figcaption><div class="frame cardpane"></div>`;
  fig.querySelector('.frame').append(card ? build(card, handlers) : idle());
  grid.append(fig);
}
setInterval(() => tickClocks(), 1000);
