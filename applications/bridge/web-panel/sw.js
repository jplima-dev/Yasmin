self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));

self.addEventListener("activate", event => event.waitUntil(
  caches.keys()
    .then(keys => Promise.all(keys.filter(key => key.startsWith("bridge-shell-")).map(key => caches.delete(key))))
    .then(() => self.clients.claim())
));

// O painel depende do Core para identidade e dados. Não servimos uma cópia
// offline, pois ela pareceria um Bridge vazio quando o servidor estivesse parado.
