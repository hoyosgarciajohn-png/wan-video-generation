// Generated from contracts/bundle.schema.json by scripts/generate_types.py.
export type FrameRate = {
  numerator: number;
  denominator: number;
};
export type Settings = {
  width: number;
  height: number;
  frame_rate: FrameRate;
  seed: number;
  steps: number;
};
export type ModelProfile = {
  id: string;
  revision: string;
  checkpoint_ref: string;
  code_revision: string;
};
export type Project = {
  id: string;
  owner_id: string;
  title: string;
  kind: "music_video" | "short_film" | "cartoon";
  runtime_limit_ms: number;
};
export type Asset = {
  id: string;
  project_id: string;
  owner_id: string;
  kind: "image" | "audio" | "video";
  object_key: string;
  mime_type: string;
  bytes: number;
  sha256: string;
  duration_ms: number | null;
};
export type Shot = {
  id: string;
  project_id: string;
  scene_id: string;
  revision: number;
  prompt: string;
  reference_asset_ids: Array<string>;
  target_duration_ms: number;
  settings: Settings;
};
export type ShotSnapshot = {
  shot_id: string;
  revision: number;
  prompt: string;
  reference_asset_ids: Array<string>;
  target_duration_ms: number;
  settings: Settings;
};
export type Budget = {
  currency: "USD";
  approved_cents: number;
  reserved_cents: number;
  spent_cents: number;
};
export type Batch = {
  id: string;
  project_id: string;
  idempotency_key: string;
  execution_mode: "fixture" | "runpod";
  model_profile: ModelProfile;
  shot_snapshots: Array<ShotSnapshot>;
  budget: Budget;
  approved_at: string;
  deadline_at: string;
  state:
    | "queued"
    | "provisioning"
    | "rendering"
    | "succeeded"
    | "failed"
    | "canceled";
  cleanup_state: "pending" | "confirmed" | "failed";
  provider_resource_id: string | null;
};
export type Attempt = {
  id: string;
  project_id: string;
  batch_id: string;
  shot_id: string;
  shot_revision: number;
  worker_id: string;
  lease_id: string;
  lease_expires_at: string;
  started_at: string;
  completed_at: string | null;
  settings: Settings;
  model_profile: ModelProfile;
  state: "claimed" | "running" | "succeeded" | "failed" | "canceled";
  failure_reason: string | null;
};
export type Take = {
  id: string;
  project_id: string;
  attempt_id: string;
  shot_id: string;
  asset_id: string;
  duration_ms: number;
  width: number;
  height: number;
  frame_rate: FrameRate;
  committed_at: string;
};
export type Review = {
  id: string;
  project_id: string;
  take_id: string;
  decision: "approved" | "rejected";
  decided_by: string;
  decided_at: string;
};
export type TimelineItem = {
  take_id: string;
  source_in_ms: number;
  source_out_ms: number;
};
export type AudioItem = {
  asset_id: string;
  source_in_ms: number;
  source_out_ms: number;
  timeline_start_ms: number;
};
export type ExportProfile = {
  width: number;
  height: number;
  frame_rate: FrameRate;
  container: "mp4";
  video_codec: "h264";
  audio_codec: "aac";
};
export type Timeline = {
  id: string;
  project_id: string;
  revision: number;
  duration_ms: number;
  items: Array<TimelineItem>;
  audio: Array<AudioItem>;
  created_at: string;
};
export type Export = {
  id: string;
  project_id: string;
  timeline_id: string;
  timeline_revision: number;
  profile: ExportProfile;
  state: "queued" | "rendering" | "succeeded" | "failed" | "canceled";
  output_asset_id: string | null;
};
export type Bundle = {
  contract_version: "0.1.0";
  project: Project;
  assets: Array<Asset>;
  shots: Array<Shot>;
  batches: Array<Batch>;
  attempts: Array<Attempt>;
  takes: Array<Take>;
  reviews: Array<Review>;
  timelines: Array<Timeline>;
  exports: Array<Export>;
};
