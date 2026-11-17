// web/app.js against the committed web/merkmal.js and web/merkmal.wasm, in
// Node, with a stub DOM: the demo's own call() wrapper, not a copy of it.
//
// ccall passes each JS string to C NUL-terminated, so "p\0junk" used to be
// answered as "p" and a pasted model registered up to the NUL. call() now
// refuses such input before it reaches C. This checks that every operation
// the demo exposes refuses it, and that ordinary input still goes through.
//
// Needs only Node: the module is the deployed build, so no emcc.
//
// Usage: node tests/wasm/app_nul_test.cjs

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const web = path.join(__dirname, "..", "..", "web");
const createMerkmal = require(path.join(web, "merkmal.js"));

// Absorbs any DOM access: every property is another stub, every call returns
// one, and assignments are accepted. Enough for app.js's init to run.
function stub() {
  const target = function () {};
  return new Proxy(target, {
    get: (_t, key) => (key === Symbol.toPrimitive ? () => "" : key === "then" ? undefined : stub()),
    set: () => true,
    apply: () => stub(),
  });
}

async function main() {
  const mk = await createMerkmal();
  const context = vm.createContext({
    document: stub(),
    window: stub(),
    fetch: () => Promise.resolve({ ok: false }),
    createMerkmal: () => Promise.resolve(mk),
    console,
  });
  // In the order index.html loads them: app.js reads guide-content.js.
  for (const script of ["guide-content.js", "app.js"]) {
    vm.runInContext(fs.readFileSync(path.join(web, script), "utf8"), context, {
      filename: "web/" + script,
    });
  }
  // Let init() finish: it awaits createMerkmal() and then lists systems.
  await new Promise((resolve) => setImmediate(resolve));

  const call = context.call;
  const model =
    "@model toy\n@type categorical\n@geometry clements-hume\n" +
    "grapheme X consonant voiceless bilabial stop\n";
  let failures = 0;
  const check = (ok, label, result) => {
    if (!ok) {
      failures++;
      console.error("FAIL: " + label + ": " + JSON.stringify(result));
    }
  };
  const refused = (r) => r.ok === false && r.error === "invalid argument" && /NUL/.test(r.detail);

  // Each operation app.js exposes, with a NUL in each string position.
  const cases = [
    ["merkmal_grapheme_features", ["string", "string"], ["descriptive", "p\u0000junk"]],
    ["merkmal_grapheme_features", ["string", "string"], ["descr\u0000iptive", "p"]],
    ["merkmal_segment_distance", ["string", "string", "string"], ["descriptive", "p", "p\u0000b"]],
    ["merkmal_tokenize", ["string", "string", "number", "number"], ["descriptive", "ta\u0000pa", 0, 0]],
    ["merkmal_distance_matrix", ["string", "string"], ["descriptive", "p,b\u0000,t"]],
    ["merkmal_register_model", ["string"], [model + "\u0000@this line is junk\n"]],
  ];
  for (const [name, types, args] of cases) {
    const r = call(name, types, ...args);
    check(refused(r), name + " refuses a NUL", r);
  }

  // Without a NUL, the same calls reach the library as before.
  const features = call("merkmal_grapheme_features", ["string", "string"], "descriptive", "p");
  check(features.ok === true && features.features.includes("bilabial"), "features of p", features);
  const distance = call(
    "merkmal_segment_distance", ["string", "string", "string"], "descriptive", "p", "b");
  check(distance.ok === true && distance.distance > 0, "distance p/b", distance);
  const tokens = call(
    "merkmal_tokenize", ["string", "string", "number", "number"], "descriptive", "tapa", 0, 0);
  check(tokens.ok === true && tokens.segments.length === 4, "tokenize tapa", tokens);
  const registered = call("merkmal_register_model", ["string"], model);
  check(registered.ok === true && registered.name === "toy", "register a clean model", registered);

  if (failures === 0) {
    console.log("app_nul: ok (" + cases.length + " refusals, 4 ordinary calls)");
  }
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
