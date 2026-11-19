import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import ts from "typescript";

// Transpile this browser utility without requiring a DOM or a Next.js server.
const source = await readFile(new URL("../frontend/lib/photo-crop.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { cropPixels, createCroppedFile, FULL_PHOTO_CROP } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const crop = { unit: "%", x: 10, y: 20, width: 50, height: 40 };
const image = { naturalWidth: 1200, naturalHeight: 1800 };
const original = new File(["original"], "portrait.jpg", { type: "image/jpeg" });

test("crop coordinates use original pixels, not the displayed preview size", () => {
  assert.deepEqual(cropPixels(crop, 1200, 1800), {
    x: 120, y: 360, width: 600, height: 720,
  });
});

test("rounding never exports pixels outside the image", () => {
  assert.deepEqual(cropPixels({ ...crop, x: 33.333, y: 0, width: 66.667, height: 100 }, 101, 79), {
    x: 34, y: 0, width: 67, height: 79,
  });
});

test("invalid or empty crop rectangles fail", () => {
  for (const invalid of [
    { ...crop, width: 0 }, { ...crop, height: -1 },
    { ...crop, x: NaN }, { ...crop, x: 150 },
  ]) assert.throws(() => cropPixels(invalid, 1200, 1800), /rectangle/);
  assert.throws(() => cropPixels(crop, 0, 1800), /rectangle/);
});

test("reset uses the original file without re-encoding it", async () => {
  assert.equal(await createCroppedFile(original, image, FULL_PHOTO_CROP, 100), original);
});

function mockCanvas(t, blob, available = true) {
  const calls = [];
  const canvas = {
    width: 0,
    height: 0,
    getContext: () => available ? { drawImage: (...args) => calls.push(args) } : null,
    toBlob: (callback, type) => {
      assert.equal(type, "image/png");
      callback(blob);
    },
  };
  const previous = Object.getOwnPropertyDescriptor(globalThis, "document");
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: { createElement: () => canvas },
  });
  t.after(() => {
    if (previous) Object.defineProperty(globalThis, "document", previous);
    else delete globalThis.document;
  });
  return { canvas, calls };
}

test("export saves a lossless cropped file and releases canvas memory", async (t) => {
  const { canvas, calls } = mockCanvas(t, new Blob(["cropped pixels"], { type: "image/png" }));
  const file = await createCroppedFile(original, image, crop, 1000);
  assert.equal(file.name, "portrait-cropped.png");
  assert.equal(file.type, "image/png");
  assert.deepEqual(calls[0], [image, 120, 360, 600, 720, 0, 0, 600, 720]);
  assert.equal(canvas.width, 0);
  assert.equal(canvas.height, 0);
});

test("oversized crop export fails without silently lowering image quality", async (t) => {
  const { canvas } = mockCanvas(t, new Blob(["too large"]));
  await assert.rejects(createCroppedFile(original, image, crop, 1), /over 10 MB/);
  assert.equal(canvas.width, 0);
});

test("encoding failure releases canvas memory", async (t) => {
  const { canvas } = mockCanvas(t, null);
  await assert.rejects(createCroppedFile(original, image, crop, 100), /couldn't save/);
  assert.equal(canvas.width, 0);
});

test("missing canvas support reports a recoverable error", async (t) => {
  const { canvas } = mockCanvas(t, null, false);
  await assert.rejects(createCroppedFile(original, image, crop, 100), /couldn't crop/);
  assert.equal(canvas.height, 0);
});

test("large output dimensions are rejected before allocating a canvas", async () => {
  await assert.rejects(
    createCroppedFile(original, { naturalWidth: 12000, naturalHeight: 12000 }, crop, 100),
    /smaller crop/,
  );
});
