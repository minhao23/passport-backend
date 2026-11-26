import assert from "node:assert/strict";
import { test } from "node:test";
import {
  framingError,
  loadFrontendESModule,
  mockGlobal,
} from "./frontend-test-utils.mjs";

const { cropPixels, createCroppedFile, FULL_PHOTO_CROP } =
  await loadFrontendESModule("lib/photo-crop.ts");
const { downloadPassportPhoto, passportPhotoFilename } =
  await loadFrontendESModule("lib/photo-download.ts");
const crop = { unit: "%", x: 10, y: 20, width: 50, height: 40 };
const image = { naturalWidth: 1200, naturalHeight: 1800 };
const original = new File(["original"], "portrait.jpg", { type: "image/jpeg" });
const { normalizePhotoError } = await loadFrontendESModule("lib/photo-errors.ts");

test("framing tips survive proxy and browser normalization without parsing prose", () => {
  const error = normalizePhotoError(framingError, 422);
  assert.deepEqual(error, {
    ...framingError,
    title: "This photo needs a little attention",
  });
  assert.deepEqual(normalizePhotoError(error, 422), error);
  for (const tips of [undefined, null, [], "not a list", [1], [""], [" ", "Tip"]]) {
    assert.equal(
      normalizePhotoError({ ...framingError, tips }, 422).tips,
      undefined,
    );
  }
  for (const code of [
    "INTERNAL_SERVER_ERROR", "SERVICE_BUSY", "PERSON_NOT_DETECTED", "INVALID_COUNTRY",
  ]) {
    assert.equal(
      normalizePhotoError({ ...framingError, code }, 422).tips,
      undefined,
    );
  }
  assert.equal(
    normalizePhotoError({ code: "PHOTO_ISSUE", detail: "Existing message." }, 422).detail,
    "Existing message.",
  );
});

test("crop coordinates use original pixels, not the displayed preview size", () => {
  assert.deepEqual(cropPixels(crop, 1200, 1800), {
    x: 120,
    y: 360,
    width: 600,
    height: 720,
  });
});

test("rounding never exports pixels outside the image", () => {
  assert.deepEqual(
    cropPixels(
      { ...crop, x: 33.333, y: 0, width: 66.667, height: 100 },
      101,
      79,
    ),
    {
      x: 34,
      y: 0,
      width: 67,
      height: 79,
    },
  );
});

test("invalid or empty crop rectangles fail", () => {
  for (const invalid of [
    { ...crop, width: 0 },
    { ...crop, height: -1 },
    { ...crop, x: NaN },
    { ...crop, x: 150 },
  ])
    assert.throws(() => cropPixels(invalid, 1200, 1800), /rectangle/);
  assert.throws(() => cropPixels(crop, 0, 1800), /rectangle/);
});

test("reset uses the original file without re-encoding it", async () => {
  assert.equal(
    await createCroppedFile(original, image, FULL_PHOTO_CROP, 100),
    original,
  );
});

function mockCanvas(t, blob, available = true) {
  const calls = [];
  const canvas = {
    width: 0,
    height: 0,
    getContext: () =>
      available ? { drawImage: (...args) => calls.push(args) } : null,
    toBlob: (callback, type) => {
      assert.equal(type, "image/png");
      callback(blob);
    },
  };
  mockGlobal(t, "document", { createElement: () => canvas });
  return { canvas, calls };
}

test("export saves a lossless cropped file and releases canvas memory", async (t) => {
  const { canvas, calls } = mockCanvas(
    t,
    new Blob(["cropped pixels"], { type: "image/png" }),
  );
  const file = await createCroppedFile(original, image, crop, 1000);
  assert.equal(file.name, "portrait-cropped.png");
  assert.equal(file.type, "image/png");
  assert.deepEqual(calls[0], [image, 120, 360, 600, 720, 0, 0, 600, 720]);
  assert.equal(canvas.width, 0);
  assert.equal(canvas.height, 0);
});

for (const [name, blob, available, limit, error, dimension] of [
  [
    "oversized crop export fails without silently lowering image quality",
    new Blob(["too large"]),
    true,
    1,
    /over 10 MB/,
    "width",
  ],
  [
    "encoding failure releases canvas memory",
    null,
    true,
    100,
    /couldn't save/,
    "width",
  ],
  [
    "missing canvas support reports a recoverable error",
    null,
    false,
    100,
    /couldn't crop/,
    "height",
  ],
]) {
  test(name, async (t) => {
    const { canvas } = mockCanvas(t, blob, available);
    await assert.rejects(
      createCroppedFile(original, image, crop, limit),
      error,
    );
    assert.equal(canvas[dimension], 0);
  });
}

test("large output dimensions are rejected before allocating a canvas", async () => {
  await assert.rejects(
    createCroppedFile(
      original,
      { naturalWidth: 12000, naturalHeight: 12000 },
      crop,
      100,
    ),
    /smaller crop/,
  );
});

test("automatic and manual downloads use a country-specific JPEG filename", () => {
  for (const [country, slug] of [
    ["United States", "united-states"],
    ["United Kingdom", "united-kingdom"],
    ["Trinidad and Tobago", "trinidad-and-tobago"],
  ])
    assert.equal(passportPhotoFilename(country), `passport-${slug}.jpg`);
});

function mockDocument(t, blocked = false) {
  const actions = [];
  const link = {
    click() {
      actions.push("click");
      if (blocked) throw new Error("Browser blocked download");
    },
    remove() {
      actions.push("remove");
    },
  };
  mockGlobal(t, "document", {
    createElement: (tag) => {
      assert.equal(tag, "a");
      return link;
    },
    body: {
      appendChild: (element) => {
        assert.equal(element, link);
        actions.push("append");
      },
    },
  });
  return { link, actions };
}

test("starts one download and removes its temporary link", (t) => {
  const { link, actions } = mockDocument(t);
  downloadPassportPhoto("blob:result", "United States");
  assert.equal(link.href, "blob:result");
  assert.equal(link.download, "passport-united-states.jpg");
  assert.equal(link.hidden, true);
  assert.deepEqual(actions, ["append", "click", "remove"]);
});

test("a blocked automatic download does not fail photo processing", (t) => {
  const { actions } = mockDocument(t, true);
  assert.doesNotThrow(() => downloadPassportPhoto("blob:result", "Canada"));
  assert.deepEqual(actions, ["append", "click", "remove"]);
});
