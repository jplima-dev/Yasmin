import { t, tr, errorText } from '../services/i18n.js';
const paths = {
  organizer: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="18" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>',
  language: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a17 17 0 0 1 0 18 17 17 0 0 1 0-18Z"/>',
  home: '<path d="m3 10 9-7 9 7v10H3Z"/><path d="M9 20v-7h6v7"/>',
  tasks: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8 12 3 3 5-6"/>',
  projects: '<path d="M3 7V5h7l2 3h9v12H3Z"/>',
  notes: '<path d="M6 3h10l3 3v15H6Z"/><path d="M9 9h7M9 13h7M9 17h4"/>',
  boards: '<rect x="3" y="3" width="8" height="11" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="13" width="7" height="8" rx="1.5"/><path d="M3 18h8"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  settings: '<path d="m9 3-1 3-3 1-2 5 2 5 3 1 1 3h6l1-3 3-1 2-5-2-5-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  back: '<path d="M20 12H4m6-6-6 6 6 6"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1"/>',
  moon: '<path d="M20 14A9 9 0 0 1 10 3a9 9 0 1 0 10 11Z"/>',
  laptop: '<rect x="4" y="3" width="16" height="13" rx="2"/><path d="M2 20h20M8 16l-1 4M16 16l1 4"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  upload: '<path d="M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  edit: '<path d="m14 5 5 5M4 20l5-1L21 7l-5-5L4 14Z"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6"/>',
  warning: '<path d="m12 3 10 18H2Z"/><path d="M12 9v5M12 17v.1"/>',
  spark: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
};

export function icon(name, className = '') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [key, value] of Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.7', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true', class: `icon ${className}` })) svg.setAttribute(key, value);
  svg.innerHTML = paths[name] || paths.notes; // Only static, source-controlled SVG strings.
  return svg;
}

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), event => { Promise.resolve(value(event)).catch(showError); });
    else if (key === 'className') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key === 'style') Object.assign(node.style, value);
    else if (key in node && !key.startsWith('aria')) node[key] = value;
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}

export function button(label, onClick, { variant = 'secondary', symbol, ...props } = {}) {
  return el('button', { type: 'button', className: `button ${variant}`, onClick, ...props }, symbol && icon(symbol), el('span', {}, label));
}

export function iconButton(label, symbol, onClick, props = {}) {
  return el('button', { type: 'button', className: 'icon-button', title: label, 'aria-label': label, onClick, ...props }, icon(symbol));
}

export function toast(message, isError = false) {
  const host = document.querySelector('#toasts');
  if (!host) return;
  const item = el('div', { className: `toast ${isError ? 'error' : ''}`, role: isError ? 'alert' : 'status' }, icon(isError ? 'warning' : 'check'), message);
  host.append(item);
  setTimeout(() => item.remove(), isError ? 8000 : 4000);
}

export function showError(error) {
  console.error(error);
  toast(error?.name === 'QuotaExceededError' ? t('Armazenamento cheio. Os dados anteriores foram preservados; exporte um backup.') : errorText(error) || t('Não foi possível concluir. Tente novamente.'), true);
}

export function pageHeading(title, subtitle, action) {
  return el('div', { className: 'page-heading' }, el('div', {}, el('h1', {}, title), subtitle && el('p', { className: 'muted' }, subtitle)), action);
}

export function emptyState(symbol, title, description, action) {
  return el('div', { className: 'empty-state' }, el('div', { className: 'empty-icon' }, icon(symbol)), el('h3', {}, title), el('p', {}, description), action);
}

export function field(label, input, help) {
  if (!input.id) input.id = `field-${crypto.randomUUID()}`;
  return el('div', { className: 'form-field' }, el('label', { htmlFor: input.id }, label), input, help && el('small', { className: 'muted' }, help));
}

export function select(options, value, props = {}) {
  const node = el('select', props, options.map(option => el('option', { value: option.value }, option.label)));
  node.value = value ?? '';
  return node;
}

export function modal(title, { wide = false } = {}) {
  const previousFocus = document.activeElement;
  const dialog = el('dialog', { className: `modal ${wide ? 'wide' : ''}` });
  const headingId = `dialog-${crypto.randomUUID()}`;
  dialog.setAttribute('aria-labelledby', headingId);
  const body = el('div', { className: 'modal-body' });
  const footer = el('div', { className: 'modal-footer' });
  let beforeClose = () => true;
  let closing = false;
  const close = async () => {
    if (closing) return;
    closing = true;
    try { if (!await beforeClose()) return; dialog.close(); dialog.remove(); previousFocus?.focus(); }
    finally { closing = false; }
  };
  dialog.append(el('div', { className: 'modal-heading' }, el('h2', { id: headingId }, title), iconButton(t('Fechar diálogo'), 'close', close)), body, footer);
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) close(); } });
  document.body.append(dialog);
  dialog.showModal();
  return { dialog, body, footer, close, setBeforeClose(fn) { beforeClose = fn; } };
}

export function confirmAction(title, message, { label = t('Confirmar'), danger = false } = {}) {
  return new Promise(resolve => {
    const box = modal(title);
    box.body.append(el('p', {}, message));
    let accepted = false;
    box.setBeforeClose(() => { resolve(accepted); return true; });
    box.footer.append(button(t('Cancelar'), box.close), button(label, () => { accepted = true; box.close(); }, { variant: danger ? 'danger' : 'primary' }));
  });
}

export function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = el('a', { href: url, download: name });
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 15000);
}

export function pager(next, history, change) {
  return el('div', { className: 'pager' }, el('small', { className: 'muted' }, tr`Página ${history.length + 1} · até 50 itens`), el('div', { className: 'button-row' }, button(t('Anterior'), () => change('prev'), { disabled: history.length === 0 }), button(t('Próxima'), () => change('next'), { disabled: !next })));
}
