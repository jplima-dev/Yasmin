export function openModule(module, browserWindow = window) {
  if (!module?.url || module.enabled === false || module.compatible === false) return false;
  browserWindow.location.assign(module.url);
  return true;
}
