export function enforceButtonTypes(root = document) {
  root.querySelectorAll?.("button:not([type])").forEach((button) => {
    button.type = "button";
  });
}

export function observeButtonTypes(root = document) {
  enforceButtonTypes(root);
  const target = root.documentElement || root;
  if (!target || !("MutationObserver" in globalThis)) return () => {};

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) continue;
        if (node.matches("button:not([type])")) node.type = "button";
        enforceButtonTypes(node);
      }
    }
  });
  observer.observe(target, { childList: true, subtree: true });
  return () => observer.disconnect();
}
