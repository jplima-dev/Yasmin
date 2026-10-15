(() => {
  const state = {
    project: null,
    currentView: "overview",
    fileSearch: "",
    language: "pt",
  };

  const byId = (id) => document.getElementById(id);
  const t = (key, variables = {}) =>
    window.ProjectI18n.t(key, variables);

  const openButtons = [
    byId("open-project"),
    byId("empty-open-project"),
  ];

  const settingsOverlay = byId("settings-overlay");
  const getApi = () =>
    window.pywebview?.api || window.BrowserAnalyzerApi;
  const globalSettings = globalThis.Mega?.settings;

  function locale() {
    return state.language === "pt" ? "pt-BR" : "en-US";
  }

  function formatNumber(value) {
    return new Intl.NumberFormat(locale()).format(value ?? 0);
  }

  function formatBytes(bytes) {
    const value = Number(bytes || 0);

    if (value < 1024) {
      return `${value} B`;
    }

    const units = ["KB", "MB", "GB", "TB"];
    let size = value;
    let unit = -1;

    do {
      size /= 1024;
      unit += 1;
    } while (size >= 1024 && unit < units.length - 1);

    const digits = size >= 10 ? 1 : 2;

    return `${new Intl.NumberFormat(locale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(size)} ${units[unit]}`;
  }

  function setScreen(screen) {
    [
      "empty-state",
      "loading-state",
      "error-state",
      "dashboard",
    ].forEach((id) => byId(id).classList.add("hidden"));

    byId(screen).classList.remove("hidden");
  }

  function setButtonsDisabled(disabled) {
    openButtons.forEach((button) => {
      button.disabled = disabled;
    });
  }

  function updateLanguageSelection() {
    document.querySelectorAll(".language-option").forEach((button) => {
      const selected =
        button.dataset.language === state.language;

      button.classList.toggle("selected", selected);
      button.setAttribute(
        "aria-checked",
        selected ? "true" : "false",
      );
    });
  }

  function applyLanguage(language) {
    state.language = window.ProjectI18n.setLanguage(language);
    updateLanguageSelection();

    if (state.project) {
      renderProject(state.project);
      showView(state.currentView);
    } else {
      byId("file-search-meta").textContent = t("browseTree");
      clearFileInspector();
    }
  }

  async function loadPersistedLanguage() {
    const sharedLanguage = globalSettings?.get("language");

    if (["pt-BR", "en"].includes(sharedLanguage)) {
      applyLanguage(sharedLanguage === "en" ? "en" : "pt");
      return;
    }

    if (!getApi()?.get_settings) {
      applyLanguage("pt");
      return;
    }

    try {
      const settings = await getApi().get_settings();
      applyLanguage(settings?.language || "pt");
    } catch {
      applyLanguage("pt");
    }
  }

  async function chooseLanguage(language) {
    const previous = state.language;
    applyLanguage(language);

    try {
      if (!getApi()?.set_language) {
        throw new Error(t("bridgeUnavailable"));
      }

      const response = await getApi().set_language(language);

      if (!response?.ok) {
        throw new Error(
          response?.error || t("settingsSaveFailed"),
        );
      }

      if (globalSettings) {
        await globalSettings.set(
          "language",
          language === "en" ? "en" : "pt-BR",
        );
      }
    } catch (error) {
      applyLanguage(previous);
      byId("error-message").textContent =
        error?.message || t("settingsSaveFailed");

      closeSettings();
      setScreen("error-state");
    }
  }

  function openSettings() {
    settingsOverlay.classList.remove("hidden");
    updateLanguageSelection();
    byId("settings-close").focus();
  }

  function closeSettings() {
    settingsOverlay.classList.add("hidden");
    byId("settings-button").focus();
  }

  async function openProject() {
    setButtonsDisabled(true);
    setScreen("loading-state");

    try {
      if (!getApi()?.select_project) {
        throw new Error(t("bridgeUnavailable"));
      }

      const response = await getApi().select_project();

      if (response.cancelled) {
        setScreen(
          state.project ? "dashboard" : "empty-state",
        );
        return;
      }

      if (!response.ok) {
        throw new Error(
          response.error || t("unknownAnalysisError"),
        );
      }

      state.project = response.data;
      state.fileSearch = "";
      byId("file-search").value = "";

      renderProject(response.data);
      setScreen("dashboard");
      showView("overview");
    } catch (error) {
      byId("error-message").textContent =
        error?.message || String(error);

      setScreen("error-state");
    } finally {
      setButtonsDisabled(false);
    }
  }

  async function openWorkspaceFolder(folderId) {
    if (!folderId || !getApi()?.open_workspace_folder) {
      return;
    }

    setButtonsDisabled(true);
    setScreen("loading-state");

    try {
      const response =
        await getApi().open_workspace_folder(folderId);

      if (!response?.ok) {
        throw new Error(
          response?.error || t("unknownAnalysisError"),
        );
      }

      state.project = response.data;
      state.fileSearch = "";
      byId("file-search").value = "";

      renderProject(response.data);
      setScreen("dashboard");
      showView("overview");
    } catch (error) {
      byId("error-message").textContent =
        error?.message || String(error);

      setScreen("error-state");
    } finally {
      setButtonsDisabled(false);
    }
  }

  function languageRows(data, metric, limit = 10) {
    return Object.entries(data.languages || {})
      .map(([label, stats]) => ({
        label,
        raw: metric === "lines" ? stats.lines : stats.files,
        percent:
          metric === "lines"
            ? stats.percent_by_lines
            : stats.percent_by_files,
      }))
      .sort((a, b) => b.raw - a.raw)
      .slice(0, limit)
      .map((row) => ({
        ...row,
        value: `${row.percent.toFixed(1)}%`,
      }));
  }

  function renderProject(data) {
    const summary = data.summary;

    const markers = data.markers || {
      counts: {},
      total: 0,
      files: 0,
      items: [],
    };

    const insights = data.insights || {};

    byId("project-name").textContent = data.project.name;
    byId("project-path").textContent = data.project.path;
    byId("stat-files").textContent = formatNumber(summary.files);
    byId("stat-folders").textContent =
      formatNumber(summary.directories);
    byId("stat-lines").textContent =
      formatNumber(summary.lines);
    byId("stat-size").textContent =
      formatBytes(summary.size);

    ProjectCharts.renderBars(
      byId("overview-languages"),
      languageRows(data, "lines", 6),
    );

    ProjectCharts.renderBars(
      byId("languages-by-lines"),
      languageRows(data, "lines"),
    );

    ProjectCharts.renderBars(
      byId("languages-by-files"),
      languageRows(data, "files"),
    );

    const largest = data.largest_files?.[0];

    byId("largest-file").textContent = largest
      ? `${largest.path} · ${formatBytes(largest.size)}`
      : "—";

    const firstExtension =
      Object.entries(data.extensions || {})[0];

    byId("common-extension").textContent = firstExtension
      ? `${firstExtension[0]} · ${t("filesCount", {
          count: formatNumber(firstExtension[1]),
        })}`
      : "—";

    byId("max-depth").textContent =
      formatNumber(data.structure.maximum_depth);

    byId("average-file-size").textContent =
      formatBytes(summary.average_file_size);

    byId("overview-markers").textContent =
      t("markersAcrossFiles", {
        markers: formatNumber(markers.total),
        files: formatNumber(markers.files),
      });

    byId("structure-directories").textContent =
      formatNumber(summary.directories);

    byId("structure-depth").textContent =
      formatNumber(data.structure.maximum_depth);

    byId("structure-empty").textContent =
      formatNumber(data.structure.empty_directories);

    byId("structure-average").textContent =
      formatBytes(summary.average_file_size);

    renderRankList(
      byId("extensions-list"),
      Object.entries(data.extensions || {})
        .map(([name, count]) => ({
          name,
          value: t("filesCount", {
            count: formatNumber(count),
          }),
        }))
        .slice(0, 15),
    );

    renderRankList(
      byId("directories-list"),
      (data.structure.largest_directories || []).map(
        (item) => ({
          name: item.path,
          value: formatBytes(item.size),
        }),
      ),
    );

    renderTree(data.tree || [], state.fileSearch);
    clearFileInspector();
    renderInsights(markers, insights);
  }

  function renderInsights(markers, insights) {
    byId("marker-todo").textContent =
      formatNumber(markers.counts?.TODO || 0);

    byId("marker-fixme").textContent =
      formatNumber(markers.counts?.FIXME || 0);

    byId("marker-hack").textContent =
      formatNumber(markers.counts?.HACK || 0);

    byId("marker-summary").textContent =
      t("occurrencesInFiles", {
        occurrences: formatNumber(markers.total || 0),
        files: formatNumber(markers.files || 0),
      });

    const emptyFiles = insights.empty_files || {
      count: 0,
      paths: [],
    };

    const largeFiles = insights.large_files || {
      count: 0,
      threshold: 0,
      items: [],
    };

    const unclassified =
      insights.unclassified_files || {
        count: 0,
        paths: [],
      };

    byId("insight-empty-files").textContent =
      formatNumber(emptyFiles.count);

    byId("insight-large-files").textContent =
      formatNumber(largeFiles.count);

    byId("insight-large-threshold").textContent =
      formatBytes(largeFiles.threshold);

    byId("insight-unclassified").textContent =
      formatNumber(unclassified.count);

    byId("insight-extension-variety").textContent =
      formatNumber(insights.extension_variety || 0);

    byId("insight-warnings").textContent =
      formatNumber(insights.warnings || 0);

    renderMarkers(
      markers.items || [],
      markers.truncated,
    );

    renderRankList(
      byId("large-files-list"),
      (largeFiles.items || []).map((item) => ({
        name: item.path,
        value: formatBytes(item.size),
      })),
    );

    renderRankList(
      byId("empty-files-list"),
      (emptyFiles.paths || []).map((path) => ({
        name: path,
        value: "0 B",
      })),
    );
  }

  function renderMarkers(items, truncated) {
    const container = byId("markers-list");
    container.replaceChildren();

    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "empty-inline marker-empty";
      empty.textContent = t("noMarkers");
      container.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "marker-item";

      const header = document.createElement("div");
      header.className = "marker-item-header";

      const badge = document.createElement("span");
      badge.className =
        `marker-badge marker-${String(item.type).toLowerCase()}`;
      badge.textContent = item.type;

      const location = document.createElement("span");
      location.className = "marker-location";
      location.textContent = `${item.path}:${item.line}`;
      location.title = `${item.path}:${item.line}`;

      const snippet = document.createElement("code");
      snippet.className = "marker-snippet";
      snippet.textContent = item.snippet || "";

      header.append(badge, location);
      row.append(header, snippet);
      container.appendChild(row);
    });

    if (truncated) {
      const note = document.createElement("div");
      note.className = "marker-truncated";
      note.textContent = t("markerListCapped");
      container.appendChild(note);
    }
  }

  function renderRankList(container, items) {
    container.replaceChildren();

    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "empty-inline";
      empty.textContent = t("noDataAvailable");
      container.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "rank-item";

      const name = document.createElement("span");
      name.className = "rank-name";
      name.textContent = item.name;
      name.title = item.name;

      const value = document.createElement("span");
      value.className = "rank-value";
      value.textContent = item.value;

      row.append(name, value);
      container.appendChild(row);
    });
  }

  function filterTree(nodes, query) {
    if (!query) {
      return nodes;
    }

    const normalized = query.toLowerCase();

    return nodes.reduce((results, node) => {
      const selfMatches =
        node.name.toLowerCase().includes(normalized) ||
        node.path.toLowerCase().includes(normalized);

      if (node.type === "file") {
        if (selfMatches) {
          results.push(node);
        }

        return results;
      }

      if (selfMatches) {
        results.push(node);
        return results;
      }

      const children = filterTree(
        node.children || [],
        query,
      );

      if (children.length) {
        results.push({
          ...node,
          children,
        });
      }

      return results;
    }, []);
  }

  function countVisibleFiles(nodes) {
    return nodes.reduce((total, node) => {
      if (node.type === "file") {
        return total + 1;
      }

      return total + countVisibleFiles(
        node.children || [],
      );
    }, 0);
  }

  function renderTree(nodes, query = "") {
    const container = byId("file-tree");
    container.replaceChildren();

    const trimmed = query.trim();
    const filtered = filterTree(nodes, trimmed);

    if (!filtered.length) {
      const empty = document.createElement("div");
      empty.className = "tree-empty";
      empty.textContent = t("noMatches", { query });
      container.appendChild(empty);

      byId("file-search-meta").textContent =
        t("zeroMatchingFiles");

      return;
    }

    const fragment = document.createDocumentFragment();

    filtered.forEach((node) => {
      fragment.appendChild(
        createTreeNode(node, Boolean(trimmed)),
      );
    });

    container.appendChild(fragment);

    if (trimmed) {
      byId("file-search-meta").textContent =
        t("matchingFiles", {
          count: formatNumber(
            countVisibleFiles(filtered),
          ),
        });
    } else {
      byId("file-search-meta").textContent =
        t("browseTree");
    }
  }

  function createTreeNode(
    node,
    expandDirectories = false,
  ) {
    const wrapper = document.createElement("div");
    wrapper.className = "tree-node";

    const row = document.createElement("button");
    row.className = "tree-row";
    row.type = "button";

    const icon = document.createElement("span");
    icon.className = "tree-icon";
    icon.textContent =
      node.type === "directory"
        ? (expandDirectories ? "▾" : "▸")
        : "·";

    const name = document.createElement("span");
    name.textContent = node.name;

    row.append(icon, name);
    wrapper.appendChild(row);

    if (node.type === "directory") {
      const children = document.createElement("div");

      children.className =
        `tree-children${expandDirectories ? "" : " hidden"}`;

      (node.children || []).forEach((child) => {
        children.appendChild(
          createTreeNode(child, expandDirectories),
        );
      });

      row.addEventListener("click", () => {
        const collapsed =
          children.classList.toggle("hidden");

        icon.textContent =
          collapsed ? "▸" : "▾";
      });

      wrapper.appendChild(children);
    } else {
      row.addEventListener("click", () => {
        document
          .querySelectorAll(".tree-row.selected")
          .forEach((element) => {
            element.classList.remove("selected");
          });

        row.classList.add("selected");
        inspectFile(node);
      });
    }

    return wrapper;
  }

  function inspectFile(file) {
    byId("file-name").textContent = file.name;
    byId("file-language").textContent =
      file.language || t("unknown");

    byId("file-size").textContent =
      formatBytes(file.size);

    byId("file-lines").textContent =
      file.lines == null
        ? t("binaryUnavailable")
        : formatNumber(file.lines);

    byId("file-path").textContent = file.path;
  }

  function clearFileInspector() {
    byId("file-name").textContent = t("selectFile");

    [
      "file-language",
      "file-size",
      "file-lines",
      "file-path",
    ].forEach((id) => {
      byId(id).textContent = "—";
    });
  }

  function showView(viewName) {
    state.currentView = viewName;

    document
      .querySelectorAll("[data-view-panel]")
      .forEach((panel) => {
        panel.classList.toggle(
          "hidden",
          panel.dataset.viewPanel !== viewName,
        );
      });

    document
      .querySelectorAll(".nav-item")
      .forEach((button) => {
        button.classList.toggle(
          "active",
          button.dataset.view === viewName,
        );
      });

    if (viewName === "files") {
      byId("file-search").focus();
    }
  }

  openButtons.forEach((button) => {
    button.addEventListener("click", openProject);
  });

  document
    .querySelectorAll(".nav-item")
    .forEach((button) => {
      button.addEventListener("click", () => {
        if (state.project) {
          showView(button.dataset.view);
        }
      });
    });

  byId("file-search").addEventListener(
    "input",
    (event) => {
      state.fileSearch = event.target.value;

      if (state.project) {
        renderTree(
          state.project.tree || [],
          state.fileSearch,
        );
      }
    },
  );

  byId("file-search").addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Escape" &&
        event.target.value
      ) {
        event.target.value = "";
        state.fileSearch = "";

        renderTree(
          state.project?.tree || [],
          "",
        );
      }
    },
  );

  byId("settings-button").addEventListener(
    "click",
    openSettings,
  );

  byId("settings-close").addEventListener(
    "click",
    closeSettings,
  );

  settingsOverlay.addEventListener(
    "click",
    (event) => {
      if (event.target === settingsOverlay) {
        closeSettings();
      }
    },
  );

  document.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Escape" &&
        !settingsOverlay.classList.contains("hidden")
      ) {
        closeSettings();
      }
    },
  );

  document
    .querySelectorAll(".language-option")
    .forEach((button) => {
      button.addEventListener("click", () =>
        chooseLanguage(button.dataset.language),
      );
    });

  window.ProjectI18n.setLanguage("pt");
  updateLanguageSelection();

  globalSettings?.subscribe(
    (settings) => {
      const next =
        settings.language === "en" ? "en" : "pt";

      if (next !== state.language) {
        applyLanguage(next);
      }
    },
    { immediate: false },
  );

  // pywebview dispatches `pywebviewready` on window, not on document.
  // If the bridge is already available (for example after a fast reload),
  // load the persisted settings immediately; otherwise wait for the event.
  if (getApi()?.get_settings) {
    loadPersistedLanguage();
  } else {
    window.addEventListener(
      "pywebviewready",
      loadPersistedLanguage,
      { once: true },
    );
  }

  openWorkspaceFolder(
    new URLSearchParams(location.search).get(
      "workspaceFolder",
    ),
  );
})();
