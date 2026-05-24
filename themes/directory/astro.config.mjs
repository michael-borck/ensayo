// @ts-check
import { defineConfig } from "astro/config";

const base = process.env.ENSAYO_BASE || "/";

export default defineConfig({
  base,
  build: { format: "directory" },
});
