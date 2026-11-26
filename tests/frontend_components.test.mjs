import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  assertMarkup,
  framingError,
  loadFrontendModule,
  mountFrontend,
} from "./frontend-test-utils.mjs";

const render = (component, props) =>
  renderToStaticMarkup(createElement(component, props));
const helpPath = "components/photo-studio/photo-framing-help.tsx";
const { default: PassportPage } = loadFrontendModule(
  "components/passport-page.tsx",
  {
    "./photo-studio/photo-studio": {
      default: () => createElement("div", { "data-studio": true }),
    },
    "@/assets/sample_rules.jpg": {
      default: {
        src: "/_next/static/media/sample_rules.test.jpg",
        width: 653,
        height: 3058,
      },
    },
  },
);
const page = render(PassportPage);
const guidance = page.match(/<aside\b[\s\S]*?<\/aside>/)[0];

test("framing errors show an introduction and two semantic list tips", () => {
  const { normalizePhotoError } = loadFrontendModule("lib/photo-errors.ts");
  for (const payload of [
    framingError, { code: "PHOTO_ISSUE", detail: "Use a smaller photo." },
  ]) {
    const error = normalizePhotoError(payload, 422);
    const { default: PhotoStudio } = loadFrontendModule(
      "components/photo-studio/photo-studio.tsx",
      {
        "next/dynamic": { default: () => () => null },
        "@/components/background-comparison": { default: () => null },
        "./photo-upload-form": { default: () => null },
        "./use-photo-studio": { usePhotoStudio: () => ({ error }) },
      },
    );
    const html = render(PhotoStudio);
    assertMarkup(html, [
      /role="alert"/, /tabindex="-1"/, /data-error-code="PHOTO_ISSUE"/,
    ]);
    if (payload.tips) {
      assertMarkup(html, [
        /<p>We couldn&#x27;t frame this photo cleanly without leaving white borders along the sides\.<\/p><ul>/,
        /<li>Adjust the crop: widen or reset it to show more of both shoulders\.<\/li>/,
        /<li>Take a new photo: hold the camera farther away/,
      ]);
      assert.equal((html.match(/<li>/g) ?? []).length, 2);
    } else {
      assertMarkup(html, [/<p>Use a smaller photo\.<\/p>/], [/<ul>|<li>/]);
    }
  }
});

test("sample photo examples are an initially closed native disclosure after the warning", () => {
  assertMarkup(
    page,
    [/Skip to photo studio/, /aria-label="Passport Studio home"/],
    [/Photo guide/],
  );
  assert.ok(page.indexOf("data-studio") < page.indexOf("<aside"));
  assert.ok(page.indexOf("</aside>") < page.indexOf("<footer"));
  assertMarkup(
    guidance,
    [
      /aria-label="Before you submit"/,
      /acceptance isn&#x27;t guaranteed/,
      /<details class="examples"><summary>/,
      /View photo examples/,
      /Check your issuing authority&#x27;s current rules/,
    ],
    [/<details[^>]*\bopen\b|role="dialog"|aria-live/],
  );
  assert.ok(
    guidance.indexOf("Before you submit.") < guidance.indexOf("<details"),
  );
});

test("the clearer supplied JPG is shown inline without a popup or image link", async () => {
  const image = await readFile(
    new URL("../frontend/assets/sample_rules.jpg", import.meta.url),
  );
  assert.equal(image.readUInt16BE(0), 0xffd8);
  assertMarkup(
    guidance,
    [
      /alt="Singapore ICA photo guidelines comparing unsuitable and suitable portraits."/,
      /width="653" height="3058"/,
      /src="\/_next\/static\/media\/sample_rules.test.jpg"/,
    ],
    [/<a\b|target="_blank"|Open full-size image|role="dialog"/],
  );
});

test("the guide shows only the requested attribution above the image", () => {
  assertMarkup(
    guidance,
    [/<p>taken from: Singapore ICA\.<\/p><img/],
    [
      /Text version|textVersion|<ul\b|<li\b|Examples cover|sample reference|current rules take precedence/i,
    ],
  );
  assert.equal((guidance.match(/<details\b/g) ?? []).length, 1);
});

test("the footer retains only the contact link", () => {
  const footer = page.match(/<footer\b[\s\S]*?<\/footer>/)[0];
  assert.equal((footer.match(/<a\b/g) ?? []).length, 1);
  assertMarkup(
    footer,
    [/Contact me/, /href="https:\/\/minhao\.dev\/home"/],
    [/Passport Studio|Back to your photo|href="#/],
  );
});

const { default: PhotoWorkspace } = loadFrontendModule(
  "components/photo-studio/photo-workspace.tsx",
);
const renderTips = (country, compact = false) => {
  const html = render(PhotoWorkspace, { country, size: [35, 45] });
  return html.match(
    compact
      ? /<details class="mobile-photo-tips">[\s\S]*?<\/details>/
      : /<section class="workspace-tips"[\s\S]*?<\/section>/,
  )[0];
};

test("photo tips cover framing, selfies, lighting and headwear exceptions", () => {
  const html = renderTips("United States");
  assert.equal((html.match(/<li>/g) ?? []).length, 4);
  assertMarkup(html, [
    /above the armpits/,
    /full head, shoulders/,
    /eye level/,
    /eyes open and mouth closed/,
    /close-up selfies/,
    /even lighting/,
    /beauty filters/,
    /No headwear or sunglasses/,
    /Religious or medical coverings may be/,
  ]);
});

test("UK online applicants are advised to keep an uncropped original", () => {
  const html = renderTips("United Kingdom");
  assertMarkup(
    html,
    [
      /UK online applications/,
      /uncropped original/,
      /head, shoulders and upper body/,
    ],
    [/above the armpits/],
  );
});

test("tips are a named informational section, not an announcement or extra action", () => {
  const html = renderTips("Canada");
  assertMarkup(
    html,
    [
      /aria-labelledby="workspace-tips-title"/,
      /<h4 id="workspace-tips-title">Photo tips<\/h4>/,
    ],
    [/role="(?:status|alert)"|aria-live|<button|<a[\s>]/],
  );
});

test("mobile tips start collapsed and retain the same country-specific advice", () => {
  for (const country of ["United States", "United Kingdom"]) {
    const regular = renderTips(country);
    const compact = renderTips(country, true);
    assertMarkup(
      compact,
      [/<details class="mobile-photo-tips">/, /<summary>Photo tips/],
      [/<details[^>]*\bopen\b|\bid=|role="(?:status|alert)"/],
    );
    assert.deepEqual(
      compact.match(/<li>[\s\S]*?<\/li>/g),
      regular.match(/<li>[\s\S]*?<\/li>/g),
    );
  }
});

test("completed results order download, rules and collapsed framing help", () => {
  for (const [result, loading] of [
    ["", false],
    ["", true],
    ["blob:result", false],
  ]) {
    const html = render(PhotoWorkspace, {
      country: "Singapore",
      size: [35, 45],
      preview: "blob:original",
      result,
      loading,
      cropped: false,
    });
    assert.equal(html.includes("Not happy with the framing?"), !!result);
    assert.equal(html.includes("Photo looks off-center"), !!result);
    assert.equal(html.includes('aria-label="Framing tips"'), !!result);
    assert.equal(html.includes('class="mobile-preview-switch"'), !!result);
    assert.equal(html.includes('class="mobile-photo-tips"'), !result);
    assert.equal(html.includes('class="mobile-processing-action"'), loading);
    assert.match(html, /class="quiet-button mobile-remove"/);
    if (result) {
      assertMarkup(
        html,
        [
          /Download JPEG/,
          /<a href="blob:result" download="passport-singapore\.jpg" class="primary download">/,
          /<img src="blob:result" alt="Generated passport photo for Singapore"/,
          /class="output-details has-result"/,
          /aria-label="Framing tips" hidden=""/,
          /aria-expanded="false"/,
          /<figure[^>]*data-open="false" aria-label=/,
          /Center your face in the crop with similar space/,
          /Center your face<br\/>in the crop/,
          /Shoulders cropped too tightly/,
          /Widen or reset the crop to show more of both shoulders/,
          /cut off in the original, retake your selfie from farther away/,
          /with your whole head and shoulders in view/,
          /Use the crop tool on your original photo to center your face/,
          /with similar space on both sides/,
          /Not facing straight ahead/,
          /data-preview="result"/,
          /aria-label="Photo preview"/,
          /aria-pressed="false">Original<\/button>/,
          /aria-pressed="true">Result<\/button>/,
        ],
        [
          /<figure[^>]*role="img"/,
          /Pause|Play|motionControl/,
          /href="#photo-tips"|role="dialog"|aria-live/,
          /If the download/,
        ],
      );
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
    } else {
      assertMarkup(html, [
        /data-preview="original"/,
        /Tap photo to crop/,
        /Double-click to crop/,
      ]);
      assert.equal((html.match(/id="workspace-tips-title"/g) ?? []).length, 1);
    }
  }
});

test("framing help toggles its disclosure without playback controls", () => {
  const help = mountFrontend(helpPath);
  for (const expectedOpen of [false, true, false]) {
    const [content, button] = help.render().props.children;
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
  help.unmount();
});

test("centering loop pauses offscreen or in a hidden tab and respects reduced motion", () => {
  let intersection;
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
  const help = mountFrontend(helpPath, undefined, {
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
  });

  help.render().props.children[1].props.onClick();
  help.render((tree) => {
    tree.props.children[0].props.children[0].props.children[0].props.ref.current =
      guide;
  });
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
  help.unmount();
  assert.equal(disconnected, true);
  assert.equal(visibilityListeners.size, 0);
  assert.equal(preferenceListeners.size, 0);
});
