import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import schema from "../../../contracts/bundle.schema.json";
import fixture from "../../../fixtures/project.json";
import type { Asset, Batch, Bundle, Project, Shot, Take } from "./contract";

const ajv = new Ajv2020({ strict: false });
addFormats(ajv);
const validBundle = ajv.compile<Bundle>(schema);

export const OWNER = "fictional-owner";
export const STORAGE_KEY = "wan-studio.fixture.0.1.0";
export const caps = {
  music_video: 300000,
  short_film: 1800000,
  cartoon: 1800000,
};
const copy = <T>(value: T): T => structuredClone(value);
const id = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;
const now = () => new Date().toISOString();
export class StudioError extends Error {
  constructor(public code: number) {
    super(String(code));
  }
}
export function errorMessage(error: unknown): string {
  const code = error instanceof StudioError ? error.code : 503;
  return (
    (
      {
        401: "Sign in again to access this project.",
        404: "This project or item is unavailable.",
        410: "This upload expired or was canceled. Select the file again to start a new upload.",
        409: "A newer version is available. Reload before saving your changes.",
        422: "Check the fields and project duration. Use references from this project.",
        507: "Browser storage is full or unavailable. Your last saved version is retained.",
      } as Record<number, string>
    )[code] ?? "The service is temporarily unavailable. Try again."
  );
}
export interface StudioProject {
  bundle: Bundle;
  scenes: { id: string; title: string }[];
  shotHistory: Shot[];
  selectedTakes: Record<string, string>;
  assetNames: Record<string, string>;
  media: Record<string, string>;
  script: string;
}
export interface Workspace {
  version: 1;
  revision: number;
  projects: StudioProject[];
}
export function initialWorkspace(): Workspace {
  return {
    version: 1,
    revision: 0,
    projects: [
      {
        bundle: copy(fixture as Bundle),
        scenes: [{ id: "scene-1", title: "Opening scene" }],
        shotHistory: [],
        selectedTakes: { "shot-1": "take-1" },
        assetNames: {
          "asset-audio": "Synthetic soundtrack",
          "asset-video": "Blue studio fixture",
        },
        media: {
          "asset-audio": "/media/audio.wav",
          "asset-video": "/media/clip.mp4",
        },
        script: "",
      },
    ],
  };
}
export function projectFor(
  state: Workspace,
  projectId: string,
  owner = OWNER,
): StudioProject {
  if (!owner) throw new StudioError(401);
  const p = state.projects.find(
    (p) =>
      p.bundle.project.id === projectId && p.bundle.project.owner_id === owner,
  );
  if (!p) throw new StudioError(404);
  return p;
}
export function requireItem<T extends { id: string }>(
  items: T[],
  itemId: string,
): T {
  const item = items.find((i) => i.id === itemId);
  if (!item) throw new StudioError(404);
  return item;
}
export function createProject(
  state: Workspace,
  title: string,
  kind: Project["kind"],
): string {
  if (!title.trim() || !Object.hasOwn(caps, kind)) throw new StudioError(422);
  const base = initialWorkspace().projects[0];
  const projectId = id("project");
  const assets = base.bundle.assets.map((a) => ({
    ...a,
    id: id("asset"),
    project_id: projectId,
    object_key: `${projectId}/${a.object_key}`,
  }));
  state.projects.push({
    bundle: {
      contract_version: "0.1.0",
      project: {
        id: projectId,
        title: title.trim(),
        kind,
        owner_id: OWNER,
        runtime_limit_ms: caps[kind],
      },
      assets,
      shots: [],
      batches: [],
      attempts: [],
      takes: [],
      reviews: [],
      timelines: [],
      exports: [],
    },
    scenes: [{ id: id("scene"), title: "Opening scene" }],
    shotHistory: [],
    selectedTakes: {},
    script: "",
    media: Object.fromEntries(
      assets.map((a) => [
        a.id,
        a.kind === "audio" ? "/media/audio.wav" : "/media/clip.mp4",
      ]),
    ),
    assetNames: Object.fromEntries(
      assets.map((a) => [
        a.id,
        a.kind === "audio" ? "Synthetic soundtrack" : "Blue studio fixture",
      ]),
    ),
  });
  return projectId;
}
export function addScene(p: StudioProject, title: string): void {
  if (!title.trim()) throw new StudioError(422);
  p.scenes.push({ id: id("scene"), title: title.trim() });
}
export function saveShot(
  p: StudioProject,
  input: Pick<
    Shot,
    | "scene_id"
    | "prompt"
    | "reference_asset_ids"
    | "target_duration_ms"
    | "settings"
  >,
  shotId?: string,
  expectedRevision?: number,
): string {
  requireItem(p.scenes, input.scene_id);
  const previous = shotId ? requireItem(p.bundle.shots, shotId) : undefined;
  if (previous && expectedRevision !== previous.revision)
    throw new StudioError(409);
  const duration = input.target_duration_ms;
  const total =
    p.bundle.shots
      .filter((s) => s.id !== shotId)
      .reduce((sum, s) => sum + s.target_duration_ms, 0) + duration;
  if (
    !input.prompt.trim() ||
    !Number.isSafeInteger(duration) ||
    duration < 1 ||
    total > p.bundle.project.runtime_limit_ms ||
    !Number.isSafeInteger(input.settings.seed) ||
    input.settings.seed < 0 ||
    input.settings.width !== 320 ||
    input.settings.height !== 180 ||
    input.settings.steps !== 1 ||
    input.settings.frame_rate.numerator !== 24 ||
    input.settings.frame_rate.denominator !== 1
  )
    throw new StudioError(422);
  for (const assetId of input.reference_asset_ids) {
    if (requireItem(p.bundle.assets, assetId).kind !== "image")
      throw new StudioError(422);
  }
  const shot: Shot = {
    ...copy(input),
    prompt: input.prompt.trim(),
    id: shotId ?? id("shot"),
    project_id: p.bundle.project.id,
    revision: (previous?.revision ?? 0) + 1,
  };
  if (previous) {
    p.shotHistory.push(copy(previous));
    p.bundle.shots[p.bundle.shots.indexOf(previous)] = shot;
  } else p.bundle.shots.push(shot);
  return shot.id;
}
export function approveBatch(
  p: StudioProject,
  shotIds: string[],
  key: string,
): string {
  if (
    !key.trim() ||
    !shotIds.length ||
    new Set(shotIds).size !== shotIds.length
  )
    throw new StudioError(422);
  const snapshots = shotIds.map((shotId) => {
    const {
      id: shot_id,
      project_id: _project,
      scene_id: _scene,
      ...rest
    } = requireItem(p.bundle.shots, shotId);
    return { shot_id, ...copy(rest) };
  });
  const existing = p.bundle.batches.find((b) => b.idempotency_key === key);
  if (existing) {
    if (JSON.stringify(existing.shot_snapshots) !== JSON.stringify(snapshots))
      throw new StudioError(409);
    return existing.id;
  }
  const batchId = id("batch");
  p.bundle.batches.push({
    id: batchId,
    project_id: p.bundle.project.id,
    idempotency_key: key,
    execution_mode: "fixture",
    model_profile: copy((fixture as Bundle).batches[0].model_profile),
    shot_snapshots: snapshots,
    budget: {
      currency: "USD",
      approved_cents: 0,
      reserved_cents: 0,
      spent_cents: 0,
    },
    approved_at: now(),
    deadline_at: new Date(Date.now() + 600000).toISOString(),
    state: "queued",
    cleanup_state: "confirmed",
    provider_resource_id: null,
  });
  return batchId;
}
export function advanceBatch(
  p: StudioProject,
  batchId: string,
  fail = false,
): void {
  const b = requireItem(p.bundle.batches, batchId);
  if (["succeeded", "failed", "canceled"].includes(b.state)) return;
  if (Date.now() >= Date.parse(b.deadline_at)) {
    b.state = "failed";
    return;
  }
  if (b.state === "queued") {
    b.state = "rendering";
    return;
  }
  const snapshot = b.shot_snapshots.find(
    (s) =>
      !p.bundle.attempts.some(
        (a) =>
          a.batch_id === b.id &&
          a.shot_id === s.shot_id &&
          a.state === "succeeded",
      ),
  );
  if (!snapshot) {
    b.state = "succeeded";
    return;
  }
  const time = now();
  const attemptId = id("attempt");
  p.bundle.attempts.push({
    id: attemptId,
    project_id: p.bundle.project.id,
    batch_id: b.id,
    shot_id: snapshot.shot_id,
    shot_revision: snapshot.revision,
    worker_id: "fictional-worker",
    lease_id: id("lease"),
    lease_expires_at: new Date(Date.now() + 120000).toISOString(),
    started_at: time,
    completed_at: time,
    settings: copy(snapshot.settings),
    model_profile: copy(b.model_profile),
    state: fail ? "failed" : "succeeded",
    failure_reason: fail ? "FIXTURE_RENDER_FAILED" : null,
  });
  if (fail) {
    b.state = "failed";
    return;
  }
  const source = (fixture as Bundle).assets.find(
    (a) => a.id === "asset-video",
  )!;
  const asset: Asset = {
    ...copy(source),
    id: id("asset"),
    project_id: p.bundle.project.id,
    owner_id: p.bundle.project.owner_id,
    object_key: `${p.bundle.project.id}/takes/${attemptId}.mp4`,
  };
  p.bundle.assets.push(asset);
  p.media[asset.id] = "/media/clip.mp4";
  p.bundle.takes.push({
    id: id("take"),
    project_id: p.bundle.project.id,
    attempt_id: attemptId,
    shot_id: snapshot.shot_id,
    asset_id: asset.id,
    duration_ms: 2000,
    width: snapshot.settings.width,
    height: snapshot.settings.height,
    frame_rate: copy(snapshot.settings.frame_rate),
    committed_at: time,
  });
  const count = p.bundle.attempts.filter(
    (a) => a.batch_id === b.id && a.state === "succeeded",
  ).length;
  if (count === b.shot_snapshots.length) b.state = "succeeded";
}
export function reviewTake(
  p: StudioProject,
  takeId: string,
  decision: "approved" | "rejected",
): void {
  const take = requireItem(p.bundle.takes, takeId);
  if (decision === "rejected" && p.selectedTakes[take.shot_id] === take.id)
    throw new StudioError(409);
  p.bundle.reviews.push({
    id: id("review"),
    project_id: p.bundle.project.id,
    take_id: takeId,
    decision,
    decided_by: OWNER,
    decided_at: now(),
  });
  if (decision === "approved") p.selectedTakes[take.shot_id] = takeId;
}
export function takeDecision(p: StudioProject, take: Take): string {
  return (
    p.bundle.reviews.filter((r) => r.take_id === take.id).at(-1)?.decision ??
    "Needs review"
  );
}
export function batchProgress(p: StudioProject, b: Batch): number {
  return p.bundle.attempts.filter(
    (a) => a.batch_id === b.id && a.state === "succeeded",
  ).length;
}
export function saveWorkspace(
  storage: Storage,
  next: Workspace,
  expected: number,
): void {
  let current: string | null;
  try {
    current = storage.getItem(STORAGE_KEY);
  } catch {
    throw new StudioError(507);
  }
  // A missing record is only valid on the initial save. Another tab may
  // have cleared it before its storage event reaches this editor.
  if (current === null) {
    if (expected !== 0) throw new StudioError(409);
  } else {
    try {
      if ((JSON.parse(current) as Workspace).revision !== expected)
        throw new StudioError(409);
    } catch {
      throw new StudioError(409);
    }
  }
  const revision = expected + 1;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify({ ...next, revision }));
  } catch {
    throw new StudioError(507);
  }
  next.revision = revision;
}
function validProject(p: StudioProject): boolean {
  if (
    !validBundle(p.bundle) ||
    p.bundle.project.owner_id !== OWNER ||
    p.bundle.project.runtime_limit_ms !== caps[p.bundle.project.kind] ||
    !Array.isArray(p.scenes) ||
    !p.scenes.length ||
    p.scenes.some(
      (s) =>
        typeof s.id !== "string" ||
        typeof s.title !== "string" ||
        !s.title.trim(),
    ) ||
    !Array.isArray(p.shotHistory) ||
    typeof p.script !== "string" ||
    !p.media ||
    !p.assetNames ||
    !p.selectedTakes
  )
    return false;
  const records = [
    p.bundle.assets,
    p.bundle.shots,
    p.bundle.batches,
    p.bundle.attempts,
    p.bundle.takes,
    p.bundle.reviews,
    p.bundle.timelines,
    p.bundle.exports,
  ];
  if (
    records.some((items) =>
      items.some((item) => item.project_id !== p.bundle.project.id),
    )
  )
    return false;
  if (
    p.bundle.assets.some(
      (a) => a.owner_id !== OWNER || typeof p.media[a.id] !== "string",
    )
  )
    return false;
  if (
    p.bundle.shots.some(
      (s) => !p.scenes.some((scene) => scene.id === s.scene_id),
    )
  )
    return false;
  return Object.entries(p.selectedTakes).every(([shotId, takeId]) => {
    const take = p.bundle.takes.find(
      (t) => t.id === takeId && t.shot_id === shotId,
    );
    return take && takeDecision(p, take) === "approved";
  });
}

export function loadWorkspace(storage: Storage): Workspace {
  let raw: string | null;
  try {
    raw = storage.getItem(STORAGE_KEY);
  } catch {
    throw new StudioError(507);
  }
  if (!raw) return initialWorkspace();
  try {
    const data = JSON.parse(raw) as Workspace;
    if (
      data.version !== 1 ||
      !Number.isSafeInteger(data.revision) ||
      data.revision < 0 ||
      !Array.isArray(data.projects) ||
      !data.projects.length ||
      data.projects.some((p) => !validProject(p))
    )
      throw new StudioError(409);
    return data;
  } catch {
    throw new StudioError(409);
  }
}
