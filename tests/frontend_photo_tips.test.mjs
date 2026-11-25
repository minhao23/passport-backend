import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

async function loadComponent(filename, stubs = {}, globals = {}) {
  const source = await readFile(
    new URL(`../frontend/components/photo-studio/${filename}`, import.meta.url),
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
  const require = createRequire(import.meta.url);
  runInNewContext(outputText, {
    exports,
    require: (name) => stubs[name] ?? require(name),
    ...globals,
  });
  return exports.default;
}

const helpStyles = { default: new Proxy({}, { get: (_, name) => name }) };
const PhotoPreparationTips = await loadComponent("photo-preparation-tips.tsx");
const PhotoFramingHelp = await loadComponent("photo-framing-help.tsx", {
  "./photo-framing-help.module.css": helpStyles,
});
const renderTips = (country, compact = false) =>
  renderToStaticMarkup(
    createElement(PhotoPreparationTips, { country, compact }),
  );

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

test("mobile tips start collapsed and retain the same country-specific advice", () => {
  for (const country of ["United States", "United Kingdom"]) {
    const regular = renderTips(country);
    const compact = renderTips(country, true);
    assert.match(compact, /<details class="mobile-photo-tips">/);
    assert.match(compact, /<summary>Photo tips/);
    assert.doesNotMatch(
      compact,
      /<details[^>]*\bopen\b|\bid=|role="(?:status|alert)"/,
    );
    assert.deepEqual(
      compact.match(/<li>[\s\S]*?<\/li>/g),
      regular.match(/<li>[\s\S]*?<\/li>/g),
    );
  }
});

test("completed results order download, rules and collapsed framing help", async () => {
  const PhotoWorkspace = await loadComponent("photo-workspace.tsx", {
    "./photo-preparation-tips": { default: PhotoPreparationTips },
    "./photo-framing-help": { default: PhotoFramingHelp },
    "@/lib/photo-download": {
      passportPhotoFilename: () => "passport-singapore.jpg",
    },
  });
  for (const [result, loading] of [
    ["", false],
    ["", true],
    ["blob:result", false],
  ]) {
    const html = renderToStaticMarkup(
      createElement(PhotoWorkspace, {
        country: "Singapore",
        size: [35, 45],
        preview: "blob:original",
        result,
        loading,
        cropped: false,
      }),
    );
    assert.equal(html.includes("Not happy with the framing?"), !!result);
    assert.equal(html.includes("Photo looks off-center"), !!result);
    assert.equal(html.includes('aria-label="Framing tips"'), !!result);
    assert.equal(html.includes('class="mobile-preview-switch"'), !!result);
    assert.equal(html.includes('class="mobile-photo-tips"'), !result);
    assert.equal(html.includes('class="mobile-processing-action"'), loading);
    assert.match(html, /class="quiet-button mobile-remove"/);
    if (result) {
      assert.match(html, /Download JPEG/);
      assert.match(html, /class="output-details has-result"/);
      assert.match(html, /aria-label="Framing tips" hidden=""/);
      assert.match(html, /aria-expanded="false"/);
      assert.match(html, /<figure[^>]*data-open="false" aria-label=/);
      assert.doesNotMatch(html, /<figure[^>]*role="img"/);
      assert.doesNotMatch(html, /Pause|Play|motionControl/);
      assert.match(html, /Center your face in the crop with similar space/);
      assert.match(html, /Center your face<br\/>in the crop/);
      assert.match(html, /Shoulders cropped too tightly/);
      assert.match(
        html,
        /Use the crop tool on your original photo to center your face/,
      );
      assert.match(html, /with similar space on both sides/);
      assert.match(html, /Not facing straight ahead/);
      assert.doesNotMatch(html, /href="#photo-tips"|role="dialog"|aria-live/);
      assert.doesNotMatch(html, /If the download/);
      assert.ok(
        html.indexOf("Download JPEG") < html.indexOf('class="result-check"'),
      );
      assert.ok(
        html.indexOf('class="result-check"') <
          html.indexOf('aria-label="Framing tips"'),
      );
      assert.ok(
        html.indexOf("Common issues") <
          html.indexOf("Not happy with the framing?"),
      );
      assert.match(html, /data-preview="result"/);
      assert.match(html, /aria-label="Photo preview"/);
      assert.match(html, /aria-pressed="false">Original<\/button>/);
      assert.match(html, /aria-pressed="true">Result<\/button>/);
    } else {
      assert.match(html, /data-preview="original"/);
      assert.match(html, /Tap photo to crop/);
      assert.match(html, /Double-click to crop/);
      assert.equal((html.match(/id="workspace-tips-title"/g) ?? []).length, 1);
    }
  }
});

test("framing help toggles its disclosure without playback controls", async () => {
  let open = false;
  const Help = await loadComponent("photo-framing-help.tsx", {
    "./photo-framing-help.module.css": helpStyles,
    react: {
      useEffect: () => {},
      useId: () => "framing-help-test",
      useRef: () => ({ current: null }),
      useState: () => [
        open,
        (update) => {
          open = update(open);
        },
      ],
    },
  });

  for (const expectedOpen of [false, true, false]) {
    const [content, button] = Help().props.children;
    assert.equal(content.props.id, button.props["aria-controls"]);
    assert.equal(content.props.hidden, !expectedOpen);
    assert.equal(button.props["aria-expanded"], expectedOpen);
    assert.equal(button.props.type, "button");
    const guide = content.props.children[0].props.children[0];
    assert.equal(guide.props["data-open"], expectedOpen);
    assert.equal(
      guide.props.children.some((child) => child.type === "button"),
      false,
    );
    button.props.onClick();
  }
});

test("centering loop pauses offscreen or in a hidden tab and respects reduced motion", async () => {
  let intersection;
  let cleanup;
  let disconnected = false;
  const animation = {
    playState: "running",
    pause() {
      this.playState = "paused";
    },
    play() {
      this.playState = "running";
    },
  };
  let animations = [animation];
  const guide = { dataset: {}, getAnimations: () => animations };
  const visibilityListeners = new Map();
  const preferenceListeners = new Map();
  const document = {
    hidden: false,
    addEventListener: (name, callback) =>
      visibilityListeners.set(name, callback),
    removeEventListener: (name) => visibilityListeners.delete(name),
  };
  const preference = {
    matches: false,
    addEventListener: (name, callback) =>
      preferenceListeners.set(name, callback),
    removeEventListener: (name) => preferenceListeners.delete(name),
  };
  const Help = await loadComponent(
    "photo-framing-help.tsx",
    {
      "./photo-framing-help.module.css": helpStyles,
      react: {
        useEffect: (effect) => {
          cleanup = effect();
        },
        useId: () => "motion-test",
        useRef: () => ({ current: guide }),
        useState: () => [true, () => {}],
      },
    },
    {
      document,
      window: { matchMedia: () => preference },
      IntersectionObserver: class {
        constructor(callback) {
          intersection = callback;
        }
        observe(element) {
          assert.equal(element, guide);
        }
        disconnect() {
          disconnected = true;
        }
      },
    },
  );

  Help();
  assert.equal(guide.dataset.motionEnabled, "true");
  assert.equal(animation.playState, "paused");
  intersection([{ isIntersecting: true }]);
  assert.equal(animation.playState, "running");
  document.hidden = true;
  visibilityListeners.get("visibilitychange")();
  assert.equal(animation.playState, "paused");
  document.hidden = false;
  visibilityListeners.get("visibilitychange")();
  assert.equal(animation.playState, "running");
  intersection([{ isIntersecting: false }]);
  assert.equal(animation.playState, "paused");
  intersection([{ isIntersecting: true }]);
  assert.equal(animation.playState, "running");
  preference.matches = true;
  preferenceListeners.get("change")();
  assert.equal(animation.playState, "paused");
  // Reduced motion removes the CSS animation; an old handle must stay idle.
  animations = [];
  animation.playState = "idle";
  intersection([{ isIntersecting: true }]);
  assert.equal(animation.playState, "idle");
  cleanup();
  assert.equal(disconnected, true);
  assert.equal(visibilityListeners.size, 0);
  assert.equal(preferenceListeners.size, 0);
});
