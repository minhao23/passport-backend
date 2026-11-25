import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { loadFrontendESModule } from "./frontend-test-utils.mjs";

const { default: config } = await loadFrontendESModule("next.config.ts");
const require = createRequire(import.meta.url);
const {
  blockCrossSiteDEV,
} = require("next/dist/server/lib/router-utils/block-cross-site-dev.js");

function checkOrigin(origin) {
  const response = {
    statusCode: 200,
    body: null,
    end(body) {
      this.body = body;
    },
  };
  const blocked = blockCrossSiteDEV(
    { url: "/_next/hmr", headers: { origin } },
    response,
    config.allowedDevOrigins,
  );
  return { blocked, response };
}

test("both local development addresses can reach Next development resources", () => {
  assert.deepEqual(config.allowedDevOrigins, ["127.0.0.1"]);
  for (const origin of ["http://localhost:3000", "http://127.0.0.1:3000"]) {
    const { blocked, response } = checkOrigin(origin);
    assert.equal(blocked, false);
    assert.equal(response.body, null);
  }
});

test("allowing the loopback address does not allow unrelated or opaque origins", () => {
  for (const origin of [
    "http://untrusted.example:3000",
    "http://127.0.0.1.attacker.example:3000",
    "null",
  ]) {
    const { blocked, response } = checkOrigin(origin);
    assert.equal(blocked, true);
    assert.equal(response.statusCode, 403);
    assert.equal(response.body, "Unauthorized");
  }
});
