import { coreUrl } from "./origin.js";
import { initializeSplitView } from "./split-view.js";

const sourceValue = new URL(location.href).searchParams.get("source") || "";
let source;
try {
  source = new URL(sourceValue, location.origin);
} catch {
  source = null;
}

if (!source || source.origin !== location.origin || !initializeSplitView(source.href)) {
  location.replace(coreUrl("/"));
}
