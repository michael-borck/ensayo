// @ts-check
import { defineConfig } from "astro/config";

// `base` lets the same theme deploy at a site root (single-company) or under a
// subpath (multi-site, e.g. /nexuspoint/). The generator sets ENSAYO_BASE.
const base = process.env.ENSAYO_BASE || "/";

export default defineConfig({
  base,
  build: { format: "directory" },
  // Sites are fully static; no adapter needed.
});
