import fs from 'node:fs';
import path from 'node:path';

// Expose only the static application assets. Never serve the linked .git directory.
export const notesFiles = ['index.html', 'script.js', 'storage.js', 'style.css', 'icons.css', 'LICENSE', 'assets/screenshots/logo.png'];
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png' };

export function notesIntegration(root) {
  const source = path.join(root, 'integrations', 'notas-flutuantes');
  let outputDirectory;
  const sourceExists = () => fs.existsSync(path.join(source, 'index.html'));
  const missingMessage = 'Notas Flutuantes não encontrado. Execute npm run link:notes, mantendo a pasta original ao lado deste projeto.';
  return {
    name: 'shared-floating-notes',
    configResolved(config) { outputDirectory = path.resolve(config.root, config.build.outDir); },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url, 'http://localhost');
        if (url.pathname === '/integration-status') {
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ available: sourceExists(), mode: 'linked', message: sourceExists() ? 'Código compartilhado com a pasta original' : missingMessage }));
          return;
        }
        if (!url.pathname.startsWith('/notas-flutuantes/')) return next();
        const file = url.pathname.slice('/notas-flutuantes/'.length) || 'index.html';
        if (!notesFiles.includes(file)) { res.statusCode = 404; res.end('Arquivo não encontrado'); return; }
        if (!sourceExists()) { res.statusCode = 503; res.end(missingMessage); return; }
        res.setHeader('Cache-Control', 'no-store');
        res.setHeader('Content-Type', mime[path.extname(file)] || 'text/plain; charset=utf-8');
        fs.createReadStream(path.join(source, file)).on('error', () => { res.statusCode = 404; res.end(); }).pipe(res);
      });
      if (sourceExists()) {
        const actualSource = fs.realpathSync(source);
        const watchedFiles = notesFiles.map(file => path.join(actualSource, file));
        server.watcher.add(watchedFiles);
        const onChange = changed => {
          if (watchedFiles.some(file => path.resolve(file) === path.resolve(changed))) {
            server.ws.send({ type: 'custom', event: 'notes-source-changed', data: {} });
          }
        };
        server.watcher.on('change', onChange);
        server.httpServer?.once('close', () => server.watcher.off('change', onChange));
      }
    },
    closeBundle() {
      if (!sourceExists()) throw new Error(missingMessage);
      for (const file of notesFiles) {
        const destination = path.join(outputDirectory, 'notas-flutuantes', file);
        fs.mkdirSync(path.dirname(destination), { recursive: true });
        fs.copyFileSync(path.join(source, file), destination);
      }
      fs.writeFileSync(path.join(outputDirectory, 'integration-status'), JSON.stringify({ available: true, mode: 'build', message: 'Versão incluída nesta distribuição' }));
    },
  };
}
