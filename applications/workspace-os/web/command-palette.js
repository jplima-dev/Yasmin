const ROUTES = [
  { id: "route-dashboard", label: "Ir para início", description: "Abrir a visão geral do Workspace OS", route: "dashboard", keywords: "home painel resumo" },
  { id: "route-modules", label: "Ver todos os módulos", description: "Abrir o catálogo de ferramentas", route: "modules", keywords: "apps ferramentas projetos" },
  { id: "route-setup", label: "Abrir primeiro uso", description: "Consultar a configuração guiada", route: "setup", keywords: "ajuda tutorial configurar" },
  { id: "route-diagnostics", label: "Executar diagnóstico", description: "Verificar módulos e serviços locais", route: "diagnostics", keywords: "saúde status erro" },
  { id: "route-settings", label: "Abrir configurações", description: "Alterar aparência, inicialização e integrações", route: "settings", keywords: "tema visual preferências" },
  { id: "action-terminal", label: "Abrir terminal", description: "Executar comandos no painel integrado", action: "terminal", keywords: "terminal console prompt comando" },
  { id: "action-dropzone", label: "Abrir Drop Zone", description: "Adicionar um arquivo e escolher em qual ferramenta usá-lo", action: "dropzone", keywords: "arquivo pasta arrastar abrir com importar recentes" },
  { id: "action-activity", label: "Abrir atividades", description: "Ver notificações, exportações e erros recentes", action: "activity", keywords: "central notificações notificacoes histórico historico erros recentes" },
  { id: "action-backup", label: "Exportar backup do Workspace", description: "Salvar configurações, favoritos e preferências em JSON", action: "backup", keywords: "cópia seguranca restaurar portátil exportar configurações" },
  { id: "action-portable", label: "Criar pacote portátil", description: "Exportar configurações, arquivos e dados autorizados em ZIP", action: "portable", keywords: "pendrive migrar computador backup zip" },
  { id: "action-reload-modules", label: "Recarregar manifestos", description: "Detectar módulos novos sem reiniciar o Core", action: "reload-modules", keywords: "plugin instalar módulo atualizar catálogo" },
  { id: "action-git-center", label: "Abrir central Git", description: "Ver branches, alterações locais e atualizações dos módulos", route: "modules", keywords: "git pull branch commit update atualização" },
];

export function normalizeSearch(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR")
    .trim();
}

export function buildCommands(modules = [], { activities = [], dropItems = [] } = {}) {
  const moduleCommands = modules
    .filter((module) => module.kind !== "planned" && module.enabled !== false)
    .map((module) => ({
      id: `module-${module.id}`,
      label: module.reachable || module.kind === "static-web" || module.kind === "desktop"
        ? `Abrir ${module.name}`
        : module.canStart ? `Iniciar ${module.name}` : `Configurar ${module.name}`,
      description: module.description,
      moduleId: module.id,
      action: module.reachable || module.kind === "static-web" || module.kind === "desktop"
        ? "open"
        : module.canStart ? "start" : "configure",
      keywords: `${module.name} ${module.category} ${module.description} ${(module.keywords || []).join(" ")}`,
    }));
  const recentModules = activities
    .filter((item) => item.kind === "module" && item.url)
    .filter((item, index, list) => list.findIndex((candidate) => candidate.moduleId === item.moduleId) === index)
    .slice(0, 8)
    .map((item) => ({
      id: `recent-module-${item.moduleId || item.id}`,
      label: item.title,
      description: `Usado recentemente · ${item.detail || "módulo do Workspace"}`,
      action: "open-url",
      url: item.url,
      keywords: `recente histórico ${item.moduleId || ""} ${item.detail || ""}`,
    }));
  const recentFiles = dropItems.slice(0, 10).map((item) => ({
    id: `recent-file-${item.id}`,
    label: `Arquivo recente: ${item.name}`,
    description: "Abrir a Drop Zone para escolher uma ação",
    action: "dropzone",
    keywords: `arquivo recente histórico ${item.name} ${item.type || ""} ${item.kind || ""}`,
  }));
  return [...ROUTES, ...recentModules, ...recentFiles, ...moduleCommands];
}

export function filterCommands(commands, query, limit = 9) {
  const normalized = normalizeSearch(query);
  if (!normalized) return commands.slice(0, limit);
  const terms = normalized.split(/\s+/).filter(Boolean);
  return commands
    .map((command, index) => {
      const label = normalizeSearch(command.label);
      const haystack = normalizeSearch(`${command.label} ${command.description} ${command.keywords || ""}`);
      if (!terms.every((term) => haystack.includes(term))) return null;
      const score = label.startsWith(normalized) ? 0 : label.includes(normalized) ? 1 : 2;
      return { command, index, score };
    })
    .filter(Boolean)
    .sort((left, right) => left.score - right.score || left.index - right.index)
    .slice(0, limit)
    .map((item) => item.command);
}
