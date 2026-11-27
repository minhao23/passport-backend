import assert from "node:assert/strict";
import { test } from "node:test";
import {
  framingError,
  heicPhoto,
  loadFrontendESModule,
  loadFrontendModule,
  mockGlobal,
} from "./frontend-test-utils.mjs";

const { cropPixels, createCroppedFile, FULL_PHOTO_CROP } =
  await loadFrontendESModule("lib/photo-crop.ts");
const { passportPhotoFilename } = await loadFrontendESModule(
  "lib/photo-download.ts",
);
const crop = { unit: "%", x: 10, y: 20, width: 50, height: 40 };
const image = { naturalWidth: 1200, naturalHeight: 1800 };
const original = new File(["original"], "portrait.jpg", { type: "image/jpeg" });
const { normalizePhotoError } = await loadFrontendESModule(
  "lib/photo-errors.ts",
);
const { MAX_FILE_SIZE, PHOTO_ACCEPT } =
  await loadFrontendESModule("lib/countries.ts");

test("upload selection accepts HEIC MIME types and gallery extensions at 15 MiB", () => {
  assert.equal(MAX_FILE_SIZE, 15 * 1024 * 1024);
  for (const type of ["image/heic", "image/heif", ".heic", ".heif"])
    assert.ok(PHOTO_ACCEPT.split(",").includes(type));
});

test("unsupported-format guidance recommends JPG, PNG or WebP", async () => {
  const { preparePhoto } = loadFrontendModule("lib/photo-loading.ts");
  await assert.rejects(
    preparePhoto(new File(["photo"], "photo.tiff", { type: "image/tiff" })),
    { message: "Please choose a JPG, PNG, or WebP photo." },
  );
});

test("HEIC header dimensions are bounded before conversion or pixel decoding", async () => {
  const { checkHeicDimensions } = loadFrontendModule("lib/photo-loading.ts");
  await checkHeicDimensions(heicPhoto());
  for (const [width, height] of [
    [5000, 4001],
    [10001, 1],
    [0, 20],
  ]) {
    await assert.rejects(
      checkHeicDimensions(heicPhoto("test.heic", "image/heic", width, height)),
    );
  }
  for (const bytes of [[], [0, 0, 0, 1], Buffer.from("not a HEIF container")]) {
    await assert.rejects(checkHeicDimensions(new Blob([bytes])));
  }
  const truncated = await heicPhoto().arrayBuffer();
  await assert.rejects(checkHeicDimensions(new Blob([truncated.slice(0, -1)])));
});

test("HEIC converts locally with native image support or the lazy decoder", async () => {
  for (const native of [true, false]) {
    const created = [];
    const revoked = [];
    let conversions = 0;
    const jpeg = new Blob(["converted"], { type: "image/jpeg" });
    const canvas = {
      width: 0,
      height: 0,
      getContext: () => ({ drawImage() {} }),
      toBlob(callback, type, quality) {
        assert.equal(type, "image/jpeg");
        assert.equal(quality, 1);
        callback(jpeg);
      },
    };
    class GalleryImage {
      naturalWidth = 32;
      naturalHeight = 48;
      set src(value) {
        if (value)
          queueMicrotask(() => (native ? this.onload() : this.onerror()));
      }
    }
    const { preparePhoto } = loadFrontendModule(
      "lib/photo-loading.ts",
      {
        "heic-to/csp": {
          heicTo: async ({ blob, type, quality }) => {
            conversions++;
            assert.equal(blob.type, "");
            assert.equal(type, "image/jpeg");
            assert.equal(quality, 1);
            return jpeg;
          },
        },
      },
      {
        File,
        Image: GalleryImage,
        document: { createElement: () => canvas },
        URL: {
          createObjectURL: () => {
            created.push("blob:preview");
            return created.at(-1);
          },
          revokeObjectURL: (url) => revoked.push(url),
        },
      },
    );
    const prepared = await preparePhoto(heicPhoto("IMG_1234.HEIC", ""));
    assert.equal(prepared.type, "image/jpeg");
    assert.equal(prepared.name, "IMG_1234.jpg");
    assert.equal(conversions, native ? 0 : 1);
    assert.deepEqual(revoked, created);
    assert.equal(canvas.width, 0);
    assert.equal(canvas.height, 0);
  }
});

test("conversion failure and converted files over 15 MiB are recoverable", async () => {
  let fail = true;
  class UnsupportedImage {
    set src(value) {
      if (value) queueMicrotask(() => this.onerror());
    }
  }
  const { preparePhoto } = loadFrontendModule(
    "lib/photo-loading.ts",
    {
      "heic-to/csp": {
        heicTo: async () => {
          if (fail) throw new Error("invalid HEIC data");
          return new Blob([Buffer.alloc(MAX_FILE_SIZE + 1)], {
            type: "image/jpeg",
          });
        },
      },
    },
    {
      File,
      Image: UnsupportedImage,
      URL: { createObjectURL: () => "blob:heic", revokeObjectURL() {} },
    },
  );
  await assert.rejects(preparePhoto(heicPhoto()), /invalid HEIC/);
  fail = false;
  await assert.rejects(
    preparePhoto(heicPhoto()),
    /exceeds 15 MB after conversion/,
  );
  await assert.rejects(
    preparePhoto(
      new File([Buffer.alloc(MAX_FILE_SIZE + 1)], "large.heic", {
        type: "image/heic",
      }),
    ),
    /15 MB or smaller/,
  );
});

test("Safari image-element fallback validates JPEG when bitmap decoding is unavailable", async () => {
  let released = false;
  class JpegImage {
    set src(value) {
      if (value) queueMicrotask(() => this.onload());
    }
  }
  const { preparePhoto } = loadFrontendModule(
    "lib/photo-loading.ts",
    {},
    {
      Image: JpegImage,
      URL: {
        createObjectURL: () => "blob:jpeg",
        revokeObjectURL: () => {
          released = true;
        },
      },
    },
  );
  assert.equal(await preparePhoto(original), original);
  assert.equal(released, true);
});

test("framing tips survive proxy and browser normalization without parsing prose", () => {
  const error = normalizePhotoError(framingError, 422);
  assert.deepEqual(error, {
    ...framingError,
    title: "This photo needs a little attention",
  });
  assert.deepEqual(normalizePhotoError(error, 422), error);
  for (const tips of [
    undefined,
    null,
    [],
    "not a list",
    [1],
    [""],
    [" ", "Tip"],
  ]) {
    assert.equal(
      normalizePhotoError({ ...framingError, tips }, 422).tips,
      undefined,
    );
  }
  for (const code of [
    "INTERNAL_SERVER_ERROR",
    "SERVICE_BUSY",
    "PERSON_NOT_DETECTED",
    "INVALID_COUNTRY",
  ]) {
    assert.equal(
      normalizePhotoError({ ...framingError, code }, 422).tips,
      undefined,
    );
  }
  assert.equal(
    normalizePhotoError(
      { code: "PHOTO_ISSUE", detail: "Existing message." },
      422,
    ).detail,
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
    /over 15 MB/,
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

test("downloads use a country-specific JPEG filename", () => {
  for (const [country, slug] of [
    ["United States", "united-states"],
    ["United Kingdom", "united-kingdom"],
    ["Trinidad and Tobago", "trinidad-and-tobago"],
  ])
    assert.equal(passportPhotoFilename(country), `passport-${slug}.jpg`);
});
