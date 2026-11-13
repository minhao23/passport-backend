import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { createServer, request as httpRequest } from "node:http";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL("../", import.meta.url));
const maxFile = 10 * 1024 * 1024;
let server;
let frontend;
let url;
let mode = "success";
let held = [];
let upstreamCalls = 0;
let onHeld = () => {};

function reply(response, status = 200) {
  const code = status === 503 ? "SERVICE_BUSY"
    : status === 408 ? "PHOTO_ISSUE" : "PERSON_NOT_DETECTED";
  response.writeHead(status, {
    "Content-Type": status === 200 ? "image/jpeg" : "application/json",
  });
  response.end(status === 200 ? Buffer.from([0xff, 0xd8, 0xff, 0xd9])
    : JSON.stringify({ code, detail: "Test upstream response" }));
}

function form(size = 5) {
  const body = new FormData();
  body.set("country", "United States");
  body.set("file", new Blob([Buffer.alloc(size)], { type: "image/png" }), "photo.png");
  return body;
}

async function send(body = form(), options = {}) {
  const response = await fetch(url, { method: "POST", body, ...options });
  const payload = response.headers.get("content-type")?.includes("json")
    ? await response.json() : await response.arrayBuffer();
  return { response, payload };
}

before(async () => {
  // Only the upstream inference is stubbed; the built Next.js route runs unchanged.
  server = createServer(async (request, response) => {
    for await (const _ of request) { /* Drain the bounded forwarded multipart body. */ }
    upstreamCalls++;
    if (mode === "hold") {
      held.push(response);
      onHeld();
    } else {
      reply(response, mode === "busy" ? 503 : mode === "no-person" ? 422
        : mode === "timeout" ? 408 : 200);
    }
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const portReservation = createServer();
  portReservation.listen(0, "127.0.0.1");
  await once(portReservation, "listening");
  const port = portReservation.address().port;
  await new Promise(resolve => portReservation.close(resolve));
  url = `http://127.0.0.1:${port}/api/process`;

  frontend = spawn(process.execPath, [
    require.resolve("next/dist/bin/next"), "start", "--hostname", "127.0.0.1",
    "--port", String(port),
  ], {
    cwd: `${root}/frontend`,
    env: { ...process.env, BACKEND_URL: `http://127.0.0.1:${server.address().port}` },
    stdio: ["ignore", "pipe", "pipe"],
  });
  await new Promise((resolve, reject) => {
    let output = "";
    const timer = setTimeout(() => reject(new Error(`Next.js startup timed out: ${output}`)), 20_000);
    const record = chunk => {
      output += chunk.toString();
      if (output.includes("Ready in")) {
        clearTimeout(timer);
        resolve();
      }
    };
    frontend.stdout.on("data", record);
    frontend.stderr.on("data", record);
    frontend.once("error", error => { clearTimeout(timer); reject(error); });
    frontend.once("exit", code => {
      clearTimeout(timer);
      reject(new Error(`Next.js exited (${code}): ${output}`));
    });
  });
});

after(async () => {
  for (const response of held) response.destroy();
  if (frontend && frontend.exitCode === null) {
    const exit = once(frontend, "exit");
    frontend.kill("SIGTERM");
    const timer = setTimeout(() => frontend.kill("SIGKILL"), 5000);
    await exit;
    clearTimeout(timer);
  }
  if (server) {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});

test("valid upload and exact 10 MiB file reach upstream", async () => {
  for (const size of [5, maxFile]) {
    const { response } = await send(form(size));
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
});

test("oversized selected file is rejected without invoking upstream", async () => {
  const before = upstreamCalls;
  const { response, payload } = await send(form(maxFile + 1));
  assert.equal(response.status, 413);
  assert.equal(payload.code, "PHOTO_ISSUE");
  assert.equal(upstreamCalls, before);
});

test("extra multipart parts cannot bypass the aggregate cap", async () => {
  const before = upstreamCalls;
  const body = form();
  body.set("extra", new Blob([Buffer.alloc(11 * 1024 * 1024)]), "extra.bin");
  const { response } = await send(body);
  assert.equal(response.status, 413);
  assert.equal(upstreamCalls, before);
});

test("chunked body without Content-Length is still bounded", async () => {
  const before = upstreamCalls;
  const body = form(11 * 1024 * 1024);
  const request = new Request(url, { method: "POST", body });
  const { response } = await send(request.body, {
    headers: { "Content-Type": request.headers.get("content-type") },
    duplex: "half",
  });
  assert.equal(response.status, 413);
  assert.equal(upstreamCalls, before);
});

async function unfinishedUpload(payload) {
  return new Promise((resolve, reject) => {
    const request = httpRequest(url, {
      method: "POST",
      headers: { "Content-Type": "multipart/form-data; boundary=boundary" },
    }, response => {
      const chunks = [];
      const socket = response.socket;
      response.on("data", chunk => chunks.push(chunk));
      response.on("error", reject);
      response.on("end", () => {
        const result = {
          status: response.statusCode,
          headers: response.headers,
          payload: JSON.parse(Buffer.concat(chunks).toString()),
        };
        if (socket.destroyed) resolve(result);
        else socket.once("close", () => resolve(result));
      });
    });
    request.on("error", reject);
    request.setTimeout(65_000, () => request.destroy(new Error("No upload error response")));
    // Deliberately never end the body: rejection must not wait for its remainder.
    request.write(payload);
  });
}

test("unfinished oversized upload receives JSON before connection closes", { timeout: 15_000 }, async () => {
  const before = upstreamCalls;
  const result = await unfinishedUpload(Buffer.alloc(11 * 1024 * 1024));
  assert.equal(result.status, 413);
  assert.equal(result.payload.code, "PHOTO_ISSUE");
  assert.equal(upstreamCalls, before);
  assert.equal((await send()).response.status, 200);
});

test("stalled upload receives timeout JSON and releases admission", { timeout: 70_000 }, async () => {
  const before = upstreamCalls;
  const result = await unfinishedUpload("--boundary\r\n");
  assert.equal(result.status, 408);
  assert.equal(result.payload.code, "PHOTO_ISSUE");
  assert.equal(upstreamCalls, before);
  assert.equal((await send()).response.status, 200);
});

test("duplicate files and malformed multipart return input errors", async () => {
  const body = form();
  body.append("file", new Blob(["other"], { type: "image/png" }), "other.png");
  assert.equal((await send(body)).response.status, 400);
  const malformed = await send("not multipart", {
    headers: { "Content-Type": "multipart/form-data; boundary=missing" },
  });
  assert.equal(malformed.response.status, 400);
  assert.equal(malformed.payload.code, "PHOTO_ISSUE");
});

test("backend busy and no-person errors remain distinct", async () => {
  try {
    mode = "busy";
    const busy = await send();
    assert.equal(busy.response.status, 503);
    assert.equal(busy.payload.code, "SERVICE_BUSY");
    assert.equal(busy.response.headers.get("retry-after"), "10");
    mode = "no-person";
    const noPerson = await send();
    assert.equal(noPerson.response.status, 422);
    assert.equal(noPerson.payload.code, "PERSON_NOT_DETECTED");
    assert.equal(noPerson.payload.title, "No person detected");
    assert.equal(noPerson.payload.detail, "Try another photo with your whole head and shoulders clearly visible.");
    mode = "timeout";
    const timeout = await send();
    assert.equal(timeout.response.status, 408);
    assert.equal(timeout.payload.code, "PHOTO_ISSUE");
  } finally {
    mode = "success";
  }
});

test("frontend rejects a fifth active request and recovers its slots", { timeout: 15_000 }, async () => {
  mode = "hold";
  held = [];
  const ready = new Promise(resolve => { onHeld = () => { if (held.length === 4) resolve(); }; });
  const requests = Array.from({ length: 4 }, () => send());
  try {
    await ready;
    const before = upstreamCalls;
    const busy = await send();
    assert.equal(busy.response.status, 503);
    assert.equal(busy.payload.code, "SERVICE_BUSY");
    assert.equal(upstreamCalls, before);
  } finally {
    mode = "success";
    for (const response of held) reply(response);
    await Promise.all(requests);
  }
  assert.equal((await send()).response.status, 200);
});

test("proxy keeps waiting photo requests open until upstream completes them", { timeout: 15_000 }, async () => {
  mode = "hold";
  held = [];
  const finished = [];
  const firstReady = new Promise(resolve => { onHeld = resolve; });
  const first = send().then(result => { finished.push("first"); return result; });
  let second;
  try {
    await firstReady;
    const secondReady = new Promise(resolve => { onHeld = resolve; });
    second = send().then(result => { finished.push("second"); return result; });
    await secondReady;
    assert.deepEqual(finished, []);
    reply(held[0]);
    assert.equal((await first).response.status, 200);
    assert.deepEqual(finished, ["first"]);
    reply(held[1]);
    assert.equal((await second).response.status, 200);
    assert.deepEqual(finished, ["first", "second"]);
  } finally {
    mode = "success";
    for (const response of held) {
      if (!response.writableEnded) reply(response);
    }
    await Promise.allSettled([first, second]);
  }
});

test("client cancellation closes upstream and permits another request", { timeout: 15_000 }, async () => {
  mode = "hold";
  held = [];
  const ready = new Promise(resolve => { onHeld = resolve; });
  const controller = new AbortController();
  const pending = send(form(), { signal: controller.signal });
  const rejected = assert.rejects(pending, error => error.name === "AbortError");
  try {
    await ready;
    const closed = once(held[0], "close");
    controller.abort();
    await rejected;
    await closed;
  } finally {
    mode = "success";
    for (const response of held) response.destroy();
  }
  assert.equal((await send()).response.status, 200);
});
