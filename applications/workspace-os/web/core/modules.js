const GRAMMAR = new Map([
  ["analisador projetos", "Analisador de Projetos"],
  ["leitor projetos", "Leitor de Projetos"],
  ["organizador fotos", "Organizador de Fotos"],
]);

export function displayNameFromFolder(folderName) {
  const words = String(folderName || "").replace(/[-_]+/g, " ").trim().toLocaleLowerCase("pt-BR");
  if (GRAMMAR.has(words)) return GRAMMAR.get(words);
  return words.replace(/(^|\s)\p{L}/gu, (letter) => letter.toLocaleUpperCase("pt-BR"));
}

export function validateModuleManifest(module) {
  if (!module || typeof module !== "object") throw new TypeError("O manifesto precisa ser um objeto.");
  for (const key of ["id", "name", "kind"]) if (!String(module[key] || "").trim()) throw new TypeError(`Campo obrigatório ausente: ${key}`);
  return module;
}
