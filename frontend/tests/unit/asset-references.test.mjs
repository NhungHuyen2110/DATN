import assert from "node:assert/strict";
import test from "node:test";
import { readdir, readFile, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
async function filesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const groups = await Promise.all(entries.filter(entry =>
    !["node_modules", "test-results"].includes(entry.name)
  ).map(entry => entry.isDirectory() ? filesIn(resolve(directory, entry.name)) : resolve(directory, entry.name)));
  return groups.flat();
}

test("HTML script/styles and literal ES module imports resolve to existing files", async () => {
  const files = await filesIn(root);
  let checked = 0;
  for (const file of files.filter(file => /\.(html|js|mjs)$/.test(file))) {
    const source = await readFile(file, "utf8");
    const expressions = file.endsWith(".html")
      ? [/<script\b[^>]*\bsrc=["']([^"']+)["']/gi, /<link\b[^>]*\bhref=["']([^"']+\.css)["']/gi]
      : [/\bfrom\s+["'](\.[^"']+)["']/g, /\bimport\(["'](\.[^"']+)["']\)/g];
    for (const expression of expressions) {
      for (const [, path] of source.matchAll(expression)) {
        if (/^(https?:|\/\/)/.test(path)) continue;
        await assert.doesNotReject(access(resolve(dirname(file), path)), `${file}: ${path}`);
        checked++;
      }
    }
  }
  assert.ok(checked > 100, "Check the real entrypoint graph, including compatibility scripts");
  await access(resolve(root, "assets/js/backend-console.js"));
});
