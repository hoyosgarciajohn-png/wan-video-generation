import { test } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import {
  initialWorkspace,
  createProject,
  projectFor,
  saveShot,
  approveBatch,
  advanceBatch,
  reviewTake,
  loadWorkspace,
  saveWorkspace,
  errorMessage,
  StudioError,
  STORAGE_KEY,
} from "../src/model";

function storage(): Storage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
    removeItem: (key) => {
      values.delete(key);
    },
    clear: () => values.clear(),
    key: (index) => [...values.keys()][index] ?? null,
    get length() {
      return values.size;
    },
  };
}
function checkContract(bundle: unknown) {
  const directory = mkdtempSync(join(tmpdir(), "wan-b03-"));
  try {
    const path = join(directory, "project.json");
    writeFileSync(path, JSON.stringify(bundle));
    execFileSync(process.env.WAN_PYTHON ?? resolve("../../.venv/bin/python"), [
      resolve("../../scripts/validate_contract.py"),
      path,
    ]);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

test("shot edits and regeneration preserve accepted take, frozen batch and historical timeline", () => {
  const p = initialWorkspace().projects[0];
  const original = structuredClone(p.bundle);
  const batch = approveBatch(p, ["shot-1"], "repeatable-key");
  saveShot(
    p,
    { ...p.bundle.shots[0], prompt: "A fictional orange light" },
    "shot-1",
    1,
  );
  assert.equal(p.bundle.shots[0].revision, 2);
  assert.equal(p.shotHistory[0].prompt, original.shots[0].prompt);
  assert.equal(
    p.bundle.batches.at(-1)!.shot_snapshots[0].prompt,
    original.shots[0].prompt,
  );
  advanceBatch(p, batch);
  advanceBatch(p, batch);
  const next = p.bundle.takes.at(-1)!;
  assert.equal(p.selectedTakes["shot-1"], "take-1");
  assert.deepEqual(p.bundle.timelines, original.timelines);
  reviewTake(p, next.id, "approved");
  assert.equal(p.selectedTakes["shot-1"], next.id);
  assert.deepEqual(p.bundle.takes[0], original.takes[0]);
  assert.deepEqual(p.bundle.timelines, original.timelines);
  checkContract(p.bundle);
});
test("same batch key is idempotent and rejects changed input", () => {
  const p = initialWorkspace().projects[0];
  const batch = approveBatch(p, ["shot-1"], "key");
  assert.equal(approveBatch(p, ["shot-1"], "key"), batch);
  saveShot(
    p,
    { ...p.bundle.shots[0], prompt: "Different prompt" },
    "shot-1",
    1,
  );
  assert.throws(
    () => approveBatch(p, ["shot-1"], "key"),
    (e) => e instanceof StudioError && e.code === 409,
  );
  assert.throws(
    () => saveShot(p, { ...p.bundle.shots[0] }, "shot-1", 1),
    StudioError,
  );
});
test("partial failure, cancellation and new batch retain committed takes", () => {
  const p = initialWorkspace().projects[0];
  const second = saveShot(p, {
    ...p.bundle.shots[0],
    prompt: "Fictional second shot",
  });
  const batch = approveBatch(p, ["shot-1", second], "partial");
  advanceBatch(p, batch);
  advanceBatch(p, batch);
  advanceBatch(p, batch, true);
  assert.equal(p.bundle.batches.at(-1)!.state, "failed");
  assert.equal(p.bundle.takes.length, 2);
  const retry = approveBatch(p, [second], "retry");
  advanceBatch(p, retry);
  advanceBatch(p, retry);
  assert.equal(p.bundle.takes.length, 3);
  advanceBatch(p, retry);
  assert.equal(p.bundle.takes.length, 3);
  const cancel = approveBatch(p, [second], "cancel");
  p.bundle.batches.find((b) => b.id === cancel)!.state = "canceled";
  advanceBatch(p, cancel);
  assert.equal(p.bundle.takes.length, 3);
  checkContract(p.bundle);
});
test("all project kinds enforce runtime caps and isolate project records", () => {
  const state = initialWorkspace();
  for (const kind of ["music_video", "short_film", "cartoon"] as const) {
    const pid = createProject(state, "Fictional " + kind, kind);
    const p = projectFor(state, pid);
    const limit = kind === "music_video" ? 360000 : 1800000;
    assert.equal(p.bundle.project.runtime_limit_ms, limit);
    const shot = {
      ...state.projects[0].bundle.shots[0],
      scene_id: p.scenes[0].id,
      target_duration_ms: limit,
    };
    saveShot(p, shot);
    assert.throws(
      () => saveShot(p, { ...shot, target_duration_ms: 1 }),
      StudioError,
    );
    assert.throws(
      () => saveShot(p, { ...shot, reference_asset_ids: ["asset-audio"] }),
      StudioError,
    );
    checkContract(p.bundle);
  }
  assert.throws(
    () => projectFor(state, "fictional-project", "another-owner"),
    (e) => e instanceof StudioError && e.code === 404,
  );
  assert.throws(
    () => projectFor(state, "fictional-project", ""),
    (e) => e instanceof StudioError && e.code === 401,
  );
});
test("reusable image references are frozen and retained across shot revisions", () => {
  const p = initialWorkspace().projects[0];
  p.bundle.assets.push({
    id: "image-1",
    project_id: p.bundle.project.id,
    owner_id: p.bundle.project.owner_id,
    kind: "image",
    object_key: "fictional-project/references/image.png",
    mime_type: "image/png",
    bytes: 100,
    sha256: "a".repeat(64),
    duration_ms: null,
  });
  saveShot(
    p,
    { ...p.bundle.shots[0], reference_asset_ids: ["image-1"] },
    "shot-1",
    1,
  );
  approveBatch(p, ["shot-1"], "refs");
  saveShot(p, { ...p.bundle.shots[0], reference_asset_ids: [] }, "shot-1", 2);
  assert.deepEqual(
    p.bundle.batches.at(-1)!.shot_snapshots[0].reference_asset_ids,
    ["image-1"],
  );
  checkContract(p.bundle);
});
test("reload restores approvals and rejects a stale browser write", () => {
  const store = storage();
  const state = initialWorkspace();
  saveWorkspace(store, state, 0);
  const restored = loadWorkspace(store);
  assert.deepEqual(restored, state);
  assert.throws(
    () => saveWorkspace(store, initialWorkspace(), 0),
    (e) => e instanceof StudioError && e.code === 409,
  );
  assert.deepEqual(loadWorkspace(store), restored);
});
test("storage failure leaves the last saved state recoverable", () => {
  const store = storage();
  const state = initialWorkspace();
  saveWorkspace(store, state, 0);
  const before = store.getItem(STORAGE_KEY);
  store.setItem = () => {
    throw new Error("quota");
  };
  const next = structuredClone(state);
  assert.throws(
    () => saveWorkspace(store, next, 1),
    (e) => e instanceof StudioError && e.code === 507,
  );
  assert.equal(store.getItem(STORAGE_KEY), before);
  assert.equal(next.revision, 1);
});
test("removed or malformed storage rejects stale writes without restoring old data", () => {
  const store = storage();
  const state = initialWorkspace();
  saveWorkspace(store, state, 0);
  for (const value of [null, "broken", "null"]) {
    if (value === null) store.clear();
    else store.setItem(STORAGE_KEY, value);
    assert.throws(
      () => saveWorkspace(store, state, 1),
      (e) => e instanceof StudioError && e.code === 409,
    );
    assert.equal(store.getItem(STORAGE_KEY), value);
    assert.equal(state.revision, 1);
  }
});
test("unavailable storage reads have the same recoverable error as writes", () => {
  const store = storage();
  store.getItem = () => {
    throw new Error("storage denied");
  };
  assert.throws(
    () => saveWorkspace(store, initialWorkspace(), 0),
    (e) => e instanceof StudioError && e.code === 507,
  );
});
test("ownership and service errors use safe messages", () => {
  for (const code of [401, 404, 409, 422, 503])
    assert.ok(errorMessage(new StudioError(code)).length > 10);
  assert.equal(
    errorMessage(new Error("secret-private-provider-details")),
    "The service is temporarily unavailable. Try again.",
  );
  const store = storage();
  store.setItem(STORAGE_KEY, "broken");
  assert.throws(() => loadWorkspace(store), StudioError);
  const state = initialWorkspace();
  state.projects[0].bundle.project.owner_id = "other-owner";
  store.setItem(STORAGE_KEY, JSON.stringify(state));
  assert.throws(() => loadWorkspace(store), StudioError);
});
