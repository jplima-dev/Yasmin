import { t, tr, getLanguage, setLanguage, errorText } from '../../services/i18n.js';
import { el, pageHeading, button, icon, modal, select, confirmAction, toast, download } from '../../components/ui.js';
import { preference, setPreference, setTheme } from '../../services/preferences-service.js';
import { exportBackup, parseBackup, previewBackup, importBackup, collections } from '../../services/backup-service.js';
import { today, formatDate } from '../../utils/dates.js';

async function downloadBackup() {
  download(await exportBackup(), `meu-painel-backup-${today()}.json`);
  setPreference('last-backup', new Date().toISOString());
  toast(t('Backup do painel exportado. Guarde o arquivo em um lugar seguro.'));
}

export async function mount(root, ctx) {
  root.append(pageHeading(t('Configurações'), t('Seu espaço, do seu jeito. Seus dados, sob seu controle.')));
  root.append(el('div', { className: 'settings-group-title' }, icon('settings'), t('Preferências')));
  const language = select([{ value: 'pt', label: 'Português (Brasil)' }, { value: 'en', label: 'English' }], getLanguage(), { id: 'interface-language', 'aria-label': t('Idioma da interface') });
  language.addEventListener('change', () => setLanguage(language.value), { signal: ctx.signal });
  root.append(el('section', { className: 'settings-section language-section' }, el('div', {}, el('h2', {}, t('Idioma')), el('p', { className: 'muted' }, t('Escolha entre português e inglês. A preferência fica salva neste navegador.')), el('small', { className: 'muted' }, t('O conteúdo dos seus projetos, tarefas e notas mantém o idioma original.')), el('p', { className: 'integration-language-note muted' }, t('A preferência também é compartilhada com os módulos traduzidos do Workspace OS.'))), el('div', { className: 'language-control' }, icon('language'), language)));
  const themes = el('div', { className: 'theme-options' });
  for (const [value, label, symbol] of [['light', t('Claro'), 'sun'], ['dark', t('Escuro'), 'moon'], ['system', t('Sistema'), 'laptop']]) {
    const item = button(label, () => { setTheme(value); for (const child of themes.children) { child.classList.toggle('selected', child.dataset.theme === value); child.setAttribute('aria-pressed', child.dataset.theme === value); } }, { variant: 'theme-option', symbol, dataset: { theme: value } });
    item.classList.toggle('selected', preference('theme', 'dark') === value); item.setAttribute('aria-pressed', preference('theme', 'dark') === value); themes.append(item);
  }
  root.append(el('section', { className: 'settings-section' }, el('div', {}, el('h2', {}, t('Aparência')), el('p', { className: 'muted' }, t('Escolha o tema mais confortável para você.'))), themes));
  root.append(el('div', { className: 'settings-group-title' }, icon('shield'), t('Dados e armazenamento')));
  const file = el('input', { type: 'file', accept: '.json,application/json', hidden: true, 'aria-label': t('Arquivo de backup do painel') });
  const last = preference('last-backup', '');
  const lastLabel = el('small', { className: 'muted' }, last ? tr`Última exportação: ${formatDate(last, { hour: '2-digit', minute: '2-digit' })}` : t('Você ainda não exportou um backup neste navegador.'));
  const importButton = button(t('Importar backup'), () => file.click(), { symbol: 'upload' });
  file.addEventListener('change', async () => {
    const selected = file.files[0];
    if (!selected) return;
    importButton.disabled = true;
    try { await importDialog(await parseBackup(selected)); } catch (error) { ctx.error(error); }
    finally { file.value = ''; importButton.disabled = false; }
  }, { signal: ctx.signal });
  root.append(el('section', { className: 'settings-section' }, el('div', {}, el('h2', {}, t('Backup do painel')), el('p', { className: 'muted' }, t('Exporte projetos, tarefas, notas e vínculos com quadros. O JSON contém seus textos legíveis.')), lastLabel), el('div', { className: 'button-row' }, button(t('Exportar backup'), async () => { await downloadBackup(); lastLabel.textContent = tr`Última exportação: ${formatDate(new Date().toISOString(), { hour: '2-digit', minute: '2-digit' })}`; }, { variant: 'primary', symbol: 'download' }), importButton, file)));
  root.append(el('div', { className: 'info-banner' }, icon('boards'), el('div', {}, el('strong', {}, t('Os Quadros têm seu próprio backup')), el('p', {}, t('Notas flutuantes, imagens e anexos ficam no módulo original. Abra Quadros → Configurações → Exportar tudo para guardá-los. O backup acima contém apenas o vínculo com os projetos.')))));
  let estimate;
  try { estimate = await navigator.storage?.estimate(); } catch { /* unsupported */ }
  if (ctx.signal.aborted) return;
  const usage = estimate ? tr`${((estimate.usage || 0) / 1024 / 1024).toFixed(1)} MB usados por este endereço no navegador` : t('Estimativa de armazenamento indisponível neste navegador.');
  root.append(el('section', { className: 'settings-section' }, el('div', {}, el('h2', {}, t('Dados locais')), el('p', { className: 'muted' }, usage), el('p', { className: 'muted' }, t('Os dados ficam neste navegador e dispositivo. Limpar dados do site pode apagá-los. A pasta no OneDrive não sincroniza o IndexedDB.'))), button(t('Solicitar armazenamento persistente'), async event => {
    if (!navigator.storage?.persist) { toast(t('Este navegador não disponibiliza essa opção.'), true); return; }
    const control = event.currentTarget;
    control.disabled = true;
    try { const persisted = await navigator.storage.persist(); toast(persisted ? t('Armazenamento persistente concedido. Continue mantendo backups.') : t('O navegador não concedeu persistência. Seus dados continuam locais.')); } finally { control.disabled = false; }
  })));
  root.append(el('section', { className: 'settings-section' }, el('div', {}, el('h2', {}, t('Notas Flutuantes conectado')), el('p', { className: 'muted' }, t('No desenvolvimento, integrations/notas-flutuantes aponta para a pasta original. Alterações nos arquivos por qualquer caminho aparecem nos dois projetos.')), el('p', { className: 'muted' }, t('Dados de outro endereço, porta ou file:// não são transferidos automaticamente. Use o backup do Notas Flutuantes.'))), el('a', { className: 'button secondary', href: '#/boards' }, icon('boards'), t('Abrir Quadros'))));
  root.append(el('footer', { className: 'settings-foot muted' }, icon('shield'), t('Organizador 0.1 · Sem conta, sem telemetria, sem IA obrigatória.')));
}

async function importDialog(backup) {
  let preview = await previewBackup(backup);
  const box = modal(t('Revisar importação'), { wide: true });
  const summary = el('div', { className: 'import-summary' });
  function setSummary() { summary.replaceChildren(el('strong', {}, tr`${preview.counts.added} novos`), el('strong', {}, tr`${preview.counts.identical} iguais`), el('strong', {}, tr`${preview.counts.conflicts} conflitos`)); }
  setSummary();
  const conflictChoice = select([{ value: 'local', label: t('Preservar meus registros atuais') }, { value: 'incoming', label: t('Usar os registros do backup nos conflitos') }], 'local', { 'aria-label': t('Como resolver conflitos') });
  const error = el('p', { className: 'form-error', role: 'alert', hidden: true });
  box.body.append(el('p', {}, t('Nada foi alterado. Escolha como trazer os dados para este painel.')), summary, el('p', { className: 'muted' }, collections.map(kind => `${backup.data[kind].length} ${kind === 'projects' ? t('projetos') : kind === 'tasks' ? t('tarefas') : kind === 'notes' ? t('notas') : kind === 'activities' ? t('atividades') : t('vínculos de quadro')}`).join(' · ')), el('label', { className: 'field-label' }, t('Se o mesmo item tiver versões diferentes:'), conflictChoice));
  if (preview.conflicts.length) box.body.append(el('details', { className: 'conflict-details' }, el('summary', {}, t('Comparar versões em conflito (até 50)')), preview.conflicts.map(conflict => el('details', {}, el('summary', {}, conflict.local.name || conflict.local.title || conflict.local.label || conflict.local.boardName), el('div', { className: 'conflict-columns' }, el('div', {}, el('strong', {}, t('Neste painel')), el('pre', {}, JSON.stringify(conflict.local, null, 2))), el('div', {}, el('strong', {}, t('No backup')), el('pre', {}, JSON.stringify(conflict.incoming, null, 2))))))));
  box.body.append(el('p', { className: 'muted' }, t('Mesclar preserva itens que existem apenas no painel. Substituir remove o conteúdo atual do painel. Os dados internos dos Quadros não são alterados.')), error);
  let busy = false;
  box.setBeforeClose(() => !busy);
  async function apply(mode) {
    if (busy) return;
    if (mode === 'replace' && !await confirmAction(t('Substituir todos os dados do painel?'), t('Projetos, tarefas, notas, atividades e vínculos atuais serão removidos e trocados pelos do backup. Exporte os dados atuais antes, caso queira mantê-los.'), { label: t('Substituir dados'), danger: true })) return;
    busy = true; error.hidden = true;
    for (const control of box.footer.querySelectorAll('button')) control.disabled = true;
    try {
      await importBackup(backup, { mode, conflictPolicy: conflictChoice.value, expectedRevision: preview.revision });
      busy = false; box.close(); toast(t('Backup restaurado com sucesso.'));
    } catch (failure) {
      error.textContent = errorText(failure); error.hidden = false;
      if (failure.name === 'Error' || failure.constructor.name === 'ConflictError') { error.textContent += t(' Feche e importe novamente para revisar a base atual.'); }
    } finally { busy = false; for (const control of box.footer.querySelectorAll('button')) control.disabled = false; }
  }
  box.footer.append(button(t('Cancelar'), box.close), button(t('Exportar dados atuais'), downloadBackup, { symbol: 'download' }), button(t('Substituir…'), () => apply('replace'), { variant: 'danger-outline' }), button(t('Mesclar'), () => apply('merge'), { variant: 'primary' }));
}
