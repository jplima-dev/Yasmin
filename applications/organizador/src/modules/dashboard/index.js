import { t, tr, locale, activityLabel } from '../../services/i18n.js';
import { el, icon, button, emptyState } from '../../components/ui.js';
import { taskRow, projectCard, noteCard, sectionTitle } from '../../components/records.js';
import { openEditor } from '../../components/entity-editor.js';
import { scan, page, projectStats, projectOptions } from '../../services/data-service.js';
import { today, formatDate, dayDistance, compareTasks } from '../../utils/dates.js';

export async function mount(root, ctx) {
  const day = today();
  const weekStart = new Date(); weekStart.setHours(0, 0, 0, 0); weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7));
  const counters = { today: 0, overdue: 0, completed: 0, projects: 0 };
  const tasks = [], alerts = [];
  const [projects, active, notes, activity] = await Promise.all([
    projectOptions(),
    page('projects', { filter: project => project.status === 'active', limit: 6 }),
    page('notes', { limit: 3 }),
    page('activities', { index: 'occurredAt', limit: 7 }),
    scan('tasks', task => {
      if (task.status === 'completed') { if (task.completedAt >= weekStart.toISOString()) counters.completed++; return; }
      if (task.dueDate === day) counters.today++;
      if (task.dueDate && task.dueDate < day) counters.overdue++;
      if (task.dueDate && task.dueDate <= day) { tasks.push(task); tasks.sort(compareTasks); if (tasks.length > 7) tasks.pop(); }
      if (task.postponementCount >= 3 && alerts.length < 2) alerts.push({ title: tr`${task.title} foi adiada ${task.postponementCount} vezes`, detail: t('Talvez valha dividir em um passo menor.'), href: `#/tasks/${task.id}` });
    }),
  ]);
  counters.projects = projects.filter(project => project.status === 'active').length;
  const stats = await Promise.all(active.records.map(project => projectStats(project.id)));
  if (ctx.signal.aborted) return;
  const projectMap = new Map(projects.map(project => [project.id, project]));
  for (const project of active.records) if (dayDistance(project.lastActivityAt) >= 7 && alerts.length < 3) alerts.push({ title: tr`${project.name} está sem atividade há ${dayDistance(project.lastActivityAt)} dias`, detail: t('Retome quando fizer sentido para você.'), href: `#/projects/${project.id}` });
  if (counters.overdue && alerts.length < 3) alerts.unshift({ title: tr`${counters.overdue} tarefa(s) passaram do prazo`, detail: t('Revise o que ainda precisa da sua atenção.'), href: '#/tasks?filter=overdue' });
  const dateText = new Intl.DateTimeFormat(locale(), { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date());
  root.append(el('div', { className: 'dashboard-greeting' }, el('div', {}, el('div', { className: 'eyebrow' }, icon('home'), t('Foco e progresso')), el('h1', {}, t('Visão geral')), el('p', { className: 'muted' }, t('Acompanhe suas prioridades e retome o que importa.'))), el('div', { className: 'greeting-actions' }, el('time', { className: 'dashboard-date', dateTime: day }, dateText), button(t('Nova tarefa'), () => openEditor('tasks'), { variant: 'primary', symbol: 'plus' }))));
  const metrics = [['tasks', t('Tarefas para hoje'), counters.today, t('Seu próximo passo'), '#/tasks?filter=today', 'blue'], ['clock', t('Em atraso'), counters.overdue, counters.overdue ? t('Precisam de atenção') : t('Tudo em dia por aqui'), '#/tasks?filter=overdue', 'orange'], ['projects', t('Projetos ativos'), counters.projects, t('Ideias em movimento'), '#/projects', 'purple'], ['check', t('Concluídas na semana'), counters.completed, t('Cada avanço conta'), '#/tasks?filter=completed', 'green']];
  root.append(el('div', { className: 'metrics-grid' }, metrics.map(([symbol, label, value, caption, href, color]) => el('a', { className: `metric ${color}`, href }, el('div', { className: 'metric-top' }, el('span', {}, label), icon(symbol)), el('strong', { className: 'metric-value' }, new Intl.NumberFormat(locale()).format(value)), el('span', { className: 'metric-caption' }, caption)))));
  const mainColumn = el('div', { className: 'dashboard-main' });
  const sideColumn = el('aside', { className: 'dashboard-aside' });
  const daily = el('section', { className: 'panel focus-panel' }, sectionTitle(t('Seu foco de hoje'), t('Ver tarefas'), '#/tasks?filter=today'));
  daily.append(el('div', { className: 'list-heading' }, el('span', {}, t('Hoje e em atraso')), el('span', { className: 'count-badge' }, counters.today + counters.overdue)));
  if (tasks.length) daily.append(...tasks.map(task => taskRow(task, projectMap.get(task.projectId), { compact: true })));
  else daily.append(emptyState('sun', t('Um dia cheio de possibilidades'), t('Escolha uma pequena tarefa para começar. Seus compromissos com prazo de hoje aparecerão aqui.'), button(t('Planejar uma tarefa'), () => openEditor('tasks', {}, { dueDate: day }), { variant: 'text', symbol: 'plus' })));
  mainColumn.append(daily);
  const projectSection = el('section', { className: 'dashboard-project-section' }, sectionTitle(t('Projetos em movimento'), t('Ver projetos'), '#/projects'));
  if (active.records.length) projectSection.append(el('div', { className: 'project-grid dashboard-projects' }, active.records.map((project, i) => projectCard(project, stats[i]))));
  else projectSection.append(el('div', { className: 'start-project' }, el('div', { className: 'start-project-art', 'aria-hidden': 'true' }, icon('projects'), el('span', { className: 'mini-check' }, icon('check'))), el('div', {}, el('h3', {}, t('Toda conquista começa com uma ideia')), el('p', {}, t('Reúna as tarefas e notas do que você quer tirar do papel.')), button(t('Criar meu primeiro projeto'), () => openEditor('projects'), { variant: 'text', symbol: 'arrow' }))));
  mainColumn.append(projectSection);
  const quick = el('section', { className: 'quick-actions' }, sectionTitle(t('Capture uma ideia')), el('p', { className: 'muted' }, t('Tire da cabeça. Guarde no lugar certo.')), button(t('Escrever uma nota'), () => openEditor('notes'), { variant: 'quick-action', symbol: 'notes' }), el('a', { className: 'button quick-action', href: '#/boards' }, icon('boards'), t('Abrir um quadro livre'), icon('arrow')));
  sideColumn.append(quick);
  if (alerts.length) sideColumn.append(el('section', { className: 'attention-panel' }, el('h2', {}, icon('warning'), t('Vale uma atenção')), alerts.slice(0, 3).map(alert => el('a', { href: alert.href, className: 'attention-item' }, el('strong', {}, alert.title), el('small', {}, alert.detail)))));
  const recent = el('section', { className: 'recent-panel' }, sectionTitle(t('Atividade recente')));
  if (activity.records.length) recent.append(el('ol', { className: 'activity-list' }, activity.records.map(item => el('li', {}, el('span', { className: 'activity-dot' }), el('div', {}, el('p', {}, activityLabel(item)), el('time', { dateTime: item.occurredAt }, formatDate(item.occurredAt, { hour: '2-digit', minute: '2-digit' })))))));
  else recent.append(el('div', { className: 'quiet-empty' }, icon('clock'), el('p', {}, t('Sua história começa aqui.')), el('small', {}, t('Projetos criados, notas salvas e tarefas concluídas aparecerão neste espaço.'))));
  sideColumn.append(recent);
  root.append(el('div', { className: 'dashboard-columns' }, mainColumn, sideColumn));
  if (notes.records.length) mainColumn.append(el('section', { className: 'dashboard-notes' }, sectionTitle(t('Notas recentes'), t('Ver notas'), '#/notes'), el('div', { className: 'note-grid' }, notes.records.map(note => noteCard(note, projectMap.get(note.projectId))))));
}
