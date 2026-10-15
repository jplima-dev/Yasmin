import { t, tr, errorText } from '../../services/i18n.js';
import { el, icon, iconButton, modal, emptyState } from '../../components/ui.js';
import { search } from '../../services/search-service.js';
import { entityNames } from '../../domain/models.js';

let openBox;
export function openSearch() {
  if (openBox?.dialog.isConnected) { openBox.input.focus(); return; }
  const box = modal(t('Buscar no seu espaço'), { wide: true });
  const input = el('input', { className: 'global-search-input', type: 'search', placeholder: t('Projetos, tarefas, notas ou uma ideia…'), 'aria-label': t('Busca global'), autocomplete: 'off' });
  const status = el('div', { className: 'search-status muted', role: 'status' }, t('Digite para buscar por título, texto ou tags.'));
  const results = el('div', { className: 'search-results' });
  const containerId = `search-results-${crypto.randomUUID()}`;
  results.id = containerId;
  input.setAttribute('aria-controls', containerId);
  input.setAttribute('aria-describedby', `${containerId}-status`);
  status.id = `${containerId}-status`;
  let timer, controller, generation = 0, selected = 0;
  function clearSearch() {
    clearTimeout(timer); controller?.abort(); generation++;
    input.value = ''; clear.hidden = true; results.replaceChildren();
    status.textContent = t('Digite para buscar por título, texto ou tags.');
    input.focus();
  }
  const clear = iconButton(t('Limpar busca'), 'close', clearSearch, { hidden: true });
  box.body.append(el('div', { className: 'search-input-wrap' }, icon('search'), input, clear), status, results);
  box.footer.append(el('small', { className: 'muted' }, t('↑ ↓ navegar · Enter abrir · Esc limpar / fechar · até 50 resultados')));
  openBox = { ...box, input };
  function markSelected() {
    Array.from(results.querySelectorAll('.search-result')).forEach((item, index) => { item.classList.toggle('selected', index === selected); });
  }
  async function run() {
    controller?.abort(); controller = new AbortController();
    const runId = ++generation;
    selected = 0;
    if (!input.value.trim()) { results.replaceChildren(); status.textContent = t('Digite para buscar por título, texto ou tags.'); return; }
    status.textContent = t('Pesquisando…');
    let signature = null;
    function paint(hits, partial) {
      if (runId !== generation || !box.dialog.isConnected) return;
      status.textContent = partial ? tr`${hits.length} resultado(s) · pesquisa em andamento…` : tr`${hits.length} resultado(s)`;
      const nextSignature = hits.map(hit => hit.key).join('|');
      if (signature !== nextSignature) {
        signature = nextSignature;
        results.replaceChildren(...hits.map(hit => el('a', { className: 'search-result', href: `#/${hit.entityType}/${hit.entityId}`, onClick: () => box.close() }, el('span', { className: 'result-icon' }, icon(hit.entityType)), el('span', {}, el('small', {}, t(entityNames[hit.entityType]).toUpperCase()), el('strong', {}, hit.title)), icon('arrow'))));
        selected = Math.min(selected, Math.max(0, hits.length - 1));
        markSelected();
      }
      if (!partial && !hits.length) results.replaceChildren(emptyState('search', t('Ainda não encontramos'), t('Tente outra palavra ou um termo mais curto.')));
    }
    const hits = await search(input.value, { signal: controller.signal, onProgress: paint });
    paint(hits, false);
  }
  input.addEventListener('input', () => { clear.hidden = !input.value; clearTimeout(timer); controller?.abort(); generation++; timer = setTimeout(() => run().catch(error => { status.textContent = errorText(error); }), 150); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape' && input.value) { event.preventDefault(); event.stopPropagation(); clearSearch(); return; }
    const items = results.querySelectorAll('.search-result');
    if (!items.length) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); selected = (selected + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length; markSelected(); items[selected].scrollIntoView({ block: 'nearest' }); }
    if (event.key === 'Enter') { event.preventDefault(); items[selected]?.click(); }
  });
  box.dialog.addEventListener('close', () => { clearTimeout(timer); controller?.abort(); openBox = null; }, { once: true });
  input.focus();
}
