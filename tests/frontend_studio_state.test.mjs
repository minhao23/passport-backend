import assert from "node:assert/strict";
import { test } from "node:test";
import { mountFrontend } from "./frontend-test-utils.mjs";

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};
const photo = (name = "portrait.jpg", type = "image/jpeg") =>
  new File(["portrait"], name, { type });
const jpeg = () => new Response(new Blob(["jpeg"], { type: "image/jpeg" }));

function studio(t, overrides = {}) {
  const created = [];
  const revoked = [];
  const downloads = [];
  const harness = mountFrontend(
    "components/photo-studio/use-photo-studio.ts",
    (module) => module.usePhotoStudio(),
    {
      AbortController,
      FormData,
      Error,
      setTimeout,
      clearTimeout,
      URL: {
        createObjectURL(blob) {
          const url = `blob:${created.length}`;
          created.push({ url, blob });
          return url;
        },
        revokeObjectURL: (url) => revoked.push(url),
      },
      createImageBitmap: async () => ({ close() {} }),
      fetch: async () => jpeg(),
      ...overrides,
    },
    {
      "@/lib/photo-download": {
        downloadPassportPhoto: (...args) => downloads.push(args),
      },
    },
  );
  t.after(() => harness.unmount());
  return { ...harness, created, revoked, downloads };
}

test("processing actions restore focus locally on desktop and phone", () => {
  for (const mobile of [false, true]) {
    let loading = false;
    let generated = 0;
    let cancelled = 0;
    const focused = [];
    const harness = mountFrontend(
      "components/photo-studio/photo-processing-actions.tsx",
      (module) =>
        module.useProcessingActions(
          loading,
          async () => {
            generated++;
          },
          () => {
            cancelled++;
          },
        ),
      { window: { matchMedia: () => ({ matches: mobile }) } },
    );
    const actions = harness.render();
    actions.primaryAction.current = {
      focus: (options) => {
        assert.equal(options.preventScroll, true);
        focused.push("primary");
      },
    };
    actions.mobileCancel.current = { focus: () => focused.push("mobile") };
    actions.generate();
    loading = true;
    harness.render();
    assert.deepEqual(focused, [mobile ? "mobile" : "primary"]);
    loading = false;
    harness.render();
    assert.equal(focused.length, 1);
    loading = true;
    harness.render();
    assert.equal(focused.length, 1);
    actions.cancel();
    loading = false;
    harness.render();
    assert.deepEqual(focused, [mobile ? "mobile" : "primary", "primary"]);
    assert.equal(generated, 1);
    assert.equal(cancelled, 1);
    harness.unmount();
  }
});

test("selection, saved crops and reset preserve the original and release previews", async (t) => {
  const state = studio(t);
  const original = photo();
  await state.render().selectFile(original);
  const selected = state.render();
  const crop = { unit: "%", x: 10, y: 10, width: 80, height: 80 };
  const cropped = photo("crop.png", "image/png");
  assert.equal(selected.applyCrop(original, cropped, crop), true);
  const edited = state.render();
  assert.equal(edited.originalFile, original);
  assert.equal(edited.file, cropped);
  assert.equal(edited.savedCrop, crop);
  assert.equal(edited.applyCrop(photo("stale.jpg"), cropped, crop), false);
  assert.equal(edited.applyCrop(original, original, crop), true);
  assert.equal(state.render().savedCrop, null);
  await state.render().selectFile(photo("invalid.txt", "text/plain"));
  assert.equal(state.render().file, original);
  assert.equal(state.render().error.code, "PHOTO_ISSUE");
  state.render().removePhoto();
  const cleared = state.render();
  assert.equal(cleared.file, null);
  assert.equal(cleared.originalFile, null);
  assert.equal(cleared.preview, "");
  assert.equal(cleared.error, null);
  assert.deepEqual(
    state.revoked,
    state.created.map((entry) => entry.url),
  );
});

test("late image decoding cannot replace a newer selection or removed photo", async (t) => {
  const decodes = [];
  let closed = 0;
  const state = studio(t, {
    createImageBitmap: () => {
      const decode = deferred();
      decodes.push(decode);
      return decode.promise;
    },
  });
  const first = state.render().selectFile(photo("first.jpg"));
  const newer = photo("newer.jpg");
  const second = state.render().selectFile(newer);
  decodes[1].resolve({
    close() {
      closed++;
    },
  });
  await second;
  decodes[0].resolve({
    close() {
      closed++;
    },
  });
  await first;
  assert.equal(state.render().file, newer);
  const pending = state.render().selectFile(photo("removed.jpg"));
  state.render().removePhoto();
  decodes[2].resolve({
    close() {
      closed++;
    },
  });
  await pending;
  assert.equal(state.render().file, null);
  assert.equal(closed, 3);
});

test("cancellation preserves the photo and a late response cannot overwrite a retry", async (t) => {
  const requests = [];
  const state = studio(t, {
    fetch: (_, options) => {
      const pending = deferred();
      requests.push({ ...pending, options });
      return pending.promise;
    },
  });
  const original = photo();
  await state.render().selectFile(original);
  const first = state.render().generate();
  assert.equal(state.render().loading, true);
  state.render().cancelProcessing();
  assert.equal(state.render().file, original);
  assert.equal(state.render().error, null);
  assert.equal(state.render().loading, false);
  assert.equal(requests[0].options.signal.aborted, true);
  const retry = state.render().generate();
  requests[0].resolve(jpeg());
  await first;
  assert.equal(state.render().result, "");
  assert.equal(state.downloads.length, 0);
  requests[1].resolve(jpeg());
  await retry;
  const result = state.render();
  assert.equal(result.loading, false);
  assert.equal(result.result, state.created.at(-1).url);
  assert.deepEqual(state.downloads, [[result.result, "United States"]]);
  result.changeCountry("Singapore");
  assert.equal(state.render().result, "");
  assert.ok(state.revoked.includes(result.result));
});

test("one request owns processing; failures release it without losing the photo", async (t) => {
  const pending = deferred();
  let calls = 0;
  const state = studio(t, {
    fetch: () => {
      calls++;
      return pending.promise;
    },
  });
  const original = photo();
  await state.render().selectFile(original);
  const processing = state.render().generate();
  await state.render().generate();
  await state.render().selectFile(photo("replacement.jpg"));
  state.render().removePhoto();
  assert.equal(state.render().applyCrop(original, photo(), {}), false);
  assert.equal(calls, 1);
  pending.resolve(
    Response.json({ code: "PERSON_NOT_DETECTED" }, { status: 422 }),
  );
  await processing;
  assert.equal(state.render().loading, false);
  assert.equal(state.render().file, original);
  assert.equal(state.render().error.code, "PERSON_NOT_DETECTED");
  assert.equal(state.render().result, "");
  assert.equal(state.downloads.length, 0);
});

test("invalid JPEGs and request failures never create or download a result", async (t) => {
  for (const reply of [
    () => new Response(new Blob(["png"], { type: "image/png" })),
    () => new Response(new Blob([], { type: "image/jpeg" })),
    () => {
      throw new Error("Network unavailable");
    },
    () => {
      throw Object.assign(new Error("Timeout"), { name: "AbortError" });
    },
  ]) {
    const state = studio(t, { fetch: async () => reply() });
    await state.render().selectFile(photo());
    await state.render().generate();
    assert.equal(state.render().loading, false);
    assert.equal(state.render().error.code, "INTERNAL_SERVER_ERROR");
    assert.equal(state.render().result, "");
    assert.equal(state.downloads.length, 0);
  }
});

test("unmount aborts a pending request and suppresses its late result", async (t) => {
  const pending = deferred();
  let signal;
  const state = studio(t, {
    fetch: (_, options) => {
      signal = options.signal;
      return pending.promise;
    },
  });
  await state.render().selectFile(photo());
  const processing = state.render().generate();
  state.unmount();
  assert.equal(signal.aborted, true);
  pending.resolve(jpeg());
  await processing;
  assert.equal(state.created.length, 1);
  assert.equal(state.downloads.length, 0);
  assert.ok(state.revoked.includes(state.created[0].url));
});
