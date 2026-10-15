const IGNORED_DIRECTORIES = new Set([
  ".git",
  ".hg",
  ".svn",
  ".idea",
  ".vscode",
  ".venv",
  "venv",
  "env",
  "__pycache__",
  "node_modules",
  "dist",
  "build",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  ".tox",
  ".next",
  ".nuxt",
  "coverage",
]);

const IGNORED_FILES = new Set([
  ".DS_Store",
  "Thumbs.db",
]);

const LANGUAGE_BY_EXTENSION = {
  ".py": "Python",
  ".pyw": "Python",
  ".js": "JavaScript",
  ".mjs": "JavaScript",
  ".cjs": "JavaScript",
  ".jsx": "JavaScript",
  ".ts": "TypeScript",
  ".tsx": "TypeScript",
  ".html": "HTML",
  ".htm": "HTML",
  ".css": "CSS",
  ".scss": "SCSS",
  ".sass": "Sass",
  ".less": "Less",
  ".json": "JSON",
  ".jsonc": "JSON",
  ".md": "Markdown",
  ".mdx": "MDX",
  ".xml": "XML",
  ".yaml": "YAML",
  ".yml": "YAML",
  ".toml": "TOML",
  ".ini": "INI",
  ".cfg": "Config",
  ".conf": "Config",
  ".sh": "Shell",
  ".bash": "Shell",
  ".zsh": "Shell",
  ".ps1": "PowerShell",
  ".bat": "Batch",
  ".cmd": "Batch",
  ".sql": "SQL",
  ".java": "Java",
  ".kt": "Kotlin",
  ".kts": "Kotlin",
  ".c": "C",
  ".h": "C/C++ Header",
  ".cc": "C++",
  ".cpp": "C++",
  ".cxx": "C++",
  ".hpp": "C++ Header",
  ".cs": "C#",
  ".go": "Go",
  ".rs": "Rust",
  ".rb": "Ruby",
  ".php": "PHP",
  ".swift": "Swift",
  ".dart": "Dart",
  ".lua": "Lua",
  ".r": "R",
  ".vue": "Vue",
  ".svelte": "Svelte",
  ".astro": "Astro",
  ".graphql": "GraphQL",
  ".gql": "GraphQL",
};

const LANGUAGE_BY_FILENAME = {
  dockerfile: "Dockerfile",
  makefile: "Makefile",
  "cmakelists.txt": "CMake",
  gemfile: "Ruby",
  rakefile: "Ruby",
};

const TEXT_EXTENSIONS = new Set([
  ...Object.keys(LANGUAGE_BY_EXTENSION),
  ".txt",
  ".csv",
  ".tsv",
  ".log",
  ".env",
  ".gitignore",
  ".gitattributes",
  ".editorconfig",
  ".properties",
  ".lock",
]);

const LARGE_FILE_THRESHOLD = 512 * 1024;

function extensionOf(name) {
  const index = name.lastIndexOf(".");

  return index > 0 ? name.slice(index).toLowerCase() : "";
}

export function languageFor(name) {
  const lower = name.toLowerCase();

  return LANGUAGE_BY_FILENAME[lower] ||
    LANGUAGE_BY_EXTENSION[extensionOf(lower)] ||
    null;
}

function likelyText(bytes, name) {
  if (
    TEXT_EXTENSIONS.has(extensionOf(name)) ||
    LANGUAGE_BY_FILENAME[name.toLowerCase()]
  ) {
    return true;
  }

  if (!bytes.length) {
    return true;
  }

  let suspicious = 0;

  for (const byte of bytes) {
    if (byte === 0) {
      return false;
    }

    if (byte < 9 || (byte > 13 && byte < 32)) {
      suspicious += 1;
    }
  }

  return suspicious / bytes.length <= .08;
}

function lineCount(text) {
  if (!text) {
    return 0;
  }

  const normalized = text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n");

  return (
    (normalized.match(/\n/g)?.length || 0) +
    (normalized.endsWith("\n") ? 0 : 1)
  );
}

function markersIn(text, language, path) {
  if (
    !language ||
    ["Markdown", "MDX", "JSON", "GraphQL"].includes(language)
  ) {
    return [];
  }

  const items = [];
  const lines = text.split(/\r\n|\r|\n/);

  const commentRules = {
    Python: /#/,
    Shell: /#/,
    PowerShell: /#/,
    Ruby: /#/,
    R: /#/,
    YAML: /#/,
    TOML: /#/,
    Config: /[#;]/,
    JavaScript: /\/\/|\/\*|^\s*\*/,
    TypeScript: /\/\/|\/\*|^\s*\*/,
    Java: /\/\/|\/\*|^\s*\*/,
    Kotlin: /\/\/|\/\*|^\s*\*/,
    C: /\/\/|\/\*|^\s*\*/,
    "C/C++ Header": /\/\/|\/\*|^\s*\*/,
    "C++": /\/\/|\/\*|^\s*\*/,
    "C++ Header": /\/\/|\/\*|^\s*\*/,
    "C#": /\/\/|\/\*|^\s*\*/,
    Go: /\/\/|\/\*|^\s*\*/,
    Rust: /\/\/|\/\*|^\s*\*/,
    CSS: /\/\*|^\s*\*/,
    SCSS: /\/\/|\/\*|^\s*\*/,
    HTML: /<!--/,
    XML: /<!--/,
    SQL: /--|\/\*|^\s*\*/,
    Lua: /--|^\s*\*/,
    Batch: /^\s*(REM\s|::)/i,
  };

  const comment = commentRules[language];

  if (!comment) {
    return items;
  }

  lines.forEach((line, index) => {
    const matches = [
      ...line.matchAll(/\b(TODO|FIXME|HACK)\b/gi),
    ];

    if (!matches.length) {
      return;
    }

    for (const match of matches) {
      if (!comment.test(line.slice(0, match.index))) {
        continue;
      }

      items.push({
        path,
        type: match[1].toUpperCase(),
        line: index + 1,
        snippet: line.trim().slice(0, 180),
      });
    }
  });

  return items;
}

async function readRecord(file, path) {
  const language = languageFor(file.name);
  const bytes = new Uint8Array(
    await file.slice(0, 8192).arrayBuffer()
  );

  let text = null;

  if (
    likelyText(bytes, file.name) &&
    file.size <= 8 * 1024 * 1024
  ) {
    try {
      text = await file.text();
    } catch {
      text = null;
    }
  }

  return {
    name: file.name,
    path,
    size: file.size,
    extension: extensionOf(file.name),
    language,
    lines: text == null ? null : lineCount(text),
    markers: text == null ? [] : markersIn(text, language, path),
  };
}

async function walkDirectory(
  handle,
  prefix,
  records,
  directories,
  warnings
) {
  try {
    for await (const [name, entry] of handle.entries()) {
      const path = prefix ? `${prefix}/${name}` : name;

      if (entry.kind === "directory") {
        if (IGNORED_DIRECTORIES.has(name)) {
          continue;
        }

        directories.push(path);

        await walkDirectory(
          entry,
          path,
          records,
          directories,
          warnings
        );
      } else if (!IGNORED_FILES.has(name)) {
        try {
          records.push(
            await readRecord(await entry.getFile(), path)
          );
        } catch (error) {
          warnings.push(`${path}: ${error.message || error}`);
        }
      }
    }
  } catch (error) {
    warnings.push(
      `${prefix || handle.name}: ${error.message || error}`
    );
  }
}

function buildTree(records, directories) {
  const root = new Map();

  const ensureDirectory = (parts) => {
    let children = root;
    let currentPath = "";

    for (const part of parts) {
      currentPath = currentPath
        ? `${currentPath}/${part}`
        : part;

      if (!children.has(part)) {
        children.set(part, {
          name: part,
          type: "directory",
          path: currentPath,
          children: new Map(),
        });
      }

      children = children.get(part).children;
    }

    return children;
  };

  directories.forEach((path) => {
    ensureDirectory(path.split("/"));
  });

  records.forEach((file) => {
    const parts = file.path.split("/");
    const children = ensureDirectory(parts.slice(0, -1));

    children.set(file.name, {
      ...file,
      type: "file",
    });
  });

  const finalize = (map) =>
    [...map.values()]
      .sort((a, b) =>
        a.type === b.type
          ? a.name.localeCompare(b.name)
          : a.type === "directory"
            ? -1
            : 1
      )
      .map((node) =>
        node.type === "directory"
          ? {
              ...node,
              children: finalize(node.children),
            }
          : node
      );

  return finalize(root);
}

export function analyzeRecords(
  records,
  directories,
  projectName,
  warnings = []
) {
  const totalSize = records.reduce(
    (sum, file) => sum + file.size,
    0
  );

  const totalLines = records.reduce(
    (sum, file) => sum + (file.lines ?? 0),
    0
  );

  const extensions = {};
  const languages = {};
  const directorySizes = {};
  const directFiles = {};
  const markerItems = [];
  const markerCounts = {
    TODO: 0,
    FIXME: 0,
    HACK: 0,
  };

  const markerFiles = new Set();

  for (const file of records) {
    const extension = file.extension || "[no extension]";

    extensions[extension] =
      (extensions[extension] || 0) + 1;

    if (file.language) {
      languages[file.language] ||= {
        files: 0,
        lines: 0,
      };

      languages[file.language].files += 1;
      languages[file.language].lines += file.lines ?? 0;
    }

    const parts = file.path.split("/").slice(0, -1);

    if (parts.length) {
      directFiles[parts.join("/")] =
        (directFiles[parts.join("/")] || 0) + 1;
    }

    parts.forEach((_, index) => {
      const path = parts
        .slice(0, index + 1)
        .join("/");

      directorySizes[path] =
        (directorySizes[path] || 0) + file.size;
    });

    if (file.markers.length) {
      markerFiles.add(file.path);
    }

    file.markers.forEach((marker) => {
      markerCounts[marker.type] += 1;

      if (markerItems.length < 500) {
        markerItems.push(marker);
      }
    });
  }

  const knownLines = Object.values(languages).reduce(
    (sum, item) => sum + item.lines,
    0
  );

  const knownFiles = Object.values(languages).reduce(
    (sum, item) => sum + item.files,
    0
  );

  Object.values(languages).forEach((item) => {
    item.percent_by_lines = knownLines
      ? Math.round((item.lines / knownLines) * 10000) / 100
      : 0;

    item.percent_by_files = knownFiles
      ? Math.round((item.files / knownFiles) * 10000) / 100
      : 0;
  });

  const sortedExtensions = Object.fromEntries(
    Object.entries(extensions).sort(
      (a, b) => b[1] - a[1] || a[0].localeCompare(b[0])
    )
  );

  const largestFiles = [...records]
    .sort((a, b) => b.size - a.size)
    .slice(0, 10);

  const largeFiles = [...records]
    .filter((file) => file.size >= LARGE_FILE_THRESHOLD)
    .sort((a, b) => b.size - a.size);

  const parentsWithChildren = new Set(
    directories
      .map((path) =>
        path.includes("/")
          ? path.slice(0, path.lastIndexOf("/"))
          : ""
      )
      .filter(Boolean)
  );

  const emptyDirectories = directories.filter(
    (path) =>
      !directFiles[path] &&
      !parentsWithChildren.has(path)
  );

  const largestDirectories = Object.entries(directorySizes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([path, size]) => ({
      path,
      size,
    }));

  const totalMarkers = Object.values(markerCounts).reduce(
    (sum, value) => sum + value,
    0
  );

  return {
    project: {
      name: projectName,
      path: `Pasta local / ${projectName}`,
    },

    summary: {
      files: records.length,
      directories: directories.length,
      lines: totalLines,
      size: totalSize,
      average_file_size: records.length
        ? totalSize / records.length
        : 0,
    },

    languages,
    extensions: sortedExtensions,
    largest_files: largestFiles,

    structure: {
      maximum_depth: Math.max(
        0,
        ...directories.map(
          (path) => path.split("/").length
        )
      ),
      empty_directories: emptyDirectories.length,
      empty_directory_paths: emptyDirectories,
      largest_directory: largestDirectories[0] || null,
      largest_directories: largestDirectories,
    },

    markers: {
      counts: markerCounts,
      total: totalMarkers,
      files: markerFiles.size,
      items: markerItems,
      truncated: totalMarkers > markerItems.length,
    },

    insights: {
      empty_files: {
        count: records.filter(
          (file) => file.size === 0
        ).length,
        paths: records
          .filter((file) => file.size === 0)
          .slice(0, 30)
          .map((file) => file.path),
      },

      large_files: {
        count: largeFiles.length,
        threshold: LARGE_FILE_THRESHOLD,
        items: largeFiles.slice(0, 10),
      },

      unclassified_files: {
        count: records.filter(
          (file) => !file.language
        ).length,
        paths: records
          .filter((file) => !file.language)
          .slice(0, 30)
          .map((file) => file.path),
      },

      extension_variety: Object.keys(extensions).length,
      warnings: warnings.length,
    },

    tree: buildTree(records, directories),
    warnings,

    ignored: {
      directories: [...IGNORED_DIRECTORIES].sort(),
      files: [...IGNORED_FILES].sort(),
    },
  };
}

export async function analyzeDirectory(handle) {
  const records = [];
  const directories = [];
  const warnings = [];

  await walkDirectory(
    handle,
    "",
    records,
    directories,
    warnings
  );

  records.sort((a, b) => a.path.localeCompare(b.path));
  directories.sort((a, b) => a.localeCompare(b));

  return analyzeRecords(
    records,
    directories,
    handle.name,
    warnings
  );
}

export async function analyzeFileList(fileList) {
  const records = [];
  const warnings = [];
  const directorySet = new Set();

  let projectName = "Projeto";

  for (const file of fileList) {
    const rawPath =
      file.webkitRelativePath || file.name;

    const parts = rawPath
      .split("/")
      .filter(Boolean);

    if (parts.length > 1) {
      projectName = parts[0];
    }

    const relativeParts =
      parts.length > 1
        ? parts.slice(1)
        : parts;

    if (
      relativeParts.some(
        (part, index) =>
          index < relativeParts.length - 1 &&
          IGNORED_DIRECTORIES.has(part)
      )
    ) {
      continue;
    }

    if (IGNORED_FILES.has(file.name)) {
      continue;
    }

    const path = relativeParts.join("/");

    relativeParts
      .slice(0, -1)
      .forEach((_, index) => {
        directorySet.add(
          relativeParts
            .slice(0, index + 1)
            .join("/")
        );
      });

    try {
      records.push(
        await readRecord(file, path)
      );
    } catch (error) {
      warnings.push(
        `${path}: ${error.message || error}`
      );
    }
  }

  records.sort((a, b) => a.path.localeCompare(b.path));

  const directories = [...directorySet].sort(
    (a, b) => a.localeCompare(b)
  );

  return analyzeRecords(
    records,
    directories,
    projectName,
    warnings
  );
}
