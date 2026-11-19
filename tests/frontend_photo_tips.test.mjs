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

test("completed results order download, rules and the informational re-crop footer", async () => {
  const workspace = await readFile(
    new URL("../frontend/components/photo-studio/photo-workspace.tsx", import.meta.url),
    "utf8",
  );
  const { outputText } = ts.transpileModule(workspace, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  });
  const exports = {};
  const require = createRequire(import.meta.url);
  runInNewContext(outputText, {
    exports,
    require: (name) =>
      name === "./photo-preparation-tips"
        ? { default: PhotoPreparationTips }
        : name === "@/lib/photo-download"
          ? { passportPhotoFilename: () => "passport-singapore.jpg" }
          : require(name),
  });
  for (const [result, loading] of [["", false], ["", true], ["blob:result", false]]) {
    const html = renderToStaticMarkup(createElement(exports.default, {
      country: "Singapore", size: [35, 45], preview: "blob:original",
      result, loading, cropped: false,
    }));
    assert.equal(html.includes("Re-crop your original photo and generate again"), !!result);
    assert.equal(html.includes('class="result-tip"'), !!result);
    if (result) {
      assert.match(html, /Try a few crops to find the fit you prefer/);
      assert.match(html, /Download JPEG/);
      assert.match(html, /class="output-details has-result"/);
      const tip = html.match(/<div class="result-tip">([\s\S]*?)<\/div>/)?.[1];
      assert.ok(tip);
      assert.match(tip, /<svg[^>]*aria-hidden="true"/);
      assert.match(tip, /width="14"/);
      assert.doesNotMatch(tip, /role="status"|<button|<a[\s>]/);
      assert.doesNotMatch(html, /If the download/);
      assert.ok(html.indexOf("Download JPEG") < html.indexOf('class="result-check"'));
      assert.ok(html.indexOf('class="result-check"') < html.indexOf('class="result-tip"'));
    }
  }
});
