const translations = {
  "Visão geral": "Overview", "Início": "Home", "Módulos": "Modules", "Primeiro uso": "First use",
  "Diagnóstico": "Diagnostics", "Configurações": "Settings", "ECOSSISTEMA": "ECOSYSTEM", "SISTEMA": "SYSTEM",
  "Core ativo": "Core active", "somente neste PC": "only on this PC", "Pesquisar e executar": "Search and run",
  "Atualizar": "Refresh", "Configurar": "Configure", "COMANDOS RÁPIDOS": "QUICK COMMANDS",
  "O que você quer fazer?": "What do you want to do?", "Use ↑ ↓ para navegar e Enter para executar.": "Use ↑ ↓ to navigate and Enter to run.",
  "Suas ferramentas, conectadas sem perder a independência.": "Your tools, connected without losing their independence.",
  "O núcleo coordena os projetos que já existem, acompanha serviços locais e mantém cada código em sua própria pasta e repositório.": "The Core coordinates existing projects, monitors local services, and keeps every codebase in its own folder and repository.",
  "Abrir ferramentas": "Open tools", "Concluir configuração": "Finish setup", "Ecossistema disponível": "Ecosystem available",
  "Projetos registrados": "Registered projects", "Instalados": "Installed", "Serviços online": "Online services",
  "Início com Windows": "Start with Windows", "Acesso rápido": "Quick access", "Ver todas": "View all",
  "Central de módulos": "Module center", "Recarregar manifestos": "Reload manifests", "Instalar módulo por pasta ou Git": "Install module from folder or Git",
  "Origem": "Source", "Pasta existente": "Existing folder", "Repositório Git": "Git repository", "Caminho ou URL": "Path or URL",
  "Nome da pasta para Git": "Folder name for Git", "Instalar e recarregar": "Install and reload", "Todos": "All",
  "Abrir": "Open", "Iniciar": "Start", "Parar": "Stop", "Ativar": "Enable", "Desativar": "Disable",
  "Em planejamento": "Planned", "Indisponível": "Unavailable", "Disponível": "Available", "Online": "Online",
  "Desativado": "Disabled", "Incompatível": "Incompatible", "Pasta ausente": "Missing folder", "Parado": "Stopped",
  "Aparência": "Appearance", "Tema": "Theme", "Automático": "Automatic", "Escuro": "Dark", "Claro": "Light",
  "Idioma da interface": "Interface language", "Cor principal livre": "Custom accent color", "Densidade": "Density",
  "Compacta": "Compact", "Confortável": "Comfortable", "Espaçosa": "Spacious", "Tamanho do texto": "Text size",
  "Pequeno": "Small", "Grande": "Large", "Barra lateral compacta": "Compact sidebar", "Reduzir animações": "Reduce motion",
  "Alto contraste": "High contrast", "Decoração discreta": "Subtle decoration", "Home": "Home",
  "Tamanho dos cards favoritos": "Favorite card size", "Compacto": "Compact", "Amplo": "Wide",
  "Resumo de saúde": "Health summary", "Indicadores rápidos": "Quick indicators", "Atalhos": "Shortcuts",
  "Pesquisa global": "Global search", "Terminal": "Terminal", "Drop Zone": "Drop Zone", "Notificações": "Notifications",
  "Inicialização": "Startup", "Iniciar com o Windows": "Start with Windows", "Abrir o painel ao entrar": "Open panel at sign-in",
  "Backup do Workspace": "Workspace backup", "Exportar backup geral": "Export general backup", "Importar backup": "Import backup",
  "Modo portátil": "Portable mode", "Configurações": "Settings", "Presets": "Presets", "Clipboard": "Clipboard",
  "Histórico": "History", "Arquivos recentes": "Recent files", "Dados autorizados dos módulos": "Authorized module data",
  "Exportar pacote .zip": "Export .zip package", "Importar pacote": "Import package", "Manual na interface": "In-app manual",
  "Salvar todas as configurações": "Save all settings", "Compatibilidade e armazenamento": "Compatibility and storage",
  "Estado dos módulos": "Module status", "Executar novamente": "Run again", "Manifestos e portas": "Manifests and ports",
  "Erros recentes": "Recent errors", "Abrir atividades": "Open activities", "Recuperação": "Recovery",
  "Reiniciar": "Restart", "Verificar": "Check", "Nenhum conflito de porta ou manifesto encontrado.": "No port or manifest conflicts found.",
  "Nenhum erro recente registrado.": "No recent errors recorded.", "Abrir terminal": "Open terminal", "Abrir Drop Zone": "Open Drop Zone",
  "Abrir central de atividades": "Open activity center", "Fechar": "Close", "Remover dos favoritos": "Remove from favorites",
  "Adicionar aos favoritos": "Add to favorites", "Mover para a esquerda": "Move left", "Mover para a direita": "Move right",
};

const textOriginal = new WeakMap();
const attributeOriginal = new WeakMap();
let language = "pt-BR";
let observer;

function translated(value) {
  return language === "en" ? (translations[value] || value) : value;
}

function apply(root = document) {
  document.documentElement.lang = language;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const raw = textOriginal.get(node) ?? node.nodeValue;
    if (!raw?.trim()) continue;
    textOriginal.set(node, raw);
    const leading = raw.match(/^\s*/)?.[0] || "", trailing = raw.match(/\s*$/)?.[0] || "";
    const value = raw.trim();
    node.nodeValue = `${leading}${translated(value)}${trailing}`;
  }
  const elements = root.querySelectorAll?.("[title], [aria-label], [placeholder]") || [];
  for (const element of elements) {
    let originals = attributeOriginal.get(element);
    if (!originals) { originals = {}; attributeOriginal.set(element, originals); }
    for (const name of ["title", "aria-label", "placeholder"]) {
      if (!element.hasAttribute(name)) continue;
      originals[name] ??= element.getAttribute(name);
      element.setAttribute(name, translated(originals[name]));
    }
  }
}

function setLanguage(value) {
  language = value === "en" ? "en" : "pt-BR";
  apply(document);
}

function observe() {
  if (observer) return;
  observer = new MutationObserver((records) => {
    for (const record of records) for (const node of record.addedNodes) if (node.nodeType === Node.ELEMENT_NODE) apply(node);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
}

export const I18n = Object.freeze({
  setLanguage, observe, apply,
  t(key) { return translated(key); },
  get language() { return language; },
});
