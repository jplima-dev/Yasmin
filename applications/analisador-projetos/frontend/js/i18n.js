window.ProjectI18n = (() => {
  const translations = {
    en: {
      appName: "Project Analyzer",
      brandSubtitle: "Local code insights",
      settings: "Settings",
      openProject: "Open Project",
      overview: "Overview",
      files: "Files",
      languages: "Languages",
      structure: "Structure",
      insights: "Insights",
      readOnlyNote: "Read-only analysis. No project files are modified.",
      inspectProject: "Inspect a project",
      inspectDescription: "Select a local folder to generate a structural and language overview.",
      chooseFolder: "Choose Folder",
      analyzingProject: "Analyzing project…",
      scanningDescription: "Scanning files, code markers and project statistics.",
      analysisFailed: "Analysis failed",
      currentProject: "Current project",
      folders: "Folders",
      lines: "Lines",
      size: "Size",
      byLines: "By lines",
      highlights: "Highlights",
      largestFile: "Largest file",
      mostCommonExtension: "Most common extension",
      maximumDepth: "Maximum depth",
      averageFileSize: "Average file size",
      codeMarkers: "Code markers",
      projectContents: "Project contents",
      searchPlaceholder: "Search files or folders…",
      browseTree: "Browse the project tree or search by name/path.",
      selectedFile: "Selected file",
      selectFile: "Select a file",
      language: "Language",
      path: "Path",
      sourceComposition: "Source composition",
      byFiles: "By files",
      organization: "Organization",
      directories: "Directories",
      emptyDirectories: "Empty directories",
      averageFile: "Average file",
      filesByExtension: "Files by extension",
      largestDirectories: "Largest directories",
      projectSignals: "Project signals",
      emptyFiles: "Empty files",
      largeFiles: "Large files",
      largeFileThreshold: "Large-file threshold",
      withoutClassification: "Without language classification",
      extensionVariety: "Extension variety",
      scannerWarnings: "Scanner warnings",
      preferences: "Preferences",
      close: "Close",
      languageDescription: "Choose the language used by the application.",
      languageSavedNote: "Your language preference is saved automatically for the next time you open the app.",
      bridgeUnavailable: "The Python bridge is unavailable. Start the app with 'python main.py'.",
      unknownAnalysisError: "Unknown analysis error.",
      filesCount: "{count} files",
      markersAcrossFiles: "{markers} across {files} files",
      occurrencesInFiles: "{occurrences} occurrences in {files} files",
      noMarkers: "No TODO, FIXME or HACK markers found.",
      markerListCapped: "The list is capped for display; totals above still include every detected marker.",
      noDataAvailable: "No data available",
      noMatches: "No files or folders match “{query}”.",
      matchingFiles: "{count} matching files · matching folders are expanded automatically",
      zeroMatchingFiles: "0 matching files",
      unknown: "Unknown",
      binaryUnavailable: "Binary / unavailable",
      settingsSaveFailed: "Could not save the language preference."
    },
    pt: {
      appName: "Analisador de Projetos",
      brandSubtitle: "Informações locais sobre o código",
      settings: "Configurações",
      openProject: "Abrir Projeto",
      overview: "Visão geral",
      files: "Arquivos",
      languages: "Linguagens",
      structure: "Estrutura",
      insights: "Insights",
      readOnlyNote: "Análise somente leitura. Nenhum arquivo do projeto é modificado.",
      inspectProject: "Analise um projeto",
      inspectDescription: "Selecione uma pasta local para gerar uma visão geral da estrutura e das linguagens.",
      chooseFolder: "Escolher Pasta",
      analyzingProject: "Analisando projeto…",
      scanningDescription: "Verificando arquivos, marcadores de código e estatísticas do projeto.",
      analysisFailed: "Falha na análise",
      currentProject: "Projeto atual",
      folders: "Pastas",
      lines: "Linhas",
      size: "Tamanho",
      byLines: "Por linhas",
      highlights: "Destaques",
      largestFile: "Maior arquivo",
      mostCommonExtension: "Extensão mais comum",
      maximumDepth: "Profundidade máxima",
      averageFileSize: "Tamanho médio dos arquivos",
      codeMarkers: "Marcadores de código",
      projectContents: "Conteúdo do projeto",
      searchPlaceholder: "Pesquisar arquivos ou pastas…",
      browseTree: "Navegue pela árvore do projeto ou pesquise por nome/caminho.",
      selectedFile: "Arquivo selecionado",
      selectFile: "Selecione um arquivo",
      language: "Idioma",
      path: "Caminho",
      sourceComposition: "Composição do código",
      byFiles: "Por arquivos",
      organization: "Organização",
      directories: "Diretórios",
      emptyDirectories: "Diretórios vazios",
      averageFile: "Arquivo médio",
      filesByExtension: "Arquivos por extensão",
      largestDirectories: "Maiores diretórios",
      projectSignals: "Sinais do projeto",
      emptyFiles: "Arquivos vazios",
      largeFiles: "Arquivos grandes",
      largeFileThreshold: "Limite para arquivo grande",
      withoutClassification: "Sem classificação de linguagem",
      extensionVariety: "Variedade de extensões",
      scannerWarnings: "Avisos do scanner",
      preferences: "Preferências",
      close: "Fechar",
      languageDescription: "Escolha o idioma usado pelo aplicativo.",
      languageSavedNote: "Sua preferência de idioma é salva automaticamente para a próxima vez que abrir o aplicativo.",
      bridgeUnavailable: "A comunicação com o Python não está disponível. Inicie o app com 'python main.py'.",
      unknownAnalysisError: "Erro desconhecido durante a análise.",
      filesCount: "{count} arquivos",
      markersAcrossFiles: "{markers} em {files} arquivos",
      occurrencesInFiles: "{occurrences} ocorrências em {files} arquivos",
      noMarkers: "Nenhum marcador TODO, FIXME ou HACK foi encontrado.",
      markerListCapped: "A lista é limitada para exibição; os totais acima ainda incluem todos os marcadores detectados.",
      noDataAvailable: "Nenhum dado disponível",
      noMatches: "Nenhum arquivo ou pasta corresponde a “{query}”.",
      matchingFiles: "{count} arquivos correspondentes · pastas correspondentes são expandidas automaticamente",
      zeroMatchingFiles: "0 arquivos correspondentes",
      unknown: "Desconhecido",
      binaryUnavailable: "Binário / indisponível",
      settingsSaveFailed: "Não foi possível salvar a preferência de idioma."
    }
  };

  let currentLanguage = "pt";

  function normalize(language) {
    return language === "pt" ? "pt" : "en";
  }

  function t(key, variables = {}) {
    const language = translations[currentLanguage] || translations.en;
    let value = language[key] ?? translations.en[key] ?? key;
    Object.entries(variables).forEach(([name, replacement]) => {
      value = value.replaceAll(`{${name}}`, String(replacement));
    });
    return value;
  }

  function applyStaticTranslations(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    root.querySelectorAll("[data-i18n-title]").forEach((element) => {
      element.title = t(element.dataset.i18nTitle);
    });
    root.querySelectorAll("[data-i18n-aria]").forEach((element) => {
      element.setAttribute("aria-label", t(element.dataset.i18nAria));
    });
  }

  function setLanguage(language) {
    currentLanguage = normalize(language);
    document.documentElement.lang = currentLanguage === "pt" ? "pt-BR" : "en";
    applyStaticTranslations();
    return currentLanguage;
  }

  function getLanguage() {
    return currentLanguage;
  }

  return { t, setLanguage, getLanguage, applyStaticTranslations };
})();
