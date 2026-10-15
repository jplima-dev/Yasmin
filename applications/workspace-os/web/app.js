import { buildCommands, filterCommands } from "/command-palette.js";
import { Settings } from "/core/settings.js";
import { applyGlobalTheme } from "/core/theme.js";
import { observeButtonTypes } from "/core/dom.js";
import { openModule } from "/module-navigation.js";
import { mountTerminal } from "/core/components/terminal.js";
import { mountUniversalDropzone } from "/core/dropzone.js";
import { mountActivityCenter } from "/core/components/activity-center.js";
import { Activity, observeExports } from "/core/activity.js";
import { downloadPortableArchive, downloadWorkspaceBackup, inspectPortableArchive, restorePortableArchive, restoreWorkspaceBackup } from "/core/backup.js";
import { mountShortcuts } from "/core/shortcuts.js";
import { I18n } from "/core/i18n.js";
import { BlackBox } from "/core/blackbox.js";
import { authorizedFetch } from "/core/origin.js";
import { mountYasminDock, openInYasmin, updateYasminModules } from "/yasmin-ui.js";

observeButtonTypes();

const state = {
  route: "dashboard",
  modules: [],
  settings: null,
  startup: null,
  diagnostics: null,
  filter: "all",
  commandResults: [],
  commandSelection: 0,
  settingsDirty: false,
  bridgeAgent: null,
  activities: [],
  dropItems: [],
  moduleAudit: null,
  gitProjects: {},
};
const settingsConversation = [];

const pageTitles = {
  dashboard: "Visão geral",
  modules: "Módulos",
  setup: "Primeiro uso",
  diagnostics: "Diagnóstico",
  settings: "Configurações",
};

const categoryLabels = {
  work: "Trabalho",
  files: "Arquivos",
  devices: "Dispositivos",
  utilities: "Utilitários",
};

const categoryDetails = {
  work: { symbol: "✦", description: "Criação, escrita e produtividade em um só fluxo." },
  files: { symbol: "◇", description: "Organize, transforme e prepare seus arquivos." },
  devices: { symbol: "⌁", description: "Conexões, sincronização e serviços do ecossistema." },
  utilities: { symbol: "⌘", description: "Ferramentas rápidas para tarefas do dia a dia." },
};

const iconLabels = {
  grid: "▦", note: "▤", image: "◇", repeat: "⇄", devices: "◉",
  drive: "▣", chart: "⌁", code: "</>", document: "D", table: "Σ", qr: "▦",
  braces: "{}", palette: "◐", diff: "±", terminal: ">_", base64: "64",
};

async function api(path, options = {}) {
  const response = await authorizedFetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let payload = {};
  try { payload = await response.json(); } catch { /* resposta sem JSON */ }
  if (!response.ok) throw new Error(payload.error || `Falha ${response.status}`);
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function applyAppearance() {
  if (!state.settings) return;
  applyGlobalTheme(state.settings);
  I18n.setLanguage(state.settings.language);
  const shell = document.querySelector(".app-shell");
  shell?.classList.toggle("sidebar-collapsed", state.settings.sidebar_collapsed);
  const collapseButton = document.querySelector("#sidebar-collapse-button");
  if (collapseButton) {
    const collapsed = state.settings.sidebar_collapsed;
    collapseButton.textContent = collapsed ? "›" : "‹";
    collapseButton.setAttribute("aria-label", collapsed ? "Expandir barra lateral" : "Recolher barra lateral");
    collapseButton.title = collapsed ? "Expandir barra lateral" : "Recolher barra lateral";
  }
}

function toast(message, type = "success") {
  const element = document.createElement("div");
  element.className = `toast ${type}`;
  element.textContent = message;
  document.querySelector("#toast-region").append(element);
  window.setTimeout(() => element.remove(), 4500);
  if (type === "error") Activity.record({ kind: "system", level: "error", title: "Erro no Workspace", detail: message }).catch(() => {});
}

async function loadState({ quiet = false } = {}) {
  try {
    const [modules, settings, startup, bridgeAgent, activities, dropzone] = await Promise.all([
      api("/api/modules"), api("/api/settings"), api("/api/startup"), api("/api/integrations/bridge-agent"),
      api("/api/activity"), api("/api/dropzone/history"),
    ]);
    state.modules = modules.modules;
    updateYasminModules(state.modules);
    state.startup = startup;
    state.bridgeAgent = bridgeAgent;
    state.activities = activities.items || [];
    state.dropItems = dropzone.items || [];
    if (state.route === "settings" && state.settingsDirty) return;
    state.settings = settings;
    applyAppearance();
    render();
  } catch (error) {
    if (!quiet) toast(`Não foi possível carregar o painel: ${error.message}`, "error");
  }
}

function navigate(route) {
  if (!(route in pageTitles)) return;
  state.route = route;
  history.replaceState(history.state, "", route === "dashboard" ? `${location.pathname}${location.search}` : `#${route}`);
  state.settingsDirty = false;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.route === route);
  });
  document.querySelector("#page-title").textContent = pageTitles[route];
  document.querySelector("#sidebar").classList.remove("open");
  render();
  if (["modules", "diagnostics"].includes(route)) loadModulePlatform();
  document.querySelector("#content").focus({ preventScroll: true });
}

function abrirNoWorkspace(module) {
  if (!module) return false;
  if (module.kind === "web-service" && !module.reachable && module.canStart) {
    startModule(module.id, { openWhenReady: true });
    return true;
  }
  if (openInYasmin(module)) return true;
  return openModule(module);
}

async function loadModulePlatform() {
  try {
    const [audit, git] = await Promise.all([api("/api/modules/audit"), api("/api/modules/git")]);
    state.moduleAudit = audit;
    state.gitProjects = Object.fromEntries((git.projects || []).map((item) => [item.moduleId, item]));
    if (["modules", "diagnostics"].includes(state.route)) render();
  } catch (error) { toast(`Não foi possível auditar os módulos: ${error.message}`, "error"); }
}

function statusInfo(module) {
  if (module.enabled === false) return { label: "Desativado", className: "" };
  if (module.compatible === false) return { label: "Incompatível", className: "warning" };
  if (module.kind === "planned") return { label: "Planejado", className: "" };
  if (!module.installed) return { label: "Pasta ausente", className: "warning" };
  if (module.reachable) return { label: "Online", className: "online" };
  if (["static-web", "desktop"].includes(module.kind)) return { label: "Disponível", className: "online" };
  if (module.kind === "remote-web" && !module.url) return { label: "Configuração pendente", className: "warning" };
  return { label: "Parado", className: "warning" };
}

function moduleCard(module, { featured = false, dashboard = false } = {}) {
  const status = statusInfo(module);
  const canOpen = Boolean(module.url) && (module.reachable || module.kind === "static-web");
  const showStop = module.managedState === "running" && module.kind === "web-service";
  let actions = "";
  if (module.enabled === false) {
    actions = `<button class="ghost-button" disabled>Módulo desativado</button>`;
  } else if (module.kind === "planned") {
    actions = `<button class="ghost-button" disabled>Em planejamento</button>`;
  } else if (module.kind === "remote-web" && !module.url) {
    actions = `<button class="secondary-button" data-route="settings">Configurar endereço</button>`;
  } else {
    if (canOpen) actions += `<button class="primary-button" data-open-module="${escapeHtml(module.id)}">Abrir</button>`;
    if (module.canStart && !module.reachable) {
      actions += module.id === "notebook"
        ? `<button class="primary-button" data-use-module="${escapeHtml(module.id)}">Usar</button>`
        : `<button class="primary-button" data-start-module="${escapeHtml(module.id)}">Iniciar</button>`;
    }
    if (showStop) actions += `<button class="danger-button" data-stop-module="${escapeHtml(module.id)}">Parar</button>`;
    if (!actions) actions = `<button class="ghost-button" disabled>Indisponível</button>`;
  }
  const favorite = (state.settings?.favorite_modules || []).includes(module.id);
  const category = categoryLabels[module.category] || module.category;
  const symbol = iconLabels[module.icon] || module.name[0];
  const git = state.gitProjects[module.id];
  const audit = state.moduleAudit?.modules?.find((item) => item.id === module.id);
  const capabilities = module.capabilities || {};
  const resources = [["export", "exporta"], ["import", "importa"], ["print", "imprime"], ["offline", "offline"]].filter(([key]) => capabilities[key]).map(([, label]) => label);
  return `
    <article class="module-card ${featured ? "module-card--featured" : ""} ${module.enabled === false ? "module-card--disabled" : ""}" draggable="${dashboard ? "true" : "false"}" data-module-card="${escapeHtml(module.id)}">
      <button class="favorite-button ${favorite ? "active" : ""}" type="button" data-favorite-module="${escapeHtml(module.id)}" aria-label="${favorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}" title="${favorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}">${favorite ? "★" : "☆"}</button>
      <div class="module-card-top">
        <div class="module-icon">${escapeHtml(symbol)}</div>
        <div class="module-card-title"><small>${escapeHtml(category)}</small><h3>${escapeHtml(module.name)}</h3><span class="badge ${status.className}">${escapeHtml(status.label)}</span></div>
      </div>
      <p>${escapeHtml(module.description)}</p>
      <div class="module-card-meta">
        <span>${escapeHtml(module.version || "sem versão")}</span>
        ${module.vendor ? `<span>Desenvolvido por ${escapeHtml(module.vendor)}.</span>` : ""}
        <span>${module.source === "manifest" ? "manifesto" : "catálogo legado"}</span>
        ${module.permissions?.length ? `<span title="${escapeHtml(module.permissions.join(", "))}">${module.permissions.length} permissão(ões)</span>` : `<span>sem permissões especiais</span>`}
        ${resources.length ? `<span title="Recursos descobertos pelo manifesto">${escapeHtml(resources.join(" · "))}</span>` : ""}
        ${git?.available ? `<span>${escapeHtml(git.branch || "Git")}${git.dirty ? " · alterações locais" : git.behind ? ` · ${git.behind} atualização(ões)` : " · limpo"}</span>` : ""}
        ${audit?.issues?.length ? `<span class="warning-text">${audit.issues.length} alerta(s)</span>` : ""}
      </div>
      ${dashboard ? `<div class="favorite-order-controls" aria-label="Ordenar favorito">
        <button type="button" class="icon-button" data-move-favorite="${escapeHtml(module.id)}" data-direction="-1" aria-label="Mover ${escapeHtml(module.name)} para a esquerda" title="Mover para a esquerda">←</button>
        <button type="button" class="icon-button" data-move-favorite="${escapeHtml(module.id)}" data-direction="1" aria-label="Mover ${escapeHtml(module.name)} para a direita" title="Mover para a direita">→</button>
      </div>` : ""}
      <div class="card-actions">${actions}${dashboard ? "" : `<button class="ghost-button" data-toggle-module="${escapeHtml(module.id)}" data-enable="${module.enabled === false ? "true" : "false"}">${module.enabled === false ? "Ativar" : "Desativar"}</button>${git?.available ? `<button class="ghost-button" data-git-module="${escapeHtml(module.id)}">Git</button>` : ""}`}</div>
      ${featured ? `<div class="module-card-art" aria-hidden="true"><span>${escapeHtml(symbol)}</span><i></i><i></i><i></i></div>` : ""}
    </article>`;
}

function moduleCategory(category, modules) {
  const details = categoryDetails[category] || { symbol: "•", description: "Ferramentas do Workspace." };
  const countLabel = modules.length === 1 ? "1 ferramenta" : `${modules.length} ferramentas`;
  return `
    <section class="module-category" data-module-category="${escapeHtml(category)}">
      <header class="module-category-header">
        <span class="module-category-symbol" aria-hidden="true">${escapeHtml(details.symbol)}</span>
        <div><h3>${escapeHtml(categoryLabels[category] || category)}</h3><p>${escapeHtml(details.description)}</p></div>
        <small>${escapeHtml(countLabel)}</small>
      </header>
      <div class="module-grid module-grid--catalog">
        ${modules.map((module, index) => moduleCard(module, { featured: index === 0 && modules.length > 1 })).join("")}
      </div>
    </section>`;
}

function renderDashboard() {
  const installed = state.modules.filter((module) => module.installed && module.kind !== "planned");
  const online = installed.filter((module) => statusInfo(module).className === "online");
  const services = state.modules.filter((module) => module.kind === "web-service");
  const activeServices = services.filter((module) => module.reachable);
  const percentage = installed.length ? Math.round((online.length / installed.length) * 100) : 0;
  const favoriteIds = state.settings.favorite_modules || [];
  const favorites = favoriteIds.map((id) => state.modules.find((module) => module.id === id)).filter(Boolean);
  const showHealth = state.settings.dashboard_show_health !== false;
  const showStats = state.settings.dashboard_show_stats !== false;
  const cardSize = state.settings.dashboard_card_size || "comfortable";
  return `
    <section class="hero ${showHealth ? "" : "hero--single"}">
      <div class="hero-main">
        <p class="eyebrow">LOCAL-FIRST · MODULAR · PRIVADO</p>
        <h2>Suas ferramentas, conectadas sem perder a independência.</h2>
        <p>O núcleo coordena os projetos que já existem, acompanha serviços locais e mantém cada código em sua própria pasta e repositório.</p>
        <div class="hero-actions">
          <button class="primary-button" data-route="modules">Abrir ferramentas</button>
          <button class="secondary-button" data-route="setup">Concluir configuração</button>
        </div>
      </div>
      ${showHealth ? `<aside class="panel health-summary">
        <div class="health-ring">
          <svg viewBox="0 0 42 42" aria-hidden="true"><circle class="ring-track" cx="21" cy="21" r="17"></circle><circle class="ring-value" cx="21" cy="21" r="17" pathLength="100" stroke-dasharray="${percentage} 100"></circle></svg>
          <strong>${percentage}%</strong>
        </div>
        <div><h3>Ecossistema disponível</h3><p>${online.length} de ${installed.length} ferramentas locais prontas ou online.</p></div>
      </aside>` : ""}
    </section>
    ${showStats ? `<section class="stats-grid">
      <article class="stat-card"><small>Projetos registrados</small><strong>${state.modules.length}</strong></article>
      <article class="stat-card"><small>Instalados</small><strong>${installed.length}</strong></article>
      <article class="stat-card"><small>Serviços online</small><strong>${activeServices.length}/${services.length}</strong></article>
      <article class="stat-card"><small>Início com Windows</small><strong>${state.startup?.enabled ? "Ativo" : "Pendente"}</strong></article>
    </section>` : ""}
    <div class="section-heading"><div><h2>Acesso rápido</h2><p>Ferramentas centrais do fluxo atual.</p></div><button class="ghost-button" data-route="modules">Ver todas</button></div>
    <section class="module-grid dashboard-grid dashboard-grid--${escapeHtml(cardSize)}">${favorites.map((module) => moduleCard(module, { dashboard: true })).join("") || `<div class="empty">Marque uma ferramenta com ☆ para deixá-la aqui.</div>`}</section>`;
}

function renderModules() {
  const categories = ["all", ...new Set(state.modules.map((module) => module.category))];
  const visible = state.filter === "all"
    ? state.modules
    : state.modules.filter((module) => module.category === state.filter);
  const visibleCategories = categories
    .filter((category) => category !== "all" && (state.filter === "all" || category === state.filter));
  return `
    <div class="section-heading"><div><h2>Central de módulos</h2><p>Ative, audite, atualize e instale ferramentas sem misturar seus projetos.</p></div><button class="secondary-button" data-reload-modules>Recarregar manifestos</button></div>
    <details class="integration-details module-install-panel">
      <summary>Instalar módulo por pasta ou Git</summary>
      <form id="module-install-form" class="settings-grid">
        <div class="field"><label for="module-source-type">Origem</label><select id="module-source-type" name="type"><option value="folder">Pasta existente</option><option value="git">Repositório Git</option></select></div>
        <div class="field"><label for="module-source">Caminho ou URL</label><input id="module-source" name="source" required placeholder="C:\\...\\meu-modulo ou https://github.com/..."></div>
        <div class="field"><label for="module-folder-name">Nome da pasta para Git</label><input id="module-folder-name" name="name" placeholder="Opcional; derivado do repositório"></div>
        <div class="integration-actions"><button class="primary-button" type="submit">Instalar e recarregar</button></div>
      </form>
      <p class="settings-live-note">Pastas precisam estar diretamente no ecossistema e conter <code>ink-module.json</code>. Atualizações Git nunca sobrescrevem alterações locais.</p>
    </details>
    <div class="filter-row">
      ${categories.map((category) => `<button class="filter-button ${state.filter === category ? "active" : ""}" data-filter="${escapeHtml(category)}">${escapeHtml(category === "all" ? "Todos" : categoryLabels[category] || category)}</button>`).join("")}
    </div>
    <div class="module-catalog">${visible.length
      ? visibleCategories.map((category) => moduleCategory(category, visible.filter((module) => module.category === category))).join("")
      : `<div class="empty">Nenhum módulo nesta categoria.</div>`}</div>`;
}

function renderSetup() {
  const startupReady = Boolean(state.startup?.enabled);
  const organizer = state.modules.find((module) => module.id === "organizer");
  const bridge = state.modules.find((module) => module.id === "bridge");
  const drive = state.modules.find((module) => module.id === "drive2");
  return `
    <div class="section-heading"><div><h2>Configuração guiada</h2><p>Faça uma vez, nesta ordem. Cada etapa mostra exatamente onde clicar.</p></div></div>
    <section class="steps">
      <article class="step-card">
        <span class="step-number">1</span>
        <div><h3>Ativar junto com o Windows</h3><p>Isso inicia o Core, o Organizador e o Bridge ao entrar na sua conta.</p>
          <ol><li>Clique em <strong>Ativar agora</strong>.</li><li>Confira a confirmação verde.</li><li>Reinicie o PC quando for conveniente; não é necessário reiniciar agora.</li><li>Após entrar no Windows, abra <strong>${escapeHtml(location.origin)}</strong> se o painel não estiver configurado para abrir sozinho.</li></ol>
        </div>
        <button class="${startupReady ? "ghost-button" : "primary-button"}" data-startup-action="${startupReady ? "disable" : "enable"}">${startupReady ? "Desativar" : "Ativar agora"}</button>
      </article>
      <article class="step-card">
        <span class="step-number">2</span>
        <div><h3>Confirmar o Organizador</h3><p>Status atual: <strong>${organizer?.reachable ? "online" : "parado"}</strong>.</p>
          <ol><li>Se estiver parado, clique em <strong>Iniciar</strong>.</li><li>Aguarde alguns segundos e clique em <strong>Atualizar</strong> no topo.</li><li>Clique em <strong>Abrir</strong>.</li><li>No Organizador, entre em <strong>Configurações → Backup do painel</strong> e exporte uma cópia antes de mudanças grandes.</li></ol>
        </div>
        <button class="primary-button" ${organizer?.reachable ? `data-open-module="organizer"` : `data-start-module="organizer"`}>${organizer?.reachable ? "Abrir" : "Iniciar"}</button>
      </article>
      <article class="step-card">
        <span class="step-number">3</span>
        <div><h3>Conectar o celular pelo Bridge</h3><p>Status atual: <strong>${bridge?.reachable ? "online" : "parado"}</strong>.</p>
          <ol><li>Inicie e abra o Bridge.</li><li>No notebook, procure o endereço indicado como <strong>Outros aparelhos</strong>.</li><li>Conecte celular e notebook ao mesmo Wi-Fi.</li><li>No navegador do celular, digite o endereço completo mostrado, incluindo <strong>http://</strong> e <strong>:8876</strong>.</li><li>Digite um nome para o celular e toque em <strong>Adicionar este aparelho</strong>.</li><li>Não use 127.0.0.1 no celular; esse endereço sempre aponta para o próprio aparelho.</li></ol>
        </div>
        <button class="primary-button" ${bridge?.reachable ? `data-open-module="bridge"` : `data-start-module="bridge"`}>${bridge?.reachable ? "Abrir" : "Iniciar"}</button>
      </article>
      <article class="step-card">
        <span class="step-number">4</span>
        <div><h3>Confirmar o InkDriver integrado</h3><p>Status atual: <strong>${drive?.reachable ? "online" : "parado"}</strong>.</p>
          <ol><li>Abra <strong>Configurações → InkDriver</strong>.</li><li>Mantenha <strong>Executar como módulo local</strong> ligado.</li><li>Clique em <strong>Salvar e reiniciar InkDriver</strong>.</li><li>Volte a <strong>Módulos → Dispositivos</strong> e abra o InkDriver.</li><li>O modo remoto por Termux e Tailscale continua disponível como opção avançada.</li></ol>
        </div>
        <button class="primary-button" ${drive?.reachable ? `data-open-module="drive2"` : `data-start-module="drive2"`}>${drive?.reachable ? "Abrir" : "Iniciar"}</button>
      </article>
      <article class="step-card">
        <span class="step-number">5</span>
        <div><h3>Ajustar a interface para uso prolongado</h3><p>Escolha o tamanho e o movimento mais confortáveis para você.</p>
          <ol><li>Na barra lateral, clique em <strong>Configurações</strong>.</li><li>Em <strong>Aparência</strong>, escolha tema, cor, densidade e tamanho do texto.</li><li>Ative <strong>Barra lateral compacta</strong> se quiser mais espaço para o conteúdo.</li><li>Ative <strong>Reduzir animações</strong> se preferir respostas imediatas e menos movimento.</li><li>Observe a mudança imediatamente; as opções visuais não precisam de botão Salvar.</li><li>Para encontrar qualquer ferramenta sem navegar pelos menus, pressione <strong>Ctrl + K</strong>, digite o nome e pressione <strong>Enter</strong>.</li></ol>
        </div>
        <button class="secondary-button" data-route="settings">Ajustar aparência</button>
      </article>
    </section>`;
}

function permissionToggle(name, title, description, checked = false) {
  return `<div class="toggle-row"><span class="toggle-copy"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(description)}</small></span><label class="switch"><input type="checkbox" name="${escapeHtml(name)}" aria-label="${escapeHtml(title)}" ${checked ? "checked" : ""}><span></span></label></div>`;
}

function manualCommand(command, label = "Copiar") {
  return `<div class="manual-command"><code>${escapeHtml(command)}</code><button class="ghost-button" type="button" data-copy-text="${escapeHtml(command)}">${escapeHtml(label)}</button></div>`;
}

function integrationManual() {
  const root = "C:\\Users\\gugas\\OneDrive\\Desktop\\codigos";
  return `<div class="integration-manual">
    <details open>
      <summary><span>Bridge</span><small>Servidor, celular e agente Windows</small></summary>
      <ol class="manual-steps">
        <li><strong>Defina a rede e a porta.</strong><p>Em <b>Bridge Core</b>, mantenha <code>0.0.0.0</code> para permitir celulares na mesma rede. Escolha a porta e, se quiser um endereço fixo, preencha o endereço público.</p></li>
        <li><strong>Salve e reinicie.</strong><p>Clique em <b>Salvar e reiniciar Bridge</b>. Aguarde a confirmação e clique em <b>Abrir painel</b>.</p></li>
        <li><strong>Cadastre o celular.</strong><p>No painel do Bridge, copie o endereço mostrado em <b>Outros aparelhos</b>. No celular conectado ao mesmo Wi-Fi, abra esse endereço completo, informe um nome e toque em <b>Adicionar este aparelho</b>.</p></li>
        <li><strong>Configure este computador.</strong><p>Em <b>Bridge Agent no Windows</b>, confira o endereço do servidor, escolha o nome e as permissões e clique em <b>Salvar perfil do agente</b>.</p></li>
        <li><strong>Faça o primeiro pareamento.</strong><p>Abra o Ink Terminal pelo botão <code>&gt;_</code>, cole o comando abaixo e confirme o código exibido na interface.</p>${manualCommand(`& '${root}\\bridge\\.venv\\Scripts\\python.exe' '${root}\\bridge\\windows-agent\\agent.py' --server http://127.0.0.1:8876 --pair`)}</li>
        <li><strong>Inicie o agente com o Windows.</strong><p>Depois do pareamento, abra o Ink Terminal e execute uma vez o instalador de inicialização. O Core do Bridge já acompanha a opção <b>Iniciar com o Windows</b> do Workspace.</p>${manualCommand(`Set-ExecutionPolicy -Scope Process Bypass; & '${root}\\bridge\\windows-agent\\install-startup.ps1'`)}</li>
      </ol>
    </details>
    <details>
      <summary><span>InkDriver</span><small>Tablet, Tailscale, .env e início automático</small></summary>
      <ol class="manual-steps">
        <li><strong>Instale os aplicativos no tablet.</strong><p>Instale Termux e Termux:Boot pela mesma fonte (preferencialmente F-Droid) e instale o Tailscale. Abra os três aplicativos uma vez.</p></li>
        <li><strong>Prepare o Termux.</strong><p>No Termux, atualize os pacotes e instale Python e Git.</p>${manualCommand("pkg update && pkg upgrade -y && pkg install python git -y")}</li>
        <li><strong>Coloque o projeto no tablet.</strong><p>Clone seu repositório do InkDriver para <code>$HOME/drive2</code> ou copie a pasta <code>driver</code> para esse local. Depois entre na pasta.</p>${manualCommand("cd $HOME/drive2")}</li>
        <li><strong>Instale o ambiente.</strong><p>Crie o ambiente virtual e instale as dependências principais. Se ativar R2 ou Gmail, instale também os arquivos de dependências correspondentes.</p>${manualCommand("python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt")}</li>
        <li><strong>Gere a configuração aqui.</strong><p>Preencha todos os campos de <b>InkDriver</b>. Se ativar login, informe uma senha de pelo menos 8 caracteres e gere o segredo. Clique em <b>Baixar .env do InkDriver</b>.</p></li>
        <li><strong>Copie o arquivo.</strong><p>Transfira o arquivo baixado para o tablet e salve exatamente como <code>$HOME/drive2/.env</code>. O banco deve continuar no espaço privado do Termux.</p></li>
        <li><strong>Teste manualmente.</strong><p>Com o Tailscale conectado, inicie o servidor e abra <code>http://127.0.0.1:8000</code> no próprio tablet.</p>${manualCommand("cd $HOME/drive2 && . .venv/bin/activate && python run.py")}</li>
        <li><strong>Conecte o Workspace.</strong><p>No Tailscale do tablet, copie o IP <code>100.x.y.z</code>. Preencha <b>Endereço Tailscale do InkDriver</b> com <code>http://100.x.y.z:8000</code> e salve.</p></li>
        <li><strong>Ative no boot.</strong><p>No Termux:Boot, crie o script de início e dê permissão. Abra o Termux:Boot pelo ícone uma vez e retire a restrição de bateria para Termux, Termux:Boot e Tailscale nas configurações do Android.</p>${manualCommand("mkdir -p ~/.termux/boot && cp scripts/termux-boot-drive2 ~/.termux/boot/20-drive2 && chmod +x ~/.termux/boot/20-drive2")}</li>
      </ol>
    </details>
  </div>`;
}

function renderSettings() {
  const settings = state.settings;
  const autoModules = new Set(settings.auto_start_modules);
  const bridge = settings.module_configs?.bridge || {};
  const driver = settings.module_configs?.drive2 || {};
  const agent = state.bridgeAgent || { server: "http://127.0.0.1:8876", name: "Meu computador", paired: false, clipboard_enabled: false, permissions: {} };
  return `
    <section class="panel yasmin-settings-panel" aria-label="Conversa sobre preferências com a Yasmin">
      <div class="section-heading"><div><h2>Converse com a Yasmin</h2><p>Conte como prefere as respostas, peça uma curiosidade ou ensine algo para lembrar.</p></div></div>
      <div class="yasmin-settings-messages" id="yasmin-settings-messages" role="log" aria-live="polite">
        ${settingsConversation.length ? settingsConversation.map((item) => `<p class="yasmin-settings-message ${item.role}"><strong>${item.role === "user" ? "Você" : "Yasmin"}</strong><span>${escapeHtml(item.text)}</span></p>`).join("") : `<p class="muted">Ex.: “Como você prefere as configurações?” ou “Prefiro respostas curtas”.</p>`}
      </div>
      <form id="yasmin-settings-chat-form" class="yasmin-settings-chat-form"><label for="yasmin-settings-chat-input">Sua mensagem</label><div><input id="yasmin-settings-chat-input" maxlength="1000" autocomplete="off" placeholder="Converse com a Yasmin…"><button class="primary-button" type="submit">Enviar</button></div></form>
    </section>
    <form id="settings-form">
      <section class="panel">
        <div class="section-heading"><div><h2>Aparência</h2><p>As alterações valem imediatamente para toda a suíte conectada.</p></div></div>
        <div class="settings-grid">
          <div class="field"><label for="theme">Tema</label><select id="theme" data-global-setting="theme"><option value="system">Automático</option><option value="dark">Escuro</option><option value="light">Claro</option></select></div>
          <div class="field"><label for="language">Idioma da interface</label><select id="language" data-global-setting="language"><option value="pt-BR">Português (Brasil)</option><option value="en">English</option></select><small>Módulos traduzidos acompanham esta preferência; o conteúdo criado não é alterado.</small></div>
          <div class="field color-field"><label for="accent">Cor principal livre</label><div class="color-control"><input id="accent" data-global-setting="accent" type="color" value="${escapeHtml(settings.accent)}"><output id="accent-value">${escapeHtml(settings.accent.toUpperCase())}</output></div><small>O sistema cria automaticamente hover, fundo suave e borda derivados desta cor.</small></div>
          <div class="field"><label for="density">Densidade</label><select id="density" data-global-setting="density"><option value="compact">Compacta</option><option value="comfortable">Confortável</option><option value="spacious">Espaçosa</option></select></div>
          <div class="field"><label for="font-size">Tamanho do texto</label><select id="font-size" data-global-setting="font_size"><option value="small">Pequeno</option><option value="comfortable">Confortável</option><option value="large">Grande</option></select><small>Aplica-se aos módulos conectados à configuração global.</small></div>
        </div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Barra lateral compacta</strong><small>Mostra somente os ícones; passe o mouse para ver o nome de cada seção.</small></span><label class="switch"><input type="checkbox" data-global-setting="sidebar_collapsed" aria-label="Barra lateral compacta" ${settings.sidebar_collapsed ? "checked" : ""}><span></span></label></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Reduzir animações</strong><small>Remove transições decorativas e deixa as respostas mais imediatas.</small></span><label class="switch"><input type="checkbox" data-global-setting="reduce_motion" aria-label="Reduzir animações" ${settings.reduce_motion ? "checked" : ""}><span></span></label></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Alto contraste</strong><small>Reforça bordas e separação entre painéis.</small></span><label class="switch"><input type="checkbox" data-global-setting="high_contrast" aria-label="Alto contraste" ${settings.high_contrast ? "checked" : ""}><span></span></label></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Decoração discreta</strong><small>Mantém formas e tonalidades suaves nos cabeçalhos.</small></span><label class="switch"><input type="checkbox" data-global-setting="decorations" aria-label="Decoração discreta" ${settings.decorations ? "checked" : ""}><span></span></label></div>
        <p class="settings-live-note">As opções visuais são aplicadas e salvas imediatamente, inclusive nas outras abas conectadas.</p>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Home</h2><p>Escolha a densidade e o que aparece no painel inicial.</p></div></div>
        <div class="settings-grid">
          <div class="field"><label for="dashboard-card-size">Tamanho dos cards favoritos</label><select id="dashboard-card-size" data-global-setting="dashboard_card_size"><option value="compact">Compacto</option><option value="comfortable">Confortável</option><option value="wide">Amplo</option></select><small>A ordem pode ser alterada pelas setas nos cards da Home.</small></div>
        </div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Resumo de saúde</strong><small>Mostra a disponibilidade do ecossistema ao lado da apresentação.</small></span><label class="switch"><input type="checkbox" data-global-setting="dashboard_show_health" aria-label="Mostrar resumo de saúde" ${settings.dashboard_show_health !== false ? "checked" : ""}><span></span></label></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Indicadores rápidos</strong><small>Mostra projetos, instalações, serviços e início com o Windows.</small></span><label class="switch"><input type="checkbox" data-global-setting="dashboard_show_stats" aria-label="Mostrar indicadores rápidos" ${settings.dashboard_show_stats !== false ? "checked" : ""}><span></span></label></div>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Atalhos</h2><p>Use combinações como Ctrl+K, Ctrl+Shift+O ou Alt+T.</p></div></div>
        <div class="settings-grid">
          ${[["search","Pesquisa global"],["terminal","Terminal"],["dropzone","Drop Zone"],["activities","Notificações"]].map(([key,label]) => `<div class="field"><label for="shortcut-${key}">${label}</label><input id="shortcut-${key}" data-shortcut="${key}" value="${escapeHtml(settings.keyboard_shortcuts?.[key] || "")}" autocomplete="off"></div>`).join("")}
        </div>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Inicialização</h2><p>O Core pode preparar os serviços sem abrir janelas de terminal.</p></div></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Iniciar com o Windows</strong><small>${state.startup?.enabled ? "Ativo nesta conta do Windows." : "Desativado."}</small></span><button type="button" class="${state.startup?.enabled ? "danger-button" : "primary-button"}" data-startup-action="${state.startup?.enabled ? "disable" : "enable"}">${state.startup?.enabled ? "Desativar" : "Ativar"}</button></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Abrir o painel ao entrar</strong><small>Se desligado, os serviços iniciam silenciosamente e o painel abre só quando você quiser.</small></span><label class="switch"><input type="checkbox" name="open_panel_on_start" aria-label="Abrir o painel ao entrar" ${settings.open_panel_on_start ? "checked" : ""}><span></span></label></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Iniciar Organizador</strong><small>Disponibiliza projetos, tarefas e notas na porta 5173.</small></span><label class="switch"><input type="checkbox" name="auto_module" value="organizer" aria-label="Iniciar Organizador" ${autoModules.has("organizer") ? "checked" : ""}><span></span></label></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Iniciar Bridge Core</strong><small>Disponibiliza dispositivos e transferências na porta 8876.</small></span><label class="switch"><input type="checkbox" name="auto_module" value="bridge" aria-label="Iniciar Bridge Core" ${autoModules.has("bridge") ? "checked" : ""}><span></span></label></div>
        <div class="toggle-row"><span class="toggle-copy"><strong>Iniciar InkDriver</strong><small>Disponibiliza o armazenamento integrado na porta configurada abaixo.</small></span><label class="switch"><input type="checkbox" name="auto_module" value="drive2" aria-label="Iniciar InkDriver" ${autoModules.has("drive2") ? "checked" : ""}><span></span></label></div>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Bridge Core</h2><p>Servidor, rede, armazenamento e agente Windows configurados pelo Workspace.</p></div><span class="badge ${state.modules.find(item => item.id === "bridge")?.reachable ? "online" : "warning"}">${state.modules.find(item => item.id === "bridge")?.reachable ? "online" : "parado"}</span></div>
        <div class="settings-grid">
          <div class="field"><label for="bridge-host">Interface de rede</label><input id="bridge-host" name="bridge_host" value="${escapeHtml(bridge.host || "0.0.0.0")}"><small>Use 0.0.0.0 para celular e outros aparelhos.</small></div>
          <div class="field"><label for="bridge-port">Porta do painel</label><input id="bridge-port" name="bridge_port" type="number" min="1" max="65535" value="${escapeHtml(bridge.port || 8876)}"></div>
          <div class="field"><label for="bridge-public-url">Endereço mostrado a outros aparelhos</label><input id="bridge-public-url" name="bridge_public_url" type="url" placeholder="Automático pela rede local" value="${escapeHtml(bridge.public_url || "")}"><small>Deixe vazio para detectar o IP do notebook.</small></div>
          <div class="field"><label for="bridge-discovery-port">Porta de descoberta</label><input id="bridge-discovery-port" name="bridge_discovery_port" type="number" min="1" max="65535" value="${escapeHtml(bridge.discovery_port || 48765)}"></div>
          <div class="field"><label for="bridge-chunk">Bloco de transferência (MB)</label><input id="bridge-chunk" name="bridge_chunk" type="number" min="1" max="64" value="${escapeHtml(bridge.max_chunk_mb || 4)}"></div>
          <div class="field"><label for="bridge-received">Pasta de arquivos recebidos</label><input id="bridge-received" name="bridge_received" placeholder="Padrão: bridge/received" value="${escapeHtml(bridge.received_dir || "")}"></div>
          <div class="field"><label for="bridge-data">Pasta do banco e identidade</label><input id="bridge-data" name="bridge_data" placeholder="Padrão: bridge/.data" value="${escapeHtml(bridge.data_dir || "")}"></div>
        </div>
        <details class="integration-details"><summary>HTTPS opcional</summary><div class="settings-grid">
          <div class="field"><label for="bridge-tls-cert">Certificado TLS</label><input id="bridge-tls-cert" name="bridge_tls_cert" placeholder="Caminho para cert.pem" value="${escapeHtml(bridge.tls_cert || "")}"></div>
          <div class="field"><label for="bridge-tls-key">Chave privada TLS</label><input id="bridge-tls-key" name="bridge_tls_key" placeholder="Caminho para key.pem" value="${escapeHtml(bridge.tls_key || "")}"></div>
        </div><p class="settings-live-note">Preencha os dois caminhos para servir o Bridge por HTTPS. Mantenha ambos vazios para HTTP local.</p></details>
        <div class="integration-actions"><button class="primary-button" type="button" data-apply-bridge>Salvar e reiniciar Bridge</button><button class="secondary-button" type="button" data-open-module="bridge">Abrir painel</button></div>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Bridge Agent no Windows</h2><p>Estas opções atualizam o perfil real do agente em %LOCALAPPDATA%\\Bridge.</p></div><span class="badge ${agent.paired ? "online" : "warning"}">${agent.paired ? "pareado" : "ainda não pareado"}</span></div>
        <div class="settings-grid">
          <div class="field"><label for="agent-name">Nome deste computador</label><input id="agent-name" name="agent_name" maxlength="80" value="${escapeHtml(agent.name)}"></div>
          <div class="field"><label for="agent-server">Endereço do Bridge usado pelo agente</label><input id="agent-server" name="agent_server" type="url" value="${escapeHtml(agent.server)}"></div>
        </div>
        ${permissionToggle("agent_clipboard", "Sincronizar área de transferência", "Compartilha texto com o primeiro celular/tablet disponível.", agent.clipboard_enabled)}
        ${permissionToggle("agent_remote_ring", "Permitir tocar alerta", "Permite localizar este computador com um alerta sonoro.", agent.permissions.remote_ring)}
        ${permissionToggle("agent_remote_actions", "Permitir ações remotas", "Permite abrir URLs, pastas dentro do perfil e notificações assinadas.", agent.permissions.remote_actions)}
        ${permissionToggle("agent_remote_lock", "Permitir bloquear a sessão", "Aceita o comando remoto assinado para bloquear o Windows.", agent.permissions.remote_lock)}
        ${permissionToggle("agent_photos", "Permitir solicitações de foto", "Habilita a permissão do agente para os fluxos de foto do Bridge.", agent.permissions.photos)}
        <div class="integration-actions"><button class="secondary-button" type="button" data-save-agent>Salvar perfil do agente</button><button class="ghost-button" type="button" data-copy-text="& '${escapeHtml("C:\\Users\\gugas\\OneDrive\\Desktop\\codigos\\bridge\\.venv\\Scripts\\python.exe")}' '${escapeHtml("C:\\Users\\gugas\\OneDrive\\Desktop\\codigos\\bridge\\windows-agent\\agent.py")}' --pair">Copiar comando para parear</button></div>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>InkDriver</h2><p>Use o serviço integrado neste computador ou conecte uma instalação remota pelo Tailscale.</p></div><span class="badge ${state.modules.find(item => item.id === "drive2")?.reachable ? "online" : "warning"}">${state.modules.find(item => item.id === "drive2")?.reachable ? "online" : "offline"}</span></div>
        <div class="settings-grid">
          <div class="field"><label for="driver-mode">Onde executar</label><select id="driver-mode" name="driver_mode"><option value="local" ${driver.run_local !== false ? "selected" : ""}>Neste computador</option><option value="remote" ${driver.run_local === false ? "selected" : ""}>No celular / servidor remoto</option></select><small>Escolha o celular para usar o endereço remoto abaixo.</small></div>
          <div class="field"><label for="drive-url">Endereço do celular</label><input id="drive-url" name="drive_url" type="url" placeholder="http://100.x.y.z:8000" value="${escapeHtml(settings.module_urls.drive2 || "")}"><small>IP do Tailscale ou domínio completo, incluindo http:// ou https://.</small></div>
          <div class="field"><label for="driver-host">Interface de rede</label><input id="driver-host" name="driver_host" value="${escapeHtml(driver.host || "127.0.0.1")}"><small>No modo local, o acesso é limitado automaticamente a 127.0.0.1.</small></div>
          <div class="field"><label for="driver-port">Porta</label><input id="driver-port" name="driver_port" type="number" min="1" max="65535" value="${escapeHtml(driver.port || 8000)}"></div>
          <div class="field"><label for="driver-storage">Pasta de arquivos</label><input id="driver-storage" name="driver_storage" value="${escapeHtml(driver.storage_root || "data/files")}"></div>
          <div class="field"><label for="driver-database">Banco SQLite</label><input id="driver-database" name="driver_database" value="${escapeHtml(driver.database || "drive2.db")}"></div>
          <div class="field"><label for="driver-upload">Upload máximo (MB)</label><input id="driver-upload" name="driver_upload" type="number" min="1" max="102400" value="${escapeHtml(driver.max_upload_mb || 1024)}"></div>
          <div class="field"><label for="driver-scan">Varredura dos arquivos (segundos)</label><input id="driver-scan" name="driver_scan" type="number" min="15" value="${escapeHtml(driver.scan_interval_seconds || 60)}"></div>
          <div class="field"><label for="driver-sync">Fila de sincronização (segundos)</label><input id="driver-sync" name="driver_sync" type="number" min="5" value="${escapeHtml(driver.sync_interval_seconds || 15)}"></div>
          <div class="field"><label for="driver-auth-user">Usuário da autenticação</label><input id="driver-auth-user" name="driver_auth_user" value="${escapeHtml(driver.auth_username || "admin")}"></div>
          <div class="field"><label for="driver-auth-hours">Duração da sessão (horas)</label><input id="driver-auth-hours" name="driver_auth_hours" type="number" min="1" max="720" value="${escapeHtml(driver.auth_session_hours || 24)}"></div>
          <div class="field"><label for="driver-password">Senha para gerar o hash</label><input id="driver-password" name="driver_password" type="password" minlength="8" autocomplete="new-password" placeholder="Não é salva pelo Workspace"><small>Usada somente ao gerar o .env.</small></div>
          <div class="field"><label for="driver-secret">Segredo de sessão</label><div class="inline-field"><input id="driver-secret" name="driver_secret" autocomplete="off" placeholder="Gerado automaticamente"><button class="secondary-button" type="button" data-generate-secret>Gerar</button></div></div>
        </div>
        ${permissionToggle("driver_tailscale_only", "Aceitar somente localhost e Tailscale", "Recomendado para o servidor no tablet.", driver.tailscale_only)}
        ${permissionToggle("driver_auth_enabled", "Ativar login no InkDriver", "O .env precisa conter senha e segredo quando ligado.", driver.auth_enabled)}
        ${permissionToggle("driver_auth_secure", "Cookie somente por HTTPS", "Ative apenas quando o InkDriver estiver publicado com HTTPS.", driver.auth_cookie_secure)}
        ${permissionToggle("driver_r2_enabled", "Ativar backup Cloudflare R2", "Inclui a seção R2 no arquivo gerado; preencha as credenciais avançadas abaixo.", driver.r2_enabled)}
        ${permissionToggle("driver_gmail_enabled", "Ativar arquivamento do Gmail", "Inclui o módulo do Gmail no perfil gerado.", driver.gmail_enabled)}
        <details class="integration-details"><summary>Pastas e execução avançada</summary><div class="settings-grid">
          <div class="field"><label for="driver-temp">Pasta temporária</label><input id="driver-temp" name="driver_temp" value="${escapeHtml(driver.temp_root || "data/temp")}"></div>
          <div class="field"><label for="driver-trash">Lixeira local</label><input id="driver-trash" name="driver_trash" value="${escapeHtml(driver.trash_root || "data/trash")}"></div>
          <div class="field"><label for="driver-emails">Pasta de e-mails</label><input id="driver-emails" name="driver_emails" value="${escapeHtml(driver.emails_root || "data/emails")}"></div>
          <div class="field"><label for="driver-attachments">Pasta de anexos</label><input id="driver-attachments" name="driver_attachments" value="${escapeHtml(driver.attachments_root || "data/attachments")}"></div>
          <div class="field"><label for="driver-log">Nível de log</label><select id="driver-log" name="driver_log"><option ${driver.log_level === "DEBUG" ? "selected" : ""}>DEBUG</option><option ${driver.log_level === "INFO" || !driver.log_level ? "selected" : ""}>INFO</option><option ${driver.log_level === "WARNING" ? "selected" : ""}>WARNING</option><option ${driver.log_level === "ERROR" ? "selected" : ""}>ERROR</option></select></div>
          <div class="field"><label for="driver-retries">Máximo de tentativas</label><input id="driver-retries" name="driver_retries" type="number" min="1" max="100" value="${escapeHtml(driver.sync_max_retries || 8)}"></div>
        </div></details>
        <details class="integration-details"><summary>Credenciais avançadas do R2 e Gmail</summary><div class="settings-grid">
          <div class="field"><label for="r2-account">R2 Account ID</label><input id="r2-account" name="r2_account"></div>
          <div class="field"><label for="r2-key">R2 Access Key ID</label><input id="r2-key" name="r2_key"></div>
          <div class="field"><label for="r2-secret">R2 Secret Access Key</label><input id="r2-secret" name="r2_secret" type="password" autocomplete="off"></div>
          <div class="field"><label for="r2-bucket">Bucket R2</label><input id="r2-bucket" name="r2_bucket" value="drive2-backup"></div>
          <div class="field"><label for="r2-endpoint">Endpoint R2</label><input id="r2-endpoint" name="r2_endpoint" type="url" placeholder="https://ACCOUNT_ID.r2.cloudflarestorage.com"></div>
          <div class="field"><label for="r2-region">Região R2</label><input id="r2-region" name="r2_region" value="${escapeHtml(driver.r2_region || "auto")}"></div>
          <div class="field"><label for="r2-prefix">Prefixo dos objetos</label><input id="r2-prefix" name="r2_prefix" value="${escapeHtml(driver.r2_prefix || "drive2")}"></div>
          <div class="field"><label for="gmail-credentials">Arquivo de credenciais Gmail</label><input id="gmail-credentials" name="gmail_credentials" value="${escapeHtml(driver.gmail_credentials_path || "config/gmail_credentials.json")}"></div>
          <div class="field"><label for="gmail-token">Token do Gmail</label><input id="gmail-token" name="gmail_token" value="${escapeHtml(driver.gmail_token_path || "config/gmail_token.json")}"></div>
          <div class="field"><label for="gmail-days">Arquivar após (dias)</label><input id="gmail-days" name="gmail_days" type="number" min="1" max="3650" value="${escapeHtml(driver.gmail_archive_after_days || 30)}"></div>
          <div class="field"><label for="gmail-max">Mensagem máxima (MB)</label><input id="gmail-max" name="gmail_max" type="number" min="1" max="1024" value="${escapeHtml(driver.gmail_max_message_mb || 50)}"></div>
        </div><p class="settings-live-note">Credenciais secretas ficam somente nos campos atuais e no arquivo baixado; não entram nas configurações globais do Workspace.</p></details>
        ${permissionToggle("gmail_protect_starred", "Proteger e-mails com estrela", "Não arquiva automaticamente mensagens marcadas com estrela.", driver.gmail_protect_starred !== false)}
        ${permissionToggle("gmail_protect_important", "Proteger e-mails importantes", "Não arquiva automaticamente mensagens marcadas como importantes.", driver.gmail_protect_important !== false)}
        ${permissionToggle("gmail_trash_after_backup", "Enviar à lixeira após backup validado", "Use somente depois de confirmar R2 e Gmail; o InkDriver valida o backup antes da lixeira.", driver.gmail_trash_after_backup)}
        <div class="integration-actions"><button class="primary-button" type="button" data-apply-driver>Salvar e aplicar InkDriver</button><button class="secondary-button" type="button" data-driver-env="download">Baixar .env</button><button class="secondary-button" type="button" data-driver-env="copy">Copiar .env</button><button class="secondary-button" type="button" data-open-module="drive2">Abrir InkDriver</button></div>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Backup do Workspace</h2><p>Leve configurações, favoritos, endereços e preferências para outra instalação.</p></div></div>
        <div class="backup-actions">
          <button class="primary-button" type="button" data-backup-export>Exportar backup geral</button>
          <label class="secondary-button backup-import-button">Importar backup<input id="workspace-backup-input" type="file" accept="application/json,.json"></label>
        </div>
        <p class="settings-live-note">O arquivo não inclui senhas digitadas, credenciais secretas nem os documentos internos de cada módulo.</p>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Modo portátil</h2><p>Crie um pacote seletivo para outro computador ou pendrive.</p></div></div>
        <div class="portable-sections" id="portable-sections">
          ${[["settings","Configurações"],["presets","Presets"],["clipboard","Clipboard"],["activity","Histórico"],["files","Arquivos recentes"],["modules","Dados autorizados dos módulos"]].map(([value,label]) => `<label><input type="checkbox" value="${value}" checked> ${label}</label>`).join("")}
        </div>
        <div class="backup-actions">
          <button class="primary-button" type="button" data-portable-export>Exportar pacote .zip</button>
          <label class="secondary-button backup-import-button">Importar pacote<input id="workspace-portable-input" type="file" accept="application/zip,.zip"></label>
        </div>
        <p class="settings-live-note">Para executar diretamente de um pendrive, use <code>iniciar-portatil.cmd</code>. Os dados serão guardados em <code>portable-data</code> ao lado do Workspace.</p>
      </section>
      <section class="panel">
        <div class="section-heading"><div><h2>Manual na interface</h2><p>Siga a ordem; os comandos possuem botão de cópia.</p></div></div>
        ${integrationManual()}
      </section>
      <button class="primary-button" type="submit">Salvar todas as configurações</button>
    </form>`;
}

function renderDiagnostics() {
  const diagnostics = state.diagnostics || {};
  const storage = diagnostics.storage || {};
  const activity = diagnostics.activity || {};
  const terminal = diagnostics.terminal || {};
  const browser = diagnostics.browser || {};
  const audit = diagnostics.audit || state.moduleAudit || {};
  const rows = state.modules.filter((module) => module.kind !== "planned").map((module) => {
    const info = statusInfo(module);
    const details = audit.modules?.find((item) => item.id === module.id) || {};
    const runtime = diagnostics.modules?.find((item) => item.id === module.id) || {};
    const issue = details.issues?.map((item) => item.message).join(" · ") || `${formatBytes(details.size || 0)} · SHA ${details.integrity || "—"}`;
    const cause = runtime.probableCause || details.issues?.[0]?.probableCause || "Nenhuma falha detectada.";
    const recovery = runtime.recoveryAction || details.issues?.[0]?.recoveryAction || "Nenhuma ação necessária.";
    return `<div class="diagnostic-row diagnostic-module-row"><strong>${escapeHtml(module.name)}</strong><div class="diagnostic-cause"><span>${escapeHtml(issue)}</span><small><b>Causa provável:</b> ${escapeHtml(cause)}</small><small><b>Recuperação:</b> ${escapeHtml(recovery)}</small></div><span class="badge ${info.className}">${escapeHtml(info.label)}</span><button class="ghost-button" data-repair-module="${escapeHtml(module.id)}">${module.kind === "web-service" ? "Reiniciar" : "Verificar"}</button></div>`;
  }).join("");
  const errors = (activity.recentErrors || []).map((item) => `<div class="diagnostic-row diagnostic-error"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.detail || "Sem detalhes")}</span><time>${escapeHtml(new Date(item.createdAt).toLocaleString("pt-BR"))}</time></div>`).join("");
  return `
    <section class="stats-grid diagnostic-summary">
      <article class="stat-card"><small>Core</small><strong>${escapeHtml(diagnostics.version || "—")}</strong><span>${escapeHtml(diagnostics.runtime || "carregando")}</span></article>
      <article class="stat-card"><small>Terminal local</small><strong>${terminal.available ? "Ativo" : "Indisponível"}</strong><span>Git ${terminal.gitAvailable ? "disponível" : "não encontrado"}</span></article>
      <article class="stat-card"><small>Drop Zone</small><strong>${Number(storage.dropzoneItems || 0)}</strong><span>${formatBytes(storage.dropzoneBytes || 0)} armazenados</span></article>
      <article class="stat-card"><small>Atividades</small><strong>${Number(activity.unread || 0)}</strong><span>não lidas de ${Number(activity.count || 0)}</span></article>
    </section>
    <section class="panel">
      <div class="section-heading"><div><h2>Compatibilidade e armazenamento</h2><p>Recursos usados pelo Core neste navegador e espaço disponível no computador.</p></div></div>
      <div class="diagnostic-list">
        <div class="diagnostic-row"><strong>Sincronização entre abas</strong><span>BroadcastChannel</span><span class="badge ${browser.broadcastChannel ? "online" : "warning"}">${browser.broadcastChannel ? "disponível" : "fallback"}</span></div>
        <div class="diagnostic-row"><strong>Armazenamento do navegador</strong><span>${formatBytes(browser.usage || 0)} usados</span><span class="badge ${browser.indexedDb ? "online" : "warning"}">${browser.indexedDb ? "IndexedDB disponível" : "indisponível"}</span></div>
        <div class="diagnostic-row"><strong>Disco local</strong><span>${formatBytes(storage.diskFree || 0)} livres</span><span class="badge online">${formatBytes(storage.diskTotal || 0)} total</span></div>
        <div class="diagnostic-row"><strong>Início com o Windows</strong><span>${diagnostics.startup?.path ? "atalho configurável" : "não detectado"}</span><span class="badge ${diagnostics.startup?.enabled ? "online" : "warning"}">${diagnostics.startup?.enabled ? "ativo" : "desativado"}</span></div>
      </div>
    </section>
    <section class="panel">
      <div class="section-heading"><div><h2>Estado dos módulos</h2><p>O teste verifica pastas locais e portas dos serviços, sem enviar telemetria.</p></div><button class="secondary-button" id="diagnostic-refresh">Executar novamente</button></div>
      <div class="diagnostic-list">${rows}</div>
    </section>
    ${(diagnostics.findings || []).length ? `<section class="panel"><div class="section-heading"><div><h2>Causas e ações recomendadas</h2><p>Problemas do Core que merecem atenção.</p></div></div><div class="diagnostic-list">${diagnostics.findings.map((item) => `<div class="diagnostic-row diagnostic-finding"><strong>${escapeHtml(item.title)}</strong><div class="diagnostic-cause"><small><b>Causa provável:</b> ${escapeHtml(item.probableCause)}</small><small><b>Recuperação:</b> ${escapeHtml(item.recoveryAction)}</small></div><span class="badge ${item.level === "error" ? "warning" : ""}">${escapeHtml(item.code)}</span></div>`).join("")}</div></section>` : ""}
    <section class="panel"><div class="section-heading"><div><h2>Manifestos e portas</h2><p>Conflitos e arquivos de módulo inválidos detectados pelo Core.</p></div></div>
      <div class="diagnostic-list">
        ${(audit.portConflicts || []).map((item) => `<div class="diagnostic-row"><strong>Porta ${item.port}</strong><span>${escapeHtml(item.modules.join(", "))}</span><span class="badge warning">conflito</span></div>`).join("")}
        ${(audit.manifestErrors || []).map((item) => `<div class="diagnostic-row diagnostic-error"><strong>Manifesto inválido</strong><span>${escapeHtml(item)}</span><span class="badge warning">erro</span></div>`).join("")}
        ${!(audit.portConflicts?.length || audit.manifestErrors?.length) ? `<div class="empty">Nenhum conflito de porta ou manifesto encontrado.</div>` : ""}
      </div>
    </section>
    <section class="panel"><div class="section-heading"><div><h2>Erros recentes</h2><p>Falhas persistidas pela Home, Terminal e integrações compartilhadas.</p></div><button class="secondary-button" type="button" data-open-activity>Abrir atividades</button></div><div class="diagnostic-list">${errors || `<div class="empty">Nenhum erro recente registrado.</div>`}</div></section>
    <section class="panel"><h2>Recuperação</h2><p class="muted">Se o painel não abrir após reiniciar, execute o atalho abaixo. Os logs JSONL rotativos ficam em <code>logs/modules</code> dentro da pasta de dados.</p><div class="code-box">${escapeHtml(state.diagnostics?.ecosystemRoot || "...")}\\workspace-os\\iniciar-workspace.cmd</div><div class="code-box">Dados: ${escapeHtml(state.diagnostics?.dataDirectory || "%LOCALAPPDATA%\\WorkspaceOS")}</div></section>`;
}

function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes || 0), unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

async function loadDiagnostics() {
  const diagnostics = await api("/api/diagnostics");
  let estimate = {};
  try { estimate = await navigator.storage?.estimate?.() || {}; } catch { /* opcional */ }
  diagnostics.browser = {
    broadcastChannel: "BroadcastChannel" in window,
    indexedDb: "indexedDB" in window,
    usage: estimate.usage || 0,
    quota: estimate.quota || 0,
  };
  return diagnostics;
}

function render() {
  if (!state.settings) return;
  const raiz = document.querySelector("#content");
  const renderers = {
    dashboard: renderDashboard,
    modules: renderModules,
    setup: renderSetup,
    settings: renderSettings,
    diagnostics: renderDiagnostics,
  };
  document.querySelector("#content").innerHTML = renderers[state.route]();
  I18n.apply(document.querySelector("#content"));
  if (state.route === "settings") {
    for (const control of document.querySelectorAll("[data-global-setting]")) {
      const value = state.settings[control.dataset.globalSetting];
      if (control.type === "checkbox") control.checked = Boolean(value); else control.value = value;
    }
  }
}

function renderCommandResults(query = "") {
  const container = document.querySelector("#command-results");
  if (!container) return;
  state.commandResults = filterCommands(buildCommands(state.modules, { activities: state.activities, dropItems: state.dropItems }), query);
  state.commandSelection = 0;
  container.innerHTML = state.commandResults.length
    ? state.commandResults.map((command, index) => `
      <button class="command-result ${index === 0 ? "selected" : ""}" type="button" role="option" aria-selected="${index === 0}" data-command-index="${index}">
        <span class="command-result-icon">${command.route ? "→" : "▦"}</span>
        <span><strong>${escapeHtml(command.label)}</strong><small>${escapeHtml(command.description)}</small></span>
      </button>`).join("")
    : `<div class="command-empty"><strong>Nenhum resultado</strong><span>Tente buscar pelo nome da ferramenta ou pela ação.</span></div>`;
}

function selectCommand(index) {
  if (!state.commandResults.length) return;
  state.commandSelection = (index + state.commandResults.length) % state.commandResults.length;
  document.querySelectorAll(".command-result").forEach((element, itemIndex) => {
    const selected = itemIndex === state.commandSelection;
    element.classList.toggle("selected", selected);
    element.setAttribute("aria-selected", String(selected));
    if (selected) element.scrollIntoView({ block: "nearest" });
  });
}

function openCommandPalette() {
  const dialog = document.querySelector("#command-dialog");
  if (!dialog.open) dialog.showModal();
  const input = document.querySelector("#command-input");
  input.value = "";
  renderCommandResults();
  window.setTimeout(() => input.focus(), 0);
}

function closeCommandPalette() {
  const dialog = document.querySelector("#command-dialog");
  if (dialog.open) dialog.close();
}

async function executeCommand(command) {
  if (!command) return;
  closeCommandPalette();
  if (command.route) {
    if (command.route === "diagnostics") state.diagnostics = await loadDiagnostics();
    navigate(command.route);
    return;
  }
  if (command.action === "configure") return navigate("settings");
  if (command.action === "terminal") return window.WorkspaceTerminal?.open();
  if (command.action === "dropzone") return window.WorkspaceDropzone?.open();
  if (command.action === "activity") return window.WorkspaceActivity?.open();
  if (command.action === "open-url" && command.url) return location.assign(command.url);
  if (command.action === "backup") {
    try { await downloadWorkspaceBackup(); toast("Backup geral exportado."); }
    catch (error) { toast(`Não foi possível exportar o backup: ${error.message}`, "error"); }
    return;
  }
  if (command.action === "portable") {
    try { await downloadPortableArchive(); toast("Pacote portátil exportado."); }
    catch (error) { toast(`Não foi possível exportar: ${error.message}`, "error"); }
    return;
  }
  if (command.action === "reload-modules") {
    try { await api("/api/modules/reload", { method: "POST", body: "{}" }); await loadState(); toast("Manifestos recarregados."); }
    catch (error) { toast(`Falha ao recarregar: ${error.message}`, "error"); }
    return;
  }
  if (command.action === "start") return startModule(command.moduleId);
  const module = state.modules.find((item) => item.id === command.moduleId);
  abrirNoWorkspace(module);
}

async function toggleSidebar() {
  const previous = state.settings.sidebar_collapsed;
  state.settings.sidebar_collapsed = !previous;
  applyAppearance();
  try {
    state.settings = await Settings.set("sidebar_collapsed", state.settings.sidebar_collapsed);
    state.settingsDirty = false;
    applyAppearance();
  } catch (error) {
    state.settings.sidebar_collapsed = previous;
    applyAppearance();
    toast(`Não foi possível ajustar a barra lateral: ${error.message}`, "error");
  }
}

async function startModule(moduleId, { openWhenReady = false } = {}) {
  try {
    const result = await api(`/api/modules/${encodeURIComponent(moduleId)}/start`, { method: "POST", body: "{}" });
    toast(result.message || "Módulo iniciado.");
    for (let attempt = 0; attempt < 6; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 700));
      const payload = await api("/api/modules");
      state.modules = payload.modules;
      const module = state.modules.find((item) => item.id === moduleId);
      if (!module || module.reachable || module.kind === "desktop") break;
    }
    render();
    const module = state.modules.find((item) => item.id === moduleId);
    if (openWhenReady && module?.reachable) abrirNoWorkspace(module);
  } catch (error) { toast(error.message, "error"); }
}

async function stopModule(moduleId) {
  try {
    const result = await api(`/api/modules/${encodeURIComponent(moduleId)}/stop`, { method: "POST", body: "{}" });
    toast(result.message, result.ok ? "success" : "error");
    await loadState({ quiet: true });
  } catch (error) { toast(error.message, "error"); }
}

async function changeStartup(action) {
  try {
    state.startup = await api(`/api/startup/${action}`, { method: "POST", body: "{}" });
    toast(action === "enable" ? "Workspace OS ativado para iniciar com o Windows." : "Inicialização automática desativada.");
    render();
  } catch (error) { toast(error.message, "error"); }
}

function numberField(data, name) {
  return Number.parseInt(String(data.get(name) || "0"), 10);
}

function readModuleConfigs(form) {
  const data = new FormData(form);
  return {
    bridge: {
      host: String(data.get("bridge_host") || "0.0.0.0").trim(),
      port: numberField(data, "bridge_port"),
      public_url: String(data.get("bridge_public_url") || "").trim(),
      discovery_port: numberField(data, "bridge_discovery_port"),
      max_chunk_mb: numberField(data, "bridge_chunk"),
      data_dir: String(data.get("bridge_data") || "").trim(),
      received_dir: String(data.get("bridge_received") || "").trim(),
      tls_cert: String(data.get("bridge_tls_cert") || "").trim(),
      tls_key: String(data.get("bridge_tls_key") || "").trim(),
    },
    drive2: {
      run_local: data.get("driver_mode") !== "remote",
      host: String(data.get("driver_host") || "0.0.0.0").trim(),
      port: numberField(data, "driver_port"),
      storage_root: String(data.get("driver_storage") || "data/files").trim(),
      database: String(data.get("driver_database") || "drive2.db").trim(),
      temp_root: String(data.get("driver_temp") || "data/temp").trim(),
      trash_root: String(data.get("driver_trash") || "data/trash").trim(),
      emails_root: String(data.get("driver_emails") || "data/emails").trim(),
      attachments_root: String(data.get("driver_attachments") || "data/attachments").trim(),
      log_level: String(data.get("driver_log") || "INFO").trim(),
      max_upload_mb: numberField(data, "driver_upload"),
      sync_max_retries: numberField(data, "driver_retries"),
      scan_interval_seconds: numberField(data, "driver_scan"),
      sync_interval_seconds: numberField(data, "driver_sync"),
      tailscale_only: data.get("driver_tailscale_only") === "on",
      auth_enabled: data.get("driver_auth_enabled") === "on",
      auth_username: String(data.get("driver_auth_user") || "admin").trim(),
      auth_cookie_secure: data.get("driver_auth_secure") === "on",
      auth_session_hours: numberField(data, "driver_auth_hours"),
      r2_enabled: data.get("driver_r2_enabled") === "on",
      r2_region: String(data.get("r2_region") || "auto").trim(),
      r2_prefix: String(data.get("r2_prefix") || "drive2").trim(),
      gmail_enabled: data.get("driver_gmail_enabled") === "on",
      gmail_credentials_path: String(data.get("gmail_credentials") || "config/gmail_credentials.json").trim(),
      gmail_token_path: String(data.get("gmail_token") || "config/gmail_token.json").trim(),
      gmail_archive_after_days: numberField(data, "gmail_days"),
      gmail_max_message_mb: numberField(data, "gmail_max"),
      gmail_protect_starred: data.get("gmail_protect_starred") === "on",
      gmail_protect_important: data.get("gmail_protect_important") === "on",
      gmail_trash_after_backup: data.get("gmail_trash_after_backup") === "on",
    },
  };
}

async function saveBridgeAgent(form) {
  const data = new FormData(form);
  const payload = {
    name: String(data.get("agent_name") || "").trim(),
    server: String(data.get("agent_server") || "").trim(),
    clipboard_enabled: data.get("agent_clipboard") === "on",
    permissions: {
      remote_ring: data.get("agent_remote_ring") === "on",
      remote_actions: data.get("agent_remote_actions") === "on",
      remote_lock: data.get("agent_remote_lock") === "on",
      photos: data.get("agent_photos") === "on",
    },
  };
  state.bridgeAgent = await api("/api/integrations/bridge-agent", { method: "POST", body: JSON.stringify(payload) });
  state.settingsDirty = false;
  toast("Perfil do Bridge Agent salvo.");
  return state.bridgeAgent;
}

async function saveSettings(form, { restartBridge = false, restartDriver = false } = {}) {
  const data = new FormData(form);
  const configs = readModuleConfigs(form);
  const driveUrl = String(data.get("drive_url") || "").trim().replace(/\/$/, "");
  try {
    if (driveUrl) {
      const parsed = new URL(driveUrl);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Use um endereço http:// ou https:// para o InkDriver.");
    }
    if (!configs.drive2.run_local && !driveUrl) {
      throw new Error("Informe o endereço do InkDriver no celular para usar o modo remoto.");
    }
    const moduleUrls = { ...(state.settings.module_urls || {}) };
    if (driveUrl) moduleUrls.drive2 = driveUrl; else delete moduleUrls.drive2;
    moduleUrls.bridge = `http://127.0.0.1:${configs.bridge.port}`;
    state.settings = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        open_panel_on_start: data.get("open_panel_on_start") === "on",
        auto_start_modules: data.getAll("auto_module").filter((moduleId) => configs.drive2.run_local || moduleId !== "drive2"),
        module_urls: moduleUrls,
        module_configs: configs,
      }),
    });
    applyAppearance();
    state.settingsDirty = false;
    if (restartBridge) {
      await api("/api/modules/bridge/stop", { method: "POST", body: "{}" }).catch(() => null);
      const result = await api("/api/modules/bridge/start", { method: "POST", body: "{}" });
      toast(result.message || "Bridge reiniciado com a nova configuração.");
    } else if (restartDriver) {
      await api("/api/modules/drive2/stop", { method: "POST", body: "{}" }).catch(() => null);
      if (configs.drive2.run_local) {
        const result = await api("/api/modules/drive2/start", { method: "POST", body: "{}" });
        toast(result.message || "InkDriver reiniciado com a nova configuração.");
      } else {
        toast("InkDriver conectado ao celular.");
      }
    } else {
      toast("Inicialização e integrações salvas.");
    }
    await loadState({ quiet: true });
  } catch (error) { toast(error.message, "error"); }
}

function bytesToBase64Url(bytes, { stripPadding = false } = {}) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  const encoded = btoa(binary).replaceAll("+", "-").replaceAll("/", "_");
  return stripPadding ? encoded.replace(/=+$/, "") : encoded;
}

async function passwordHash(password) {
  if (password.length < 8) throw new Error("A senha do InkDriver precisa ter pelo menos 8 caracteres.");
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  const digest = new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: 310000 }, key, 256));
  return `pbkdf2_sha256$310000$${bytesToBase64Url(salt)}$${bytesToBase64Url(digest)}`;
}

function generateSecret() {
  return bytesToBase64Url(crypto.getRandomValues(new Uint8Array(48)), { stripPadding: true });
}

async function driverEnvironment(form) {
  const data = new FormData(form);
  const config = readModuleConfigs(form).drive2;
  const enabled = (value) => value ? "true" : "false";
  let secret = String(data.get("driver_secret") || "").trim();
  let hash = "";
  if (config.auth_enabled) {
    hash = await passwordHash(String(data.get("driver_password") || ""));
    if (!secret) {
      secret = generateSecret();
      form.elements.driver_secret.value = secret;
    }
  }
  return [
    "# InkDriver · gerado pelo Workspace OS",
    `DRIVE2_HOST=${config.host}`,
    `DRIVE2_PORT=${config.port}`,
    `DRIVE2_STORAGE_ROOT=${config.storage_root}`,
    `DRIVE2_DATABASE=${config.database}`,
    `DRIVE2_TEMP_ROOT=${config.temp_root}`,
    `DRIVE2_TRASH_ROOT=${config.trash_root}`,
    `DRIVE2_EMAILS_ROOT=${config.emails_root}`,
    `DRIVE2_ATTACHMENTS_ROOT=${config.attachments_root}`,
    `DRIVE2_LOG_LEVEL=${config.log_level}`,
    `DRIVE2_MAX_UPLOAD_MB=${config.max_upload_mb}`,
    `DRIVE2_SCAN_INTERVAL_SECONDS=${config.scan_interval_seconds}`,
    `DRIVE2_SYNC_INTERVAL_SECONDS=${config.sync_interval_seconds}`,
    `DRIVE2_SYNC_MAX_RETRIES=${config.sync_max_retries}`,
    `DRIVE2_TAILSCALE_ONLY=${enabled(config.tailscale_only)}`,
    "",
    `DRIVE2_AUTH_ENABLED=${enabled(config.auth_enabled)}`,
    `DRIVE2_AUTH_USERNAME=${config.auth_username}`,
    `DRIVE2_AUTH_PASSWORD_HASH=${hash}`,
    `DRIVE2_AUTH_SECRET=${secret}`,
    `DRIVE2_AUTH_COOKIE_SECURE=${enabled(config.auth_cookie_secure)}`,
    `DRIVE2_AUTH_SESSION_HOURS=${config.auth_session_hours}`,
    "",
    `R2_ENABLED=${enabled(config.r2_enabled)}`,
    `R2_ACCOUNT_ID=${String(data.get("r2_account") || "").trim()}`,
    `R2_ACCESS_KEY_ID=${String(data.get("r2_key") || "").trim()}`,
    `R2_SECRET_ACCESS_KEY=${String(data.get("r2_secret") || "").trim()}`,
    `R2_BUCKET=${String(data.get("r2_bucket") || "drive2-backup").trim()}`,
    `R2_ENDPOINT=${String(data.get("r2_endpoint") || "").trim()}`,
    `R2_REGION=${config.r2_region}`,
    `R2_PREFIX=${config.r2_prefix}`,
    "",
    `GMAIL_ENABLED=${enabled(config.gmail_enabled)}`,
    `GMAIL_CREDENTIALS_PATH=${config.gmail_credentials_path}`,
    `GMAIL_TOKEN_PATH=${config.gmail_token_path}`,
    `GMAIL_ARCHIVE_AFTER_DAYS=${config.gmail_archive_after_days}`,
    `GMAIL_MAX_MESSAGE_MB=${config.gmail_max_message_mb}`,
    `GMAIL_PROTECT_STARRED=${enabled(config.gmail_protect_starred)}`,
    `GMAIL_PROTECT_IMPORTANT=${enabled(config.gmail_protect_important)}`,
    `GMAIL_TRASH_AFTER_BACKUP=${enabled(config.gmail_trash_after_backup)}`,
    "",
  ].join("\n");
}

async function copyText(value, message = "Texto copiado.") {
  await navigator.clipboard.writeText(value);
  toast(message);
}

async function exportDriverEnvironment(form, mode) {
  try {
    const contents = await driverEnvironment(form);
    if (mode === "copy") return await copyText(contents, "Conteúdo do .env copiado.");
    const url = URL.createObjectURL(new Blob([contents], { type: "text/plain;charset=utf-8" }));
    const anchor = Object.assign(document.createElement("a"), { href: url, download: "drive2.env" });
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Arquivo drive2.env gerado. Renomeie para .env no tablet.");
  } catch (error) { toast(error.message, "error"); }
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("button");
  if (!target) return;
  if (target.dataset.commandIndex !== undefined) {
    await executeCommand(state.commandResults[Number(target.dataset.commandIndex)]);
    return;
  }
  if (target.id === "command-trigger") return openCommandPalette();
  if (target.id === "command-close") return closeCommandPalette();
  if (target.id === "sidebar-collapse-button") return toggleSidebar();
  if (target.dataset.copyText !== undefined) {
    try { await copyText(target.dataset.copyText); }
    catch (error) { toast(`Não foi possível copiar: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.generateSecret !== undefined) {
    const field = document.querySelector('[name="driver_secret"]');
    if (field) field.value = generateSecret();
    state.settingsDirty = true;
    toast("Segredo de sessão gerado. Ele será incluído no .env.");
    return;
  }
  if (target.dataset.driverEnv) {
    await exportDriverEnvironment(document.querySelector("#settings-form"), target.dataset.driverEnv);
    return;
  }
  if (target.dataset.saveAgent !== undefined) {
    try { await saveBridgeAgent(document.querySelector("#settings-form")); }
    catch (error) { toast(error.message, "error"); }
    return;
  }
  if (target.dataset.applyBridge !== undefined) {
    await saveSettings(document.querySelector("#settings-form"), { restartBridge: true });
    return;
  }
  if (target.dataset.applyDriver !== undefined) {
    await saveSettings(document.querySelector("#settings-form"), { restartDriver: true });
    return;
  }
  if (target.dataset.backupExport !== undefined) {
    try { await downloadWorkspaceBackup(); toast("Backup geral exportado."); }
    catch (error) { toast(`Não foi possível exportar o backup: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.portableExport !== undefined) {
    const sections = [...document.querySelectorAll("#portable-sections input:checked")].map((input) => input.value);
    try { const result = await downloadPortableArchive(sections); toast(`Pacote portátil criado (${formatBytes(result.size)}).`); }
    catch (error) { toast(`Não foi possível criar o pacote: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.reloadModules !== undefined) {
    try { await api("/api/modules/reload", { method: "POST", body: "{}" }); await loadState(); await loadModulePlatform(); toast("Manifestos recarregados."); }
    catch (error) { toast(`Falha ao recarregar: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.toggleModule) {
    const action = target.dataset.enable === "true" ? "enable" : "disable";
    try { await api(`/api/modules/${encodeURIComponent(target.dataset.toggleModule)}/${action}`, { method: "POST", body: "{}" }); await loadState(); toast(action === "enable" ? "Módulo ativado." : "Módulo desativado."); }
    catch (error) { toast(`Não foi possível alterar o módulo: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.gitModule) {
    const moduleId = target.dataset.gitModule;
    try {
      const git = await api(`/api/modules/${encodeURIComponent(moduleId)}/git-status`, { method: "POST", body: JSON.stringify({ fetch: true }) });
      state.gitProjects[moduleId] = git; render();
      if (git.dirty) return toast(`${git.branch}: existem alterações locais; atualização bloqueada.`, "error");
      if (!git.behind) return toast(`${git.branch}: projeto atualizado.`);
      if (window.confirm(`Há ${git.behind} atualização(ões) para ${moduleId}. Aplicar com fast-forward?`)) {
        const result = await api(`/api/modules/${encodeURIComponent(moduleId)}/git-update`, { method: "POST", body: "{}" });
        state.gitProjects[moduleId] = result.status; render(); toast(result.message);
      }
    } catch (error) { toast(`Git: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.repairModule) {
    const module = state.modules.find((item) => item.id === target.dataset.repairModule);
    try {
      if (module?.kind === "web-service") await api(`/api/modules/${encodeURIComponent(module.id)}/restart`, { method: "POST", body: "{}" });
      else await api("/api/modules/reload", { method: "POST", body: "{}" });
      state.diagnostics = await loadDiagnostics(); await loadState(); toast(module?.kind === "web-service" ? "Serviço reiniciado." : "Módulo verificado novamente.");
    } catch (error) { toast(`Não foi possível reparar: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.openActivity !== undefined) { window.WorkspaceActivity?.open(); return; }
  if (target.dataset.moveFavorite) {
    const favorites = [...(state.settings.favorite_modules || [])];
    const index = favorites.indexOf(target.dataset.moveFavorite);
    const nextIndex = index + Number(target.dataset.direction || 0);
    if (index < 0 || nextIndex < 0 || nextIndex >= favorites.length) return;
    [favorites[index], favorites[nextIndex]] = [favorites[nextIndex], favorites[index]];
    try {
      state.settings = await Settings.set("favorite_modules", favorites);
      render();
    } catch (error) { toast(`Não foi possível ordenar os favoritos: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.favoriteModule) {
    const moduleId = target.dataset.favoriteModule;
    const favorites = new Set(state.settings.favorite_modules || []);
    if (favorites.has(moduleId)) favorites.delete(moduleId); else favorites.add(moduleId);
    try {
      state.settings = await Settings.set("favorite_modules", [...favorites]);
      render();
      toast(favorites.has(moduleId) ? "Adicionado aos favoritos." : "Removido dos favoritos.");
    } catch (error) { toast(`Não foi possível atualizar os favoritos: ${error.message}`, "error"); }
    return;
  }
  if (target.dataset.route) navigate(target.dataset.route);
  if (target.dataset.filter) { state.filter = target.dataset.filter; render(); }
  if (target.dataset.openModule) {
    const module = state.modules.find((item) => item.id === target.dataset.openModule);
    abrirNoWorkspace(module);
  }
  if (target.dataset.useModule) await startModule(target.dataset.useModule, { openWhenReady: true });
  if (target.dataset.startModule) await startModule(target.dataset.startModule);
  if (target.dataset.stopModule) await stopModule(target.dataset.stopModule);
  if (target.dataset.startupAction) await changeStartup(target.dataset.startupAction);
  if (target.id === "refresh-button" || target.id === "diagnostic-refresh") {
    if (state.route === "diagnostics") state.diagnostics = await loadDiagnostics();
    await loadState();
    toast("Estado atualizado.");
  }
});

document.addEventListener("submit", (event) => {
  if (event.target.id === "yasmin-settings-chat-form") {
    event.preventDefault();
    const form = event.target;
    const input = form.querySelector("input");
    const texto = input.value.trim();
    if (!texto || form.dataset.busy === "true") return;
    input.value = "";
    form.dataset.busy = "true";
    form.querySelector("button").disabled = true;
    const append = (role, message) => {
      settingsConversation.push({ role, text: String(message) });
      if (settingsConversation.length > 30) settingsConversation.shift();
      const area = document.querySelector("#yasmin-settings-messages");
      if (!area) return;
      area.querySelector(".muted")?.remove();
      const row = document.createElement("p");
      row.className = `yasmin-settings-message ${role}`;
      const label = document.createElement("strong");
      label.textContent = role === "user" ? "Você" : "Yasmin";
      const content = document.createElement("span");
      content.textContent = String(message);
      row.append(label, content);
      area.append(row);
      area.scrollTop = area.scrollHeight;
    };
    append("user", texto);
    api("/api/yasmin/command", { method: "POST", body: JSON.stringify({ texto }) })
      .then((data) => append("assistant", data.resposta || "Não recebi uma resposta."))
      .catch((error) => append("assistant", `Não consegui conversar agora: ${error.message}`))
      .finally(() => { form.dataset.busy = "false"; form.querySelector("button").disabled = false; });
    return;
  }
  if (event.target.id === "module-install-form") {
    event.preventDefault();
    const data = new FormData(event.target);
    const type = String(data.get("type") || "folder");
    const source = String(data.get("source") || "").trim();
    api("/api/modules/install", {
      method: "POST", body: JSON.stringify(type === "git" ? { type, repository: source, name: String(data.get("name") || "").trim() } : { type, path: source }),
    }).then(async (result) => { toast(result.message); await loadState(); await loadModulePlatform(); event.target.reset(); })
      .catch((error) => toast(`Não foi possível instalar: ${error.message}`, "error"));
    return;
  }
  if (event.target.id === "settings-form") {
    event.preventDefault();
    saveSettings(event.target);
  }
});

document.addEventListener("input", (event) => {
  if (event.target.matches('[data-global-setting="accent"]')) {
    state.settings = { ...state.settings, accent: event.target.value };
    applyAppearance();
    document.querySelector("#accent-value").textContent = event.target.value.toUpperCase();
    return;
  }
  if (event.target.closest("#settings-form") && !event.target.dataset.globalSetting) state.settingsDirty = true;
});

document.addEventListener("change", async (event) => {
  if (event.target.id === "workspace-portable-input") {
    const [file] = event.target.files || [];
    if (!file) return;
    try {
      const info = await inspectPortableArchive(file);
      const sections = [...document.querySelectorAll("#portable-sections input:checked")].map((input) => input.value).filter((value) => info.sections.includes(value));
      const summary = Object.entries(info.counts || {}).map(([key, value]) => `${key}: ${value}`).join(" · ");
      if (window.confirm(`Pacote de ${new Date(info.createdAt).toLocaleString("pt-BR")}\n${summary}\n\nRestaurar as seções selecionadas?`)) {
        const restored = await restorePortableArchive(file, sections);
        if (restored.relocated || restored.pathWarnings?.length) {
          window.alert(`Pacote restaurado em um novo local. O Workspace adaptou a raiz do ecossistema. ${restored.pathWarnings?.length || 0} caminho(s) externo(s) precisam ser revisados em Configurações.`);
        }
        toast("Pacote restaurado. Recarregando o Workspace…");
        window.setTimeout(() => location.reload(), 700);
      }
    } catch (error) { toast(`Não foi possível importar o pacote: ${error.message}`, "error"); }
    event.target.value = "";
    return;
  }
  if (event.target.id === "workspace-backup-input") {
    const [file] = event.target.files || [];
    if (!file) return;
    if (!window.confirm("Restaurar este backup substituirá as configurações atuais do Workspace. Continuar?")) { event.target.value = ""; return; }
    try {
      await restoreWorkspaceBackup(file);
      toast("Backup restaurado. Recarregando o Workspace…");
      window.setTimeout(() => location.reload(), 700);
    } catch (error) { toast(`Não foi possível restaurar: ${error.message}`, "error"); }
    return;
  }
  if (event.target.dataset.shortcut) {
    const shortcuts = { ...(state.settings.keyboard_shortcuts || {}), [event.target.dataset.shortcut]: event.target.value.trim() };
    try { state.settings = await Settings.set("keyboard_shortcuts", shortcuts); toast("Atalho atualizado."); }
    catch (error) { toast(`Atalho inválido: ${error.message}`, "error"); }
    return;
  }
  const key = event.target.dataset.globalSetting;
  if (key) {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    state.settings = { ...state.settings, [key]: value };
    applyAppearance();
    try { state.settings = await Settings.set(key, value); }
    catch (error) { toast(`Não foi possível salvar a aparência: ${error.message}`, "error"); }
    return;
  }
  if (event.target.closest("#settings-form")) state.settingsDirty = true;
});

document.querySelector("#menu-button").addEventListener("click", () => {
  document.querySelector("#sidebar").classList.toggle("open");
});

document.querySelector("#sidebar-backdrop").addEventListener("click", () => {
  document.querySelector("#sidebar").classList.remove("open");
});

document.querySelector("#command-input").addEventListener("input", (event) => {
  renderCommandResults(event.target.value);
});

document.querySelector("#command-dialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeCommandPalette();
});

document.addEventListener("keydown", async (event) => {
  const dialog = document.querySelector("#command-dialog");
  if (!dialog.open) return;
  if (event.key === "ArrowDown") { event.preventDefault(); selectCommand(state.commandSelection + 1); }
  if (event.key === "ArrowUp") { event.preventDefault(); selectCommand(state.commandSelection - 1); }
  if (event.key === "Enter") {
    event.preventDefault();
    await executeCommand(state.commandResults[state.commandSelection]);
  }
});

let draggedFavorite = "";
document.addEventListener("dragstart", (event) => {
  const card = event.target.closest?.(".dashboard-grid [data-module-card]");
  if (!card) return;
  draggedFavorite = card.dataset.moduleCard;
  card.classList.add("dragging");
  event.dataTransfer.effectAllowed = "move";
});
document.addEventListener("dragend", (event) => { event.target.closest?.("[data-module-card]")?.classList.remove("dragging"); draggedFavorite = ""; });
document.addEventListener("dragover", (event) => { if (draggedFavorite && event.target.closest?.(".dashboard-grid [data-module-card]")) event.preventDefault(); });
document.addEventListener("drop", async (event) => {
  const target = event.target.closest?.(".dashboard-grid [data-module-card]");
  if (!target || !draggedFavorite || target.dataset.moduleCard === draggedFavorite) return;
  event.preventDefault();
  const favorites = [...(state.settings.favorite_modules || [])];
  const from = favorites.indexOf(draggedFavorite), to = favorites.indexOf(target.dataset.moduleCard);
  if (from < 0 || to < 0) return;
  favorites.splice(to, 0, favorites.splice(from, 1)[0]);
  state.settings = await Settings.set("favorite_modules", favorites);
  render();
});

Settings.subscribe((settings) => {
  if (!state.settings) return;
  state.settings = { ...state.settings, ...settings };
  applyAppearance();
  if (state.route === "settings") {
    for (const control of document.querySelectorAll("[data-global-setting]")) {
      const value = state.settings[control.dataset.globalSetting];
      if (control.type === "checkbox") control.checked = Boolean(value); else control.value = value;
    }
    const output = document.querySelector("#accent-value");
    if (output) output.textContent = state.settings.accent.toUpperCase();
  } else if (state.route === "dashboard") render();
}, { immediate: false });

document.addEventListener("workspace:activity", () => {
  Promise.all([api("/api/activity"), api("/api/dropzone/history")]).then(([activities, dropzone]) => {
    state.activities = activities.items || [];
    state.dropItems = dropzone.items || [];
  }).catch(() => {});
});

window.setInterval(() => loadState({ quiet: true }), 15000);
loadDiagnostics().then((data) => { state.diagnostics = data; if (state.route === "diagnostics" && state.settings) render(); }).catch(() => {});
const initialRoute = location.hash.slice(1);
if (initialRoute in pageTitles) {
  state.route = initialRoute;
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.route === initialRoute));
  document.querySelector("#page-title").textContent = pageTitles[initialRoute];
}
Settings.init().finally(async () => { await loadState(); if (["modules", "diagnostics"].includes(state.route)) await loadModulePlatform(); });
mountYasminDock({ onModule: abrirNoWorkspace });
window.WorkspaceTerminal = mountTerminal();
window.WorkspaceDropzone = mountUniversalDropzone();
window.WorkspaceActivity = mountActivityCenter();
mountShortcuts({ search: openCommandPalette });
I18n.observe();
BlackBox.start("workspace");
observeExports({ moduleId: "workspace" });
