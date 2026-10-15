import { en } from '../i18n/en.js';

function storedLanguage() {
  try { return localStorage.getItem('organizador:language') === 'en' ? 'en' : 'pt'; }
  catch { return 'pt'; }
}
const globalSettings = globalThis.Mega?.settings;
let language = storedLanguage();
export const getLanguage = () => language;
export const locale = () => language === 'en' ? 'en-US' : 'pt-BR';

export function t(message, variables = {}) {
  const translated = language === 'en' && Object.hasOwn(en, message) ? en[message] : message;
  return String(translated).replace(/\{(\w+)\}/g, (match, key) => Object.hasOwn(variables, key) ? String(variables[key]) : match);
}

// Interpolated values are opaque text: titles, paths and note bodies are never translated.
export function tr(parts, ...values) {
  const key = parts.reduce((result, part, index) => result + (index ? `{${index - 1}}` : '') + part, '');
  return t(key, values);
}

export function applyLanguage() {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = locale();
  const skip = document.querySelector('.skip-link');
  if (skip) skip.textContent = t('Pular para o conteúdo');
}

export function setLanguage(value, { syncGlobal = true } = {}) {
  if (!['pt', 'en'].includes(value)) throw new RangeError('Unsupported language');
  language = value;
  try { localStorage.setItem('organizador:language', value); } catch { /* usable for this session */ }
  applyLanguage();
  if (typeof window !== 'undefined') window.dispatchEvent(new Event('languagechange'));
  if (syncGlobal && globalSettings) {
    const shared = value === 'en' ? 'en' : 'pt-BR';
    globalSettings.set('language', shared).catch(() => { /* preferência local permanece disponível sem o Core */ });
  }
}

globalSettings?.subscribe((settings) => {
  const next = settings.language === 'en' ? 'en' : 'pt';
  if (next !== language) setLanguage(next, { syncGlobal: false });
}, { immediate: false });

export function activityLabel(item) {
  if (language !== 'en') return item.label;
  const actions = { created: 'created', updated: 'updated', deleted: 'deleted', completed: 'completed', reopened: 'reopened', postponed: 'postponed' };
  const nouns = { projects: 'Project', tasks: 'Task', notes: 'Note' };
  const [kind, action] = item.type.split('.');
  const colon = item.label.indexOf(': ');
  return nouns[kind] && actions[action] && colon !== -1 ? `${nouns[kind]} ${actions[action]}: ${item.label.slice(colon + 2)}` : item.label;
}

// Domain errors keep their original contracts and are localized only when displayed.
export function errorText(error) {
  const message = error?.message || String(error);
  if (language !== 'en' || Object.hasOwn(en, message)) return t(message);
  const fields = { nome: 'name', título: 'title', descrição: 'description', texto: 'text', ícone: 'icon', subtarefa: 'subtask', tag: 'tag' };
  let match = /^Preencha (.+)\.$/.exec(message);
  if (match) return `Enter ${fields[match[1]] || match[1]}.`;
  match = /^(.+): texto inválido\.$/.exec(message);
  if (match) return `Invalid text: ${fields[match[1].toLowerCase()] || match[1]}.`;
  match = /^(.+): limite de ([\d.]+) caracteres\.$/.exec(message);
  if (match) return `${fields[match[1].toLowerCase()] || match[1]}: limit of ${Number(match[2].replaceAll('.', '')).toLocaleString('en-US')} characters.`;
  match = /^Coleção (.+) ausente ou inválida\.$/.exec(message);
  if (match) return `Missing or invalid collection: ${match[1]}.`;
  match = /^ID inválido( ou repetido)? em (.+)\.$/.exec(message);
  if (match) return `Invalid${match[1] ? ' or duplicate' : ''} ID in ${match[2]}.`;
  return message;
}
