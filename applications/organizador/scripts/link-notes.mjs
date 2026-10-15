import { lstat, mkdir, readFile, realpath, symlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.resolve(process.argv[2] || path.join(root, '..', 'notas-flutuantes'));
const destination = path.join(root, 'integrations', 'notas-flutuantes');
for (const name of ['index.html', 'script.js', 'storage.js', 'style.css', 'icons.css', 'LICENSE']) {
  await readFile(path.join(source, name));
}
await mkdir(path.dirname(destination), { recursive: true });
const existing = await lstat(destination).catch(error => {
  if (error.code !== 'ENOENT') throw error;
  return null;
});
if (existing) {
  if (!existing.isSymbolicLink() || await realpath(destination) !== await realpath(source)) {
    throw new Error('O destino já existe e não corresponde à fonte. Nada foi alterado.');
  }
  console.log('A ligação com o Notas Flutuantes já está configurada.');
} else {
  await symlink(source, destination, process.platform === 'win32' ? 'junction' : 'dir');
  console.log(`Ligação criada: ${destination}\nFonte compartilhada: ${source}`);
}
