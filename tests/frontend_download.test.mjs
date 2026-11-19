import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../frontend/lib/photo-download.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { downloadPassportPhoto, passportPhotoFilename } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);

test("automatic and manual downloads use a country-specific JPEG filename", () => {
  assert.equal(passportPhotoFilename("United States"), "passport-united-states.jpg");
  assert.equal(passportPhotoFilename("United Kingdom"), "passport-united-kingdom.jpg");
  assert.equal(passportPhotoFilename("Trinidad and Tobago"), "passport-trinidad-and-tobago.jpg");
});

function mockDocument(t, blocked = false) {
  const actions = [];
  const link = {
    click() {
      actions.push("click");
      if (blocked) throw new Error("Browser blocked download");
    },
    remove() { actions.push("remove"); },
  };
  const previous = Object.getOwnPropertyDescriptor(globalThis, "document");
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: {
      createElement: tag => {
        assert.equal(tag, "a");
        return link;
      },
      body: { appendChild: element => {
        assert.equal(element, link);
        actions.push("append");
      } },
    },
  });
  t.after(() => {
    if (previous) Object.defineProperty(globalThis, "document", previous);
    else delete globalThis.document;
  });
  return { link, actions };
}

test("starts one download and removes its temporary link", t => {
  const { link, actions } = mockDocument(t);
  downloadPassportPhoto("blob:result", "United States");
  assert.equal(link.href, "blob:result");
  assert.equal(link.download, "passport-united-states.jpg");
  assert.equal(link.hidden, true);
  assert.deepEqual(actions, ["append", "click", "remove"]);
});

test("a blocked automatic download does not fail photo processing", t => {
  const { actions } = mockDocument(t, true);
  assert.doesNotThrow(() => downloadPassportPhoto("blob:result", "Canada"));
  assert.deepEqual(actions, ["append", "click", "remove"]);
});
