import { t, locale } from '../services/i18n.js';
export function today(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
export function formatDate(value, options = {}) {
  if (!value) return t('Sem prazo');
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  return new Intl.DateTimeFormat(locale(), { day: 'numeric', month: 'short', ...options }).format(date);
}
export function dayDistance(value, now = new Date()) {
  const target = value ? (value.length === 10 ? value : today(new Date(value))) : null;
  if (!target) return 0;
  return Math.floor((Date.parse(`${today(now)}T00:00:00Z`) - Date.parse(`${target}T00:00:00Z`)) / 86400000);
}
export function taskMatches(task, filter = 'all', date = today()) {
  if (filter === 'completed') return task.status === 'completed';
  if (filter === 'all') return true;
  if (task.status === 'completed') return false;
  if (filter === 'today') return task.dueDate === date;
  if (filter === 'overdue') return Boolean(task.dueDate && task.dueDate < date);
  if (filter === 'upcoming') return Boolean(task.dueDate && task.dueDate > date);
  return true;
}

export function compareTasks(a, b) {
  const weights = { urgent: 4, high: 3, normal: 2, low: 1 };
  return (a.dueDate || '9999').localeCompare(b.dueDate || '9999') || weights[b.priority] - weights[a.priority] || a.createdAt.localeCompare(b.createdAt);
}
