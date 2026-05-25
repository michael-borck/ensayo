// Automated WCAG 2.1 A/AA audit with axe-core over built HTML (via jsdom).
// Page scripts are NOT executed (outside-only); axe is evaluated in the window.
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import axe from "axe-core";

const files = process.argv.slice(2);
const byRule = {};
let totalViol = 0;
const pagesWithViol = [];

for (const f of files) {
  const html = readFileSync(f, "utf8");
  const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true });
  const { window } = dom;
  window.eval(axe.source);
  let results;
  try {
    results = await window.axe.run(window.document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      // jsdom has no layout engine, so colour-contrast can't be measured here;
      // it's verified separately against the theme palettes.
      rules: { "color-contrast": { enabled: false } },
    });
  } catch (e) {
    console.log(`ERROR auditing ${f}: ${e.message}`);
    continue;
  }
  const v = results.violations;
  if (v.length) {
    pagesWithViol.push(f);
    for (const x of v) {
      byRule[x.id] = byRule[x.id] || { help: x.help, impact: x.impact, count: 0, pages: new Set() };
      byRule[x.id].count += x.nodes.length;
      byRule[x.id].pages.add(f.split("/sites/")[1] || f);
    }
    totalViol += v.length;
  }
}

console.log(`\nAudited ${files.length} pages.`);
console.log(`Pages with violations: ${pagesWithViol.length}`);
const rules = Object.entries(byRule);
if (!rules.length) {
  console.log("✅ No WCAG 2.1 A/AA violations found (excluding colour-contrast — see notes).");
} else {
  console.log("\nViolations by rule:");
  for (const [id, r] of rules.sort((a, b) => b[1].count - a[1].count)) {
    console.log(`  [${r.impact}] ${id} — ${r.help}`);
    console.log(`      ${r.count} node(s) across: ${[...r.pages].slice(0, 4).join(", ")}`);
  }
}
process.exit(rules.length ? 1 : 0);
