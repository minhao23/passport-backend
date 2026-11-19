import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(
  new URL(
    "../frontend/components/photo-studio/photo-preparation-tips.tsx",
    import.meta.url,
  ),
  "utf8",
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  },
});
const exports = {};
runInNewContext(outputText, {
  exports,
  require: createRequire(import.meta.url),
});
const PhotoPreparationTips = exports.default;
const renderTips = (country) =>
  renderToStaticMarkup(createElement(PhotoPreparationTips, { country }));

test("photo tips cover framing, selfies, lighting and headwear exceptions", () => {
  const html = renderTips("United States");
  assert.equal((html.match(/<li>/g) ?? []).length, 4);
  assert.match(html, /above the armpits/);
  assert.match(html, /full head, shoulders/);
  assert.match(html, /eye level/);
  assert.match(html, /eyes open and mouth closed/);
  assert.match(html, /close-up selfies/);
  assert.match(html, /even lighting/);
  assert.match(html, /beauty filters/);
  assert.match(html, /No headwear or sunglasses/);
  assert.match(html, /Religious or medical coverings may be/);
});

test("UK online applicants are advised to keep an uncropped original", () => {
  const html = renderTips("United Kingdom");
  assert.match(html, /UK online applications/);
  assert.match(html, /uncropped original/);
  assert.match(html, /head, shoulders and upper body/);
  assert.doesNotMatch(html, /above the armpits/);
});

test("tips are a named informational section, not an announcement or extra action", () => {
  const html = renderTips("Canada");
  assert.match(html, /aria-labelledby="workspace-tips-title"/);
  assert.match(html, /<h4 id="workspace-tips-title">Photo tips<\/h4>/);
  assert.doesNotMatch(
    html,
    /role="(?:status|alert)"|aria-live|<button|<a[\s>]/,
  );
});
