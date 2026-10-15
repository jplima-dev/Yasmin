(() => {
  const root = document.documentElement;
  const coreOrigin = (() => { try { return new URL(document.currentScript?.src || location.href).origin; } catch { return location.origin; } })();
  let settings = null;
  try { settings = JSON.parse(localStorage.getItem("workspace.settings.cache.v2") || "null"); } catch { settings = null; }
  if (!settings) {
    try {
      const request = new XMLHttpRequest();
      request.open("GET", `${coreOrigin}/api/settings`, false);
      request.send();
      if (request.status === 200) settings = JSON.parse(request.responseText);
    } catch { settings = null; }
  }
  settings ||= { theme: "light", accent: "#ff5b3d", density: "comfortable", font_size: "comfortable" };
  const theme = settings.theme === "system" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : settings.theme;
  const dark = theme === "dark";
  const colors = dark
    ? { background: "#101114", surface: "#15171b", surface2: "#1b1e23", surfaceHover: "#24272d", text: "#f3efe7", muted: "#9f9c94", border: "rgba(255,255,255,.11)", borderStrong: "rgba(255,255,255,.23)" }
    : { background: "#ede8dc", surface: "#faf7ef", surface2: "#e4ded0", surfaceHover: "#e8e1d3", text: "#121315", muted: "#747269", border: "rgba(18,19,21,.16)", borderStrong: "rgba(18,19,21,.30)" };
  const validHex = /^#[0-9a-f]{6}$/i;
  const accent = validHex.test(settings.accent || "") ? settings.accent.toLowerCase() : "#ff5b3d";
  const mix = (from, to, amount) => {
    const channel = (value, offset) => Number.parseInt(value.slice(1 + offset, 3 + offset), 16);
    return `#${[0, 2, 4].map((offset) => Math.round(channel(from, offset) + (channel(to, offset) - channel(from, offset)) * amount).toString(16).padStart(2, "0")).join("")}`;
  };
  const accentHover = mix(accent, dark ? "#ffffff" : "#000000", dark ? .16 : .12);
  const accentSoft = mix(accent, dark ? "#15171b" : "#faf7ef", dark ? .74 : .88);
  const accentBorder = mix(accent, dark ? "#4b4d52" : "#c8c1b4", .58);
  const rgb = [0, 2, 4].map((offset) => Number.parseInt(accent.slice(1 + offset, 3 + offset), 16));
  const asHex = (values) => `#${values.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
  const secondary = asHex([rgb[1], rgb[2], rgb[0]]);
  const tertiary = asHex([rgb[2], rgb[0], rgb[1]]);
  root.dataset.theme = theme;
  root.dataset.workspaceTheme = theme;
  root.dataset.themePreference = settings.theme;
  root.dataset.density = settings.density || "comfortable";
  root.dataset.fontSize = settings.font_size || "comfortable";
  root.dataset.reduceMotion = String(Boolean(settings.reduce_motion));
  root.dataset.highContrast = String(Boolean(settings.high_contrast));
  root.dataset.decorations = String(settings.decorations !== false);
  root.style.colorScheme = theme;
  root.style.backgroundColor = colors.background;
  const aliases = {
    "--accent": accent, "--accent-hover": accentHover, "--accent-dark": accentHover,
    "--accent-secondary": secondary, "--accent-tertiary": tertiary,
    "--accent-soft": accentSoft, "--accent-border": accentBorder,
    "--primary": accent, "--primary-dark": accentHover, "--teal": accent,
    "--teal-dark": accentHover, "--mint": accentSoft, "--purple": accent,
    "--purple-dark": accentHover, "--purple-light": accentSoft,
    "--bg": colors.background, "--background": colors.background, "--paper": colors.background,
    "--panel": colors.surface, "--surface": colors.surface, "--surface-solid": colors.surface,
    "--white": colors.surface, "--page": colors.surface,
    "--panel-2": colors.surface2, "--surface-2": colors.surface2,
    "--surface-soft": colors.surface2, "--toolbar": colors.surface2,
    "--header": colors.surface2, "--grid": colors.border,
    "--selected": accentSoft, "--selected-border": accent,
    "--text": colors.text, "--ink": colors.text,
    "--muted": colors.muted, "--text-secondary": colors.muted,
    "--border": colors.border, "--line": colors.border, "--border-strong": colors.borderStrong,
    "--green": dark ? "#caff52" : "#477115",
    "--amber": dark ? "#f0bb62" : "#9a5b00",
    "--red": dark ? "#ff8b7a" : "#b93629",
    "--ws-color-rail": dark ? "#090a0c" : "#121315",
    "--ws-color-rail-text": "#f7f3ea",
    "--ws-color-rail-muted": dark ? "#8f908d" : "#9b9a93",
    "--ws-grid-line": dark ? "rgba(255,255,255,.045)" : "rgba(18,19,21,.055)",
    "--ws-color-background": colors.background, "--ws-color-surface": colors.surface,
    "--ws-color-surface-subtle": colors.surface2, "--ws-color-surface-hover": colors.surfaceHover,
    "--ws-color-border": colors.border, "--ws-color-border-strong": colors.borderStrong,
    "--ws-color-text": colors.text, "--ws-color-text-muted": colors.muted,
    "--ws-color-primary": accent, "--ws-color-primary-hover": accentHover,
    "--ws-color-primary-soft": accentSoft,
    "--ws-radius-small": "5px", "--ws-radius-medium": "8px", "--ws-radius-large": "12px",
    "--ws-shadow-1": dark ? "0 1px 0 rgba(255,255,255,.035), 0 8px 24px rgba(0,0,0,.20)" : "0 1px 0 rgba(18,19,21,.08), 0 7px 22px rgba(18,19,21,.045)",
    "--ws-shadow-2": dark ? "0 18px 44px rgba(0,0,0,.34)" : "0 14px 36px rgba(18,19,21,.11)",
    "--accent-gradient": `linear-gradient(135deg, ${accent}, ${accentHover})`,
    "--accent-soft-gradient": `linear-gradient(135deg, ${accentSoft}, color-mix(in srgb, ${accent} 12%, ${colors.surface}))`,
    "--surface-gradient": `linear-gradient(145deg, ${colors.surface}, color-mix(in srgb, ${accent} ${dark ? 8 : 5}%, ${colors.surface2}))`,
    "--hero-gradient": `linear-gradient(135deg, color-mix(in srgb, ${accent} ${dark ? 14 : 9}%, ${colors.surface}), ${colors.surface} 46%, color-mix(in srgb, ${accent} ${dark ? 8 : 5}%, ${colors.surface2}))`,
    "--section-accent": mix(accent, colors.surface, dark ? .78 : .88),
    "--section-secondary": mix(secondary, colors.surface, dark ? .82 : .91),
    "--section-tertiary": mix(tertiary, colors.surface, dark ? .84 : .93),
    "--section-accent-gradient": `linear-gradient(145deg, color-mix(in srgb, ${accent} ${dark ? 18 : 9}%, ${colors.surface}), color-mix(in srgb, ${accent} ${dark ? 8 : 4}%, ${colors.surface2}))`,
    "--section-secondary-gradient": `linear-gradient(145deg, color-mix(in srgb, ${secondary} ${dark ? 14 : 7}%, ${colors.surface}), color-mix(in srgb, ${secondary} ${dark ? 6 : 3}%, ${colors.surface2}))`,
    "--section-tertiary-gradient": `linear-gradient(145deg, color-mix(in srgb, ${tertiary} ${dark ? 12 : 6}%, ${colors.surface}), color-mix(in srgb, ${tertiary} ${dark ? 5 : 2}%, ${colors.surface2}))`,
  };
  for (const [name, value] of Object.entries(aliases)) root.style.setProperty(name, value);
})();
