import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(
  new URL("../frontend/components/photo-guide.tsx", import.meta.url),
  "utf8",
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  },
});
const require = createRequire(import.meta.url);
const exports = {};
runInNewContext(outputText, {
  exports,
  require: (name) => {
    if (name === "@/assets/sample_rules.jpg") {
      return {
        default: {
          src: "/_next/static/media/sample_rules.test.jpg",
          width: 653,
          height: 3058,
        },
      };
    }
    if (name === "./photo-guide.module.css") {
      return { default: new Proxy({}, { get: (_, key) => key }) };
    }
    return require(name);
  },
});
const html = renderToStaticMarkup(createElement(exports.default));

test("sample photo examples are an initially closed native disclosure after the warning", () => {
  assert.match(html, /aria-label="Before you submit"/);
  assert.match(html, /acceptance isn&#x27;t guaranteed/);
  assert.match(html, /<details class="examples"><summary>/);
  assert.match(html, /View photo examples/);
  assert.doesNotMatch(html, /<details[^>]*\bopen\b|role="dialog"|aria-live/);
  assert.ok(html.indexOf("Before you submit.") < html.indexOf("<details"));
  assert.match(html, /Check your issuing authority&#x27;s current rules/);
});

test("the clearer supplied JPG is shown inline without a popup or image link", async () => {
  const image = await readFile(
    new URL("../frontend/assets/sample_rules.jpg", import.meta.url),
  );
  assert.equal(image.readUInt16BE(0), 0xffd8);
  assert.doesNotMatch(
    html,
    /<a\b|target="_blank"|Open full-size image|role="dialog"/,
  );
  assert.match(
    html,
    /alt="Singapore ICA photo guidelines comparing unsuitable and suitable portraits."/,
  );
  assert.match(html, /width="653" height="3058"/);
  assert.match(html, /src="\/_next\/static\/media\/sample_rules.test.jpg"/);
});

test("the guide shows only the requested attribution above the image", () => {
  assert.match(html, /<p>taken from: Singapore ICA\.<\/p><img/);
  assert.equal((html.match(/<details\b/g) ?? []).length, 1);
  assert.doesNotMatch(
    html,
    /Text version|textVersion|<ul\b|<li\b|Examples cover|sample reference|current rules take precedence/i,
  );
});

test("the footer retains only the contact link", async () => {
  const footerSource = await readFile(
    new URL("../frontend/components/site-footer.tsx", import.meta.url),
    "utf8",
  );
  const { outputText: footerCode } = ts.transpileModule(footerSource, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
    },
  });
  const footerExports = {};
  runInNewContext(footerCode, { exports: footerExports, require });
  const footer = renderToStaticMarkup(createElement(footerExports.default));
  assert.equal((footer.match(/<a\b/g) ?? []).length, 1);
  assert.match(footer, /Contact me/);
  assert.match(footer, /href="https:\/\/minhao\.dev\/home"/);
  assert.doesNotMatch(footer, /Passport Studio|Back to your photo|href="#/);
});
