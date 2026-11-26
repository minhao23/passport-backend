import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const root = fileURLToPath(new URL("../frontend/", import.meta.url));
const require = createRequire(import.meta.url);

export async function loadFrontendESModule(filename) {
  const { outputText } = ts.transpileModule(
    readFileSync(resolve(root, filename), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
      },
    },
  );
  return import(
    `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
  );
}

export function mockGlobal(t, name, value) {
  const previous = Object.getOwnPropertyDescriptor(globalThis, name);
  Object.defineProperty(globalThis, name, { configurable: true, value });
  t.after(() => {
    if (previous) Object.defineProperty(globalThis, name, previous);
    else delete globalThis[name];
  });
}

export function assertMarkup(html, contains = [], excludes = []) {
  for (const pattern of contains) assert.match(html, pattern);
  for (const pattern of excludes) assert.doesNotMatch(html, pattern);
}

export function loadFrontendModule(filename, stubs = {}, globals = {}) {
  const cache = new Map();
  function load(path) {
    if (!extname(path)) {
      path = [".ts", ".tsx"].map((ext) => path + ext).find(existsSync);
    }
    if (!path) throw new Error(`Frontend module not found: ${filename}`);
    if (cache.has(path)) return cache.get(path);
    const exports = {};
    cache.set(path, exports);
    const { outputText } = ts.transpileModule(readFileSync(path, "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
      },
    });
    runInNewContext(outputText, {
      exports,
      ...globals,
      require: (name) => {
        if (name in stubs) return stubs[name];
        if (name.endsWith(".css")) {
          return { default: new Proxy({}, { get: (_, key) => key }) };
        }
        if (name.startsWith("@/")) return load(resolve(root, name.slice(2)));
        if (name.startsWith(".")) return load(resolve(dirname(path), name));
        return require(name);
      },
    });
    return exports;
  }
  return load(resolve(root, filename));
}

// Simulate state/effect cleanup; actual DOM behavior is checked in the browser.
export function mountFrontend(
  filename,
  invoke = (module) => module.default(),
  globals = {},
  stubs = {},
) {
  const slots = [];
  let index = 0;
  let dirty = false;
  let effects = [];
  const react = {
    useState(initial) {
      const slot = (slots[index++] ??= { value: initial });
      return [
        slot.value,
        (update) => {
          const next =
            typeof update === "function" ? update(slot.value) : update;
          if (!Object.is(next, slot.value)) {
            slot.value = next;
            dirty = true;
          }
        },
      ];
    },
    useRef(initial) {
      return (slots[index++] ??= { current: initial });
    },
    useId() {
      return (slots[index++] ??= { value: `test-id-${index}` }).value;
    },
    useEffect(effect, deps) {
      const slot = (slots[index++] ??= {});
      if (
        !slot.deps ||
        deps.some((value, i) => !Object.is(value, slot.deps[i]))
      ) {
        slot.deps = deps;
        effects.push(() => {
          slot.cleanup?.();
          slot.cleanup = effect();
        });
      }
    },
  };
  const module = loadFrontendModule(filename, { react, ...stubs }, globals);
  return {
    render(commit = () => {}) {
      let value;
      do {
        dirty = false;
        index = 0;
        effects = [];
        value = invoke(module);
        commit(value);
        for (const effect of effects) effect();
      } while (dirty);
      return value;
    },
    unmount() {
      for (const slot of slots) {
        slot.cleanup?.();
        slot.cleanup = undefined;
      }
    },
  };
}
