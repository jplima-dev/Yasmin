const media = matchMedia('(prefers-color-scheme: dark)');
const workspaceSettings = () => globalThis.Mega?.settings;

export function preference(key, fallback) {
  if (key === 'theme') {
    const shared = workspaceSettings()?.get('theme');
    if (['light', 'dark', 'system'].includes(shared)) return shared;
  }
  try { return localStorage.getItem(`organizador:${key}`) ?? fallback; } catch { return fallback; }
}
export function setPreference(key, value) { try { localStorage.setItem(`organizador:${key}`, value); } catch { /* settings may be temporary; records still use IndexedDB */ } }
export function applyTheme(choice = preference('theme', 'light')) {
  document.documentElement.dataset.theme = choice === 'system' ? (media.matches ? 'dark' : 'light') : choice;
}
export function setTheme(value, { syncGlobal = true } = {}) {
  setPreference('theme', value);
  applyTheme(value);
  const globalSettings = workspaceSettings();
  if (syncGlobal && globalSettings) {
    globalSettings.set('theme', value).catch(() => { /* o Organizador continua utilizável quando o Core está offline */ });
  }
}
media.addEventListener('change', applyTheme);

workspaceSettings()?.subscribe((settings) => {
  if (!['light', 'dark', 'system'].includes(settings.theme)) return;
  globalThis.Mega?.theme?.apply(settings);
  setTheme(settings.theme, { syncGlobal: false });
}, { immediate: false });

document.addEventListener('workspace:settings-applied', event => {
  globalThis.Mega?.theme?.apply(event.detail);
  setTheme(event.detail.theme, { syncGlobal: false });
});
