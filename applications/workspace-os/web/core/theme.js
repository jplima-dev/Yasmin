const HEX = /^#[0-9a-f]{6}$/i;
const systemThemeStates = new WeakMap();

export function normalizeHex(value, fallback = "#ff5b3d") {
  const color = String(value || "").trim();
  return HEX.test(color) ? color.toLowerCase() : fallback;
}

function channels(color) {
  const value = normalizeHex(color).slice(1);
  return [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
}

function toHex(values) {
  return `#${values.map((value) => Math.round(value).toString(16).padStart(2, "0")).join("")}`;
}

export function mix(color, target, amount) {
  const from = channels(color);
  const to = channels(target);
  return toHex(from.map((value, index) => value + (to[index] - value) * amount));
}

export function derivePalette(accent, theme = "light") {
  const base = normalizeHex(accent);
  const dark = theme === "dark";
  const [red, green, blue] = channels(base);
  return {
    accent: base,
    secondary: toHex([green, blue, red]),
    tertiary: toHex([blue, red, green]),
    hover: mix(base, dark ? "#ffffff" : "#000000", dark ? 0.16 : 0.12),
    soft: mix(base, dark ? "#15171b" : "#faf7ef", dark ? 0.74 : 0.88),
    border: mix(base, dark ? "#4b4d52" : "#c8c1b4", 0.58),
  };
}

export function resolvedTheme(theme, media = globalThis.matchMedia?.("(prefers-color-scheme: dark)")) {
  return theme === "system" ? (media?.matches ? "dark" : "light") : theme;
}

function watchSystemTheme(root, settings) {
  const view = root?.ownerDocument?.defaultView;
  const media = view?.matchMedia?.("(prefers-color-scheme: dark)");
  if (!media) return;
  let state = systemThemeStates.get(root);
  if (!state) {
    state = { settings };
    state.listener = () => {
      if (state.settings?.theme === "system") applyGlobalTheme(state.settings, root);
    };
    media.addEventListener?.("change", state.listener);
    systemThemeStates.set(root, state);
  }
  state.settings = { ...settings };
}

export function applyGlobalTheme(settings, root = document.documentElement) {
  watchSystemTheme(root, settings);
  const theme = resolvedTheme(settings.theme);
  const palette = derivePalette(settings.accent, theme);
  const surfaces = theme === "dark" ? {
    background: "#101114", surface: "#15171b", surface2: "#1b1e23",
    text: "#f3efe7", muted: "#9f9c94", border: "rgba(255,255,255,.11)", borderStrong: "rgba(255,255,255,.23)",
  } : {
    background: "#ede8dc", surface: "#faf7ef", surface2: "#e4ded0",
    text: "#121315", muted: "#747269", border: "rgba(18,19,21,.16)", borderStrong: "rgba(18,19,21,.30)",
  };
  root.dataset.theme = theme;
  root.dataset.workspaceTheme = theme;
  root.dataset.themePreference = settings.theme;
  root.dataset.density = settings.density;
  root.dataset.fontSize = settings.font_size;
  root.dataset.reduceMotion = String(Boolean(settings.reduce_motion));
  root.dataset.highContrast = String(Boolean(settings.high_contrast));
  root.dataset.decorations = String(settings.decorations !== false);
  root.ownerDocument?.body?.classList.toggle("dark", theme === "dark");
  root.lang = settings.language === "en" ? "en" : "pt-BR";
  const aliases = {
    "--accent": palette.accent, "--accent-hover": palette.hover, "--accent-2": palette.hover,
    "--accent-secondary": palette.secondary, "--accent-tertiary": palette.tertiary,
    "--accent-dark": palette.hover, "--accent-soft": palette.soft, "--accent-border": palette.border,
    "--primary": palette.accent, "--primary-dark": palette.hover, "--teal": palette.accent,
    "--teal-dark": palette.hover, "--mint": palette.soft,
    "--purple": palette.accent, "--purple-dark": palette.hover, "--purple-light": palette.soft,
    "--bg": surfaces.background, "--background": surfaces.background, "--paper": surfaces.background,
    "--panel": surfaces.surface, "--surface": surfaces.surface, "--surface-solid": surfaces.surface,
    "--white": surfaces.surface, "--page": surfaces.surface,
    "--panel-2": surfaces.surface2, "--surface-2": surfaces.surface2, "--surface-soft": surfaces.surface2, "--toolbar": surfaces.surface2,
    "--soft": palette.soft, "--header": surfaces.surface2, "--selected": palette.soft,
    "--selected-border": palette.accent, "--grid": surfaces.border,
    "--text": surfaces.text, "--ink": surfaces.text,
    "--muted": surfaces.muted, "--text-secondary": surfaces.muted,
    "--border": surfaces.border, "--line": surfaces.border, "--border-strong": surfaces.borderStrong,
    "--green": theme === "dark" ? "#caff52" : "#477115",
    "--amber": theme === "dark" ? "#f0bb62" : "#9a5b00",
    "--red": theme === "dark" ? "#ff8b7a" : "#b93629",
    "--ws-color-rail": theme === "dark" ? "#090a0c" : "#121315",
    "--ws-color-rail-text": "#f7f3ea",
    "--ws-color-rail-muted": theme === "dark" ? "#8f908d" : "#9b9a93",
    "--ws-grid-line": theme === "dark" ? "rgba(255,255,255,.045)" : "rgba(18,19,21,.055)",
    "--ws-color-background": surfaces.background, "--ws-color-surface": surfaces.surface,
    "--ws-color-surface-subtle": surfaces.surface2, "--ws-color-border": surfaces.border,
    "--ws-color-border-strong": surfaces.borderStrong, "--ws-color-text": surfaces.text,
    "--ws-color-text-muted": surfaces.muted, "--ws-color-primary": palette.accent,
    "--ws-color-primary-hover": palette.hover, "--ws-color-primary-soft": palette.soft,
    "--ws-color-surface-hover": theme === "dark" ? "#24272d" : "#e8e1d3",
    "--ws-radius-small": "5px", "--ws-radius-medium": "8px", "--ws-radius-large": "12px",
    "--ws-shadow-1": theme === "dark" ? "0 1px 0 rgba(255,255,255,.035), 0 8px 24px rgba(0,0,0,.20)" : "0 1px 0 rgba(18,19,21,.08), 0 7px 22px rgba(18,19,21,.045)",
    "--ws-shadow-2": theme === "dark" ? "0 18px 44px rgba(0,0,0,.34)" : "0 14px 36px rgba(18,19,21,.11)",
    "--accent-gradient": `linear-gradient(135deg, ${palette.accent}, ${palette.hover})`,
    "--accent-soft-gradient": `linear-gradient(135deg, ${palette.soft}, color-mix(in srgb, ${palette.accent} 12%, ${surfaces.surface}))`,
    "--surface-gradient": `linear-gradient(145deg, ${surfaces.surface}, color-mix(in srgb, ${palette.accent} ${theme === "dark" ? 8 : 5}%, ${surfaces.surface2}))`,
    "--hero-gradient": `linear-gradient(135deg, color-mix(in srgb, ${palette.accent} ${theme === "dark" ? 14 : 9}%, ${surfaces.surface}), ${surfaces.surface} 46%, color-mix(in srgb, ${palette.accent} ${theme === "dark" ? 8 : 5}%, ${surfaces.surface2}))`,
    "--section-accent": mix(palette.accent, surfaces.surface, theme === "dark" ? 0.78 : 0.88),
    "--section-secondary": mix(palette.secondary, surfaces.surface, theme === "dark" ? 0.82 : 0.91),
    "--section-tertiary": mix(palette.tertiary, surfaces.surface, theme === "dark" ? 0.84 : 0.93),
    "--section-accent-gradient": `linear-gradient(145deg, color-mix(in srgb, ${palette.accent} ${theme === "dark" ? 18 : 9}%, ${surfaces.surface}), color-mix(in srgb, ${palette.accent} ${theme === "dark" ? 8 : 4}%, ${surfaces.surface2}))`,
    "--section-secondary-gradient": `linear-gradient(145deg, color-mix(in srgb, ${palette.secondary} ${theme === "dark" ? 14 : 7}%, ${surfaces.surface}), color-mix(in srgb, ${palette.secondary} ${theme === "dark" ? 6 : 3}%, ${surfaces.surface2}))`,
    "--section-tertiary-gradient": `linear-gradient(145deg, color-mix(in srgb, ${palette.tertiary} ${theme === "dark" ? 12 : 6}%, ${surfaces.surface}), color-mix(in srgb, ${palette.tertiary} ${theme === "dark" ? 5 : 2}%, ${surfaces.surface2}))`,
  };
  for (const [name, value] of Object.entries(aliases)) root.style.setProperty(name, value);
  return palette;
}
