import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

test("bundle validation works when runtime string compilation is forbidden", () => {
  const path = new URL(
    "../src/generated/bundle-validator.cjs",
    import.meta.url,
  );
  const context = vm.createContext(
    { module: { exports: {} }, require: createRequire(path) },
    { codeGeneration: { strings: false, wasm: false } },
  );
  vm.runInContext(readFileSync(path, "utf8"), context);
  const validate = context.module.exports;
  const fixture = JSON.parse(
    readFileSync(new URL("../../../fixtures/project.json", import.meta.url)),
  );
  assert.equal(validate(fixture), true);
  const invalid = structuredClone(fixture);
  invalid.project.kind = "invalid-kind";
  assert.equal(validate(invalid), false);
  const invalidFormat = structuredClone(fixture);
  invalidFormat.assets[0].sha256 = "not-a-sha256";
  assert.equal(validate(invalidFormat), false);
});
