import { useEffect, useRef, useState } from "react";
import { SignIn } from "./SignIn";
import { StudioClient } from "./api";
import { type Workspace, errorMessage, StudioError } from "./model";
import modelCatalog from "../../../services/providers/music_models.json";

export type DirectorShot = {
  start_ms: number;
  end_ms: number;
  action: string;
  camera: string;
  singing: boolean;
};
export type Brief = {
  song_id: string | null;
  reference_ids: string[];
  primary_id: string | null;
  start_ms: number;
  end_ms: number;
  direction: string;
  identity: string;
  lyrics: string;
  location: string;
  performance: string;
  model_id: string;
  resolution: string;
  aspect_ratio: string;
  budget_cents: number;
  target_minutes: number;
  shots: DirectorShot[];
};
export const emptyBrief = (): Brief => ({
  song_id: null,
  reference_ids: [],
  primary_id: null,
  start_ms: 0,
  end_ms: 60000,
  direction:
    "A cinematic daylight beach concert. The lead singer sings while dancing with a large, smiling dance ensemble. Cut between coordinated choreography, fans, the live band and the performer. Ocean waves roll, palm trees sway and clothing moves naturally in the breeze.",
  identity:
    "Same face and proportions as the original photos. Backward black cap in every shot. Black suit with open neckline. No invented hair or changes in age.",
  lyrics: "",
  location:
    "One beach stage · daylight · ocean behind stage · consistent sun direction",
  performance:
    "Singer dances and sings. Dancers smile and perform the choreography; they sing only during confirmed group-vocal sections.",
  model_id: "ltx-fast",
  resolution: "1080p",
  aspect_ratio: "16:9",
  budget_cents: 2000,
  target_minutes: 10,
  shots: [],
});
export function draftShots(start: number, end: number): DirectorShot[] {
  const cameras = [
    "Crane descends from ocean toward full stage",
    "Low tracking camera follows full-body choreography",
    "Moving medium shot of lead singer with ensemble",
    "Lateral stage camera reveals band and dancers",
    "Crowd-level camera tracks fans clapping",
    "Wide orbit around singer and dance formation",
    "Tight moving portrait; cap and face clearly visible",
    "Stage-side tracking shot follows diagonal dance line",
    "Aerial pullback shows beach, stage and audience",
    "Low wide camera pushes toward synchronized dance",
    "Moving fan close-up with stage in background",
    "Crane rises from full ensemble to concert-wide finale",
  ];
  const actions = [
    "Full ensemble dances in formation; establish the same stage and crowd.",
    "Singer and dancers step together, pivot and advance one row.",
    "Singer continues the phrase while dancers mirror the step-touch pattern.",
    "Band plays; the singer and ensemble continue in the background.",
    "Fans clap and dance; no invented solo singing.",
    "Dancers open a semicircle around the singer, then return to formation.",
    "Singer performs while moving shoulders and stepping to the beat.",
    "Ensemble moves diagonally together; singer remains the visual lead.",
    "Continuous choreography on the same stage; natural surf and wind.",
    "Singer and dancers execute a coordinated side-step and arm sweep.",
    "Fans cheer and move with the rhythm; keep stage geography consistent.",
    "Ensemble completes a shared dance phrase; finish on the concert energy.",
  ];
  const count = Math.max(1, Math.ceil((end - start) / 5000));
  return Array.from({ length: count }, (_, i) => ({
    start_ms: start + Math.round(((end - start) * i) / count),
    end_ms: start + Math.round(((end - start) * (i + 1)) / count),
    action: actions[i % actions.length],
    camera: cameras[i % cameras.length],
    singing: ![3, 4, 8, 10].includes(i % 12),
  }));
}
const time = (ms: number) =>
  `${Math.floor(ms / 60000)
    .toString()
    .padStart(
      2,
      "0",
    )}:${Math.floor(ms / 1000) % 60 < 10 ? "0" : ""}${Math.floor(ms / 1000) % 60}`;
async function call<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const r = await fetch("/v1/studio/" + path, {
    method,
    credentials: "same-origin",
    headers:
      method === "GET"
        ? {}
        : { "Content-Type": "application/json", "X-WAN-Request": "studio" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!r.ok) throw new StudioError(r.status);
  return r.json() as Promise<T>;
}
type Review = {
  issues: string[];
  estimate_cents: number | null;
  estimate_note: string;
  endpoint: string;
};
export function Director() {
  const api = useRef(new StudioClient()).current;
  const [workspace, setWorkspace] = useState<Workspace>();
  const [owner, setOwner] = useState("");
  const [pid, setPid] = useState("");
  const [title, setTitle] = useState("Beach Concert · 60-second test");
  const [brief, setBrief] = useState<Brief>(emptyBrief);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [page, setPage] = useState("Brief");
  const [review, setReview] = useState<Review>();
  const [configured, setConfigured] = useState(false);
  const [progress, setProgress] = useState("");
  const audio = useRef<HTMLAudioElement>(null);
  const [playhead, setPlayhead] = useState(0);
  const project = workspace?.projects.find((p) => p.bundle.project.id === pid);
  const model = modelCatalog.find((m) => m.id === brief.model_id)!;
  const assets = project?.bundle.assets ?? [];
  const images = assets.filter((a) => a.mime_type.startsWith("image/"));
  const songs = assets.filter((a) => a.mime_type.startsWith("audio/"));
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function load() {
    const session = await api.session();
    setOwner(session.owner_id);
    setWorkspace(await api.load());
    const c = await call<{ configured: boolean }>("director/models");
    setConfigured(c.configured);
  }
  useEffect(() => {
    void load().catch(e => { if (!(e instanceof StudioError && e.code === 401)) setError(errorMessage(e)); });
  }, []);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function change(partial: Partial<Brief>) {
    setBrief((b) => ({ ...b, ...partial }));
    setDirty(true);
    setReview(undefined);
    setMessage("");
  }
  async function select(id: string) {
    const saved = await call<{ revision: number; brief: Brief | null }>(
      `projects/${id}/director`,
    );
    setPid(id);
    setRevision(saved.revision);
    setBrief(saved.brief ?? emptyBrief());
    setDirty(false);
    setReview(undefined);
    setPage("Brief");
  }
  async function create() {
    const w = await api.create(title, "music_video", workspace!.revision);
    setWorkspace(w);
    const p = w.projects.find(
      (x) =>
        !workspace?.projects.some(
          (old) => old.bundle.project.id === x.bundle.project.id,
        ),
    )!;
    await select(p.bundle.project.id);
    setMessage("Project created. Add your song and original reference photos.");
  }
  async function save() {
    if (!pid) throw new StudioError(422);
    const r = await call<{ revision: number }>(
      `projects/${pid}/director`,
      "PUT",
      { expected_revision: revision, brief },
    );
    setRevision(r.revision);
    setDirty(false);
    setMessage("Saved to your project.");
  }
  async function upload(files: FileList | null) {
    if (!files || !pid || !workspace) return;
    let w = workspace;
    let next = { ...brief, reference_ids: [...brief.reference_ids] };
    for (const file of Array.from(files)) {
      const before = new Set(
        w.projects
          .find((p) => p.bundle.project.id === pid)!
          .bundle.assets.map((a) => a.id),
      );
      w = await api.uploadFile(
        {
          kind: "upload-file",
          projectId: pid,
          file,
          expected_revision: w.revision,
          idempotency_key: crypto.randomUUID(),
        },
        (p) =>
          setProgress(
            `${file.name} · ${Math.round((p.received / p.total) * 100)}%`,
          ),
      );
      setWorkspace(w);
      const a = w.projects
        .find((p) => p.bundle.project.id === pid)!
        .bundle.assets.find((a) => !before.has(a.id));
      if (a) {
        if (a.mime_type.startsWith("image/")) {
          next.reference_ids.push(a.id);
          next.primary_id ??= a.id;
        } else {
          next.song_id = a.id;
          next.start_ms = 0;
          next.end_ms = Math.min(60000, a.duration_ms ?? 60000);
          next.shots = [];
        }
      }
      setBrief({ ...next });
      setDirty(true);
    }
    setProgress("");
    setMessage("Upload complete. Save the brief to keep these selections.");
  }
  async function analyze() {
    if (dirty) await save();
    setReview(
      await call<Review>(`projects/${pid}/director/review`, "POST", {}),
    );
    setPage("Preview");
  }
  const rate = (model.cents_per_second as Record<string, number | null>)[
    brief.resolution
  ];
  const estimate =
    rate === null
      ? null
      : Math.ceil(((brief.end_ms - brief.start_ms) / 1000) * rate) / 100;
  const currentShot = brief.shots.find(
    (s) => playhead >= s.start_ms && playhead < s.end_ms,
  );
  return (
    <div className="director">
      <header className="d-header">
        <a className="d-brand" href="/#director">
          <span className="d-logo">W</span>
          <span>
            WAN STUDIO<small>Music Video Director</small>
          </span>
        </a>
        <span className="d-badge">DIRECTOR · FOUNDATION</span>
        <a
          href="/#studio"
          onClick={(e) => {
            if (dirty) {
              e.preventDefault();
              setError("Save the draft before switching studios.");
            } else {
              e.preventDefault();
              location.assign("/#studio");
              location.reload();
            }
          }}
        >
          Classic studio ↗
        </a>
      </header>
      <main className="d-main">
        <div className="d-title">
          <div>
            <p className="d-eyebrow">
              YOUR SONG. YOUR CHARACTER. YOUR DIRECTION.
            </p>
            <h1>Make every shot intentional.</h1>
            <p>
              Plan a complete performance before spending on video generation.
            </p>
          </div>
          <span className="d-state">
            {dirty
              ? "● Unsaved changes"
              : pid
                ? "✓ Saved project"
                : "○ New project"}
          </span>
        </div>
        {!owner ? (
          <SignIn onSignedIn={load} />
        ) : (
          <>
            <section className="d-project">
              <label>
                Project
                <select
                  value={pid}
                  disabled={busy || dirty}
                  onChange={(e) => void act(() => select(e.target.value))}
                >
                  <option value="" disabled>
                    Select a project
                  </option>
                  {workspace?.projects.map((p) => (
                    <option
                      key={p.bundle.project.id}
                      value={p.bundle.project.id}
                    >
                      {p.bundle.project.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                New project name
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <button
                disabled={busy || dirty || !title.trim()}
                onClick={() => void act(create)}
              >
                ＋ Create project
              </button>
              <button
                disabled={busy || dirty}
                onClick={() =>
                  void act(async () => {
                    await api.logout();
                    setOwner("");
                    setWorkspace(undefined);
                    setPid("");
                  })
                }
              >
                Sign out
              </button>
            </section>
            <nav className="d-steps" aria-label="Production steps">
              {["Brief", "Storyboard", "Preview", "Render", "Compare"].map(
                (s, i) => (
                  <button
                    key={s}
                    className={page === s ? "active" : ""}
                    disabled={!pid || busy}
                    onClick={() => setPage(s)}
                  >
                    <b>{i + 1}</b>
                    {s}
                    {i > 2 && <small>Next phase</small>}
                  </button>
                ),
              )}
            </nav>
            <fieldset className="d-fields" disabled={!pid || busy}>
              {page === "Brief" && (
                <div className="d-grid">
                  <div className="d-stack">
                    <section className="d-card">
                      <div className="d-card-title">
                        <h2>
                          <span>01</span> Song & timing
                        </h2>
                        <span className="d-badge">ORIGINAL AUDIO</span>
                      </div>
                      <label className="d-drop">
                        ♫ <strong>Upload your song</strong>
                        <span>WAV, MP3 or M4A · up to 128 MB</span>
                        <input
                          aria-label="Upload song"
                          type="file"
                          accept="audio/wav,audio/mpeg,audio/mp4,.wav,.mp3,.m4a"
                          disabled={!pid || busy}
                          onChange={(e) => {
                            const f = e.target.files;
                            void act(() => upload(f));
                            e.target.value = "";
                          }}
                        />
                      </label>
                      <label>
                        Song
                        <select
                          value={brief.song_id ?? ""}
                          onChange={(e) =>
                            change({ song_id: e.target.value, shots: [] })
                          }
                        >
                          <option value="">Select uploaded audio</option>
                          {songs.map((a) => (
                            <option key={a.id} value={a.id}>
                              {project?.assetNames[a.id] ?? a.id}
                            </option>
                          ))}
                        </select>
                      </label>
                      {brief.song_id && (
                        <audio controls src={project?.media[brief.song_id]} />
                      )}
                      <div className="d-row">
                        <label>
                          Start · seconds
                          <input
                            type="number"
                            min="0"
                            step="1"
                            value={brief.start_ms / 1000}
                            onChange={(e) =>
                              change({
                                start_ms: Number(e.target.value) * 1000,
                                shots: [],
                              })
                            }
                          />
                        </label>
                        <label>
                          End · seconds
                          <input
                            type="number"
                            min="1"
                            step="1"
                            value={brief.end_ms / 1000}
                            onChange={(e) =>
                              change({
                                end_ms: Number(e.target.value) * 1000,
                                shots: [],
                              })
                            }
                          />
                        </label>
                        <div className="d-duration">
                          <strong>
                            {time(Math.max(0, brief.end_ms - brief.start_ms))}
                          </strong>
                          <small>selected duration</small>
                        </div>
                      </div>
                    </section>
                    <section className="d-card">
                      <div className="d-card-title">
                        <h2>
                          <span>02</span> Main character
                        </h2>
                        <span className="d-badge">ORIGINAL REFERENCES</span>
                      </div>
                      <p className="d-muted">
                        Select the primary face reference. Keep the original
                        photos available for every shot review.
                      </p>
                      <div className="d-photos">
                        {images.map((a) => (
                          <button
                            key={a.id}
                            className={
                              brief.primary_id === a.id ? "selected" : ""
                            }
                            onClick={() =>
                              change({
                                primary_id: a.id,
                                reference_ids: [
                                  ...new Set([...brief.reference_ids, a.id]),
                                ],
                              })
                            }
                          >
                            <img
                              src={project?.media[a.id]}
                              alt={
                                project?.assetNames[a.id] ??
                                "Character reference"
                              }
                            />
                            <span>
                              {brief.primary_id === a.id
                                ? "✓ Primary face"
                                : "Use as primary"}
                            </span>
                          </button>
                        ))}
                        <label className="d-add">
                          ＋<span>Add photos</span>
                          <input
                            aria-label="Upload character photos"
                            type="file"
                            multiple
                            accept="image/png,image/jpeg,image/webp"
                            disabled={!pid || busy}
                            onChange={(e) => {
                              const f = e.target.files;
                              void act(() => upload(f));
                              e.target.value = "";
                            }}
                          />
                        </label>
                      </div>
                      <small>
                        PNG, JPG or WebP · each image up to 1 MB in the current
                        uploader · maximum 10 selected references.
                      </small>
                      <label>
                        Character continuity requirements
                        <textarea
                          rows={3}
                          value={brief.identity}
                          onChange={(e) => change({ identity: e.target.value })}
                        />
                      </label>
                      <p className="d-note">
                        These are review requirements. No model can promise 100%
                        identity fidelity.
                      </p>
                    </section>
                    <section className="d-card">
                      <h2>
                        <span>03</span> Video direction
                      </h2>
                      <label>
                        Your concept
                        <textarea
                          rows={5}
                          value={brief.direction}
                          onChange={(e) =>
                            change({ direction: e.target.value })
                          }
                        />
                      </label>
                      <div className="d-tags">
                        <span>Daylight concert</span>
                        <span>Moving cameras</span>
                        <span>Live choreography</span>
                      </div>
                      <label>
                        Location, light & environment
                        <textarea
                          rows={2}
                          value={brief.location}
                          onChange={(e) => change({ location: e.target.value })}
                        />
                      </label>
                      <label>
                        Singer, dancers & group vocals
                        <textarea
                          rows={3}
                          value={brief.performance}
                          onChange={(e) =>
                            change({ performance: e.target.value })
                          }
                        />
                      </label>
                      <label>
                        Lyrics & vocal cues{" "}
                        <small>Optional · timing must be reviewed</small>
                        <textarea
                          rows={3}
                          placeholder="Paste lyrics and mark where the chorus or group vocals begin…"
                          value={brief.lyrics}
                          onChange={(e) => change({ lyrics: e.target.value })}
                        />
                      </label>
                    </section>
                  </div>
                  <aside className="d-stack">
                    <section className="d-card">
                      <h2>Model & output</h2>
                      <label>
                        Exact model
                        <select
                          value={brief.model_id}
                          onChange={(e) => {
                            const m = modelCatalog.find(
                              (x) => x.id === e.target.value,
                            )!;
                            change({
                              model_id: m.id,
                              resolution: m.resolutions[0],
                            });
                          }}
                        >
                          {modelCatalog.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="d-model">
                        <strong>{model.role}</strong>
                        <p>{model.audio}</p>
                        <small>
                          {model.min_seconds}–{model.max_seconds}s per clip in
                          this integration
                        </small>
                        <code>{model.endpoint}</code>
                        <a href={model.source} target="_blank" rel="noreferrer">
                          Official endpoint documentation ↗
                        </a>
                      </div>
                      <div className="d-row">
                        <label>
                          Format
                          <select
                            value={brief.aspect_ratio}
                            onChange={(e) =>
                              change({ aspect_ratio: e.target.value })
                            }
                          >
                            <option>16:9</option>
                            <option>9:16</option>
                          </select>
                        </label>
                        <label>
                          Resolution
                          <select
                            value={brief.resolution}
                            onChange={(e) =>
                              change({ resolution: e.target.value })
                            }
                          >
                            {model.resolutions.map((r) => (
                              <option key={r}>{r}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <div className="d-connection">
                        <b>Provider: fal</b>
                        <span>
                          {configured
                            ? "Credential configured · not live-verified"
                            : "Server API key required"}
                        </span>
                        <small>
                          Adapter implemented. Paid rendering is not enabled in
                          this foundation release.
                        </small>
                      </div>
                    </section>
                    <section className="d-card">
                      <h2>Creative review checklist</h2>
                      <ul className="d-rules">
                        <li>Same face, cap and wardrobe</li>
                        <li>Singer dances with the ensemble</li>
                        <li>Dancers sing only at group vocals</li>
                        <li>Wide, full-body, close and aerial coverage</li>
                        <li>Moving cameras, waves, palms and clothing</li>
                        <li>Fresh action; no repeated filler clips</li>
                      </ul>
                      <p className="d-note">
                        Applied as direction and review criteria, not automatic
                        guarantees.
                      </p>
                    </section>
                    <section className="d-card">
                      <h2>Budget & speed target</h2>
                      <div className="d-row">
                        <label>
                          Budget · USD
                          <input
                            type="number"
                            min="0"
                            max="1000"
                            step="0.01"
                            value={brief.budget_cents / 100}
                            onChange={(e) =>
                              change({
                                budget_cents: Math.round(
                                  Number(e.target.value) * 100,
                                ),
                              })
                            }
                          />
                        </label>
                        <label>
                          Target · minutes
                          <input
                            type="number"
                            min="1"
                            max="120"
                            value={brief.target_minutes}
                            onChange={(e) =>
                              change({ target_minutes: Number(e.target.value) })
                            }
                          />
                        </label>
                      </div>
                      <div className="d-estimate">
                        <span>Indicative video cost</span>
                        <strong>
                          {estimate === null
                            ? "Quote required"
                            : "$" + Math.max(0, estimate).toFixed(2)}
                        </strong>
                      </div>
                      <p className="d-muted">
                        Excludes retries, image creation, editing and taxes.
                        Rates checked Nov 18, 2026. Speed is a benchmark target,
                        not a promise.
                      </p>
                      <p className="d-note">
                        ✓ Review storyboard and character images before
                        rendering.
                      </p>
                    </section>
                  </aside>
                </div>
              )}
              {page === "Storyboard" && (
                <section className="d-card">
                  <div className="d-card-title">
                    <div>
                      <h2>Direct the minute, shot by shot.</h2>
                      <p>
                        Editable pacing draft. This is not audio analysis; align
                        actions and group vocals with your song.
                      </p>
                    </div>
                    <button
                      disabled={busy || brief.end_ms <= brief.start_ms}
                      onClick={() =>
                        change({
                          shots: draftShots(brief.start_ms, brief.end_ms),
                        })
                      }
                    >
                      {brief.shots.length
                        ? "Rebuild pacing draft"
                        : "Build pacing draft"}
                    </button>
                  </div>
                  {brief.shots.length === 0 ? (
                    <p>No shots yet. Build a draft, then direct each scene.</p>
                  ) : (
                    <div className="d-shot-list">
                      {brief.shots.map((shot, i) => (
                        <article className="d-shot" key={i}>
                          <div className="d-shot-number">
                            {String(i + 1).padStart(2, "0")}
                            <small>
                              {time(shot.start_ms)}–{time(shot.end_ms)}
                            </small>
                            {i < brief.shots.length - 1 && (
                              <label>
                                Cut at · seconds
                                <input
                                  type="number"
                                  step="1"
                                  value={shot.end_ms / 1000}
                                  onChange={(e) => {
                                    const cut = Number(e.target.value) * 1000;
                                    change({
                                      shots: brief.shots.map((s, j) =>
                                        j === i
                                          ? { ...s, end_ms: cut }
                                          : j === i + 1
                                            ? { ...s, start_ms: cut }
                                            : s,
                                      ),
                                    });
                                  }}
                                />
                              </label>
                            )}
                          </div>
                          <label>
                            Action & choreography
                            <textarea
                              rows={3}
                              value={shot.action}
                              onChange={(e) =>
                                change({
                                  shots: brief.shots.map((s, j) =>
                                    j === i
                                      ? { ...s, action: e.target.value }
                                      : s,
                                  ),
                                })
                              }
                            />
                          </label>
                          <label>
                            Camera movement
                            <textarea
                              rows={2}
                              value={shot.camera}
                              onChange={(e) =>
                                change({
                                  shots: brief.shots.map((s, j) =>
                                    j === i
                                      ? { ...s, camera: e.target.value }
                                      : s,
                                  ),
                                })
                              }
                            />
                            <span className="d-check">
                              <input
                                type="checkbox"
                                checked={shot.singing}
                                onChange={(e) =>
                                  change({
                                    shots: brief.shots.map((s, j) =>
                                      j === i
                                        ? { ...s, singing: e.target.checked }
                                        : s,
                                    ),
                                  })
                                }
                              />{" "}
                              Visible lead singing
                            </span>
                          </label>
                        </article>
                      ))}
                    </div>
                  )}
                  <button
                    className="d-primary"
                    disabled={busy || !brief.shots.length}
                    onClick={() => void act(analyze)}
                  >
                    Save & check storyboard →
                  </button>
                </section>
              )}
              {page === "Preview" && (
                <section className="d-card">
                  <h2>Review before rendering</h2>
                  <p>
                    Audio-timed direction preview. No generated footage or
                    approved scene images yet.
                  </p>
                  {brief.song_id && (
                    <audio
                      ref={audio}
                      controls
                      src={project?.media[brief.song_id]}
                      onLoadedMetadata={() => {
                        if (audio.current)
                          audio.current.currentTime = brief.start_ms / 1000;
                      }}
                      onTimeUpdate={() => {
                        const a = audio.current!;
                        setPlayhead(a.currentTime * 1000);
                        if (a.currentTime * 1000 >= brief.end_ms) a.pause();
                      }}
                    />
                  )}
                  <div className="d-preview">
                    <span className="d-badge">
                      {time(playhead)} · DIRECTION CARD
                    </span>
                    <h3>
                      {currentShot?.camera ?? "Play the selected song segment"}
                    </h3>
                    <p>
                      {currentShot?.action ??
                        "Your shot directions will follow playback."}
                    </p>
                    <small>Camera instructions are not generated images.</small>
                  </div>
                  <button disabled={busy} onClick={() => void act(analyze)}>
                    Validate saved storyboard
                  </button>
                  {review && (
                    <div className="d-review">
                      <strong>
                        Video estimate:{" "}
                        {review.estimate_cents === null
                          ? "Quote required"
                          : "$" + (review.estimate_cents / 100).toFixed(2)}
                      </strong>
                      <p>{review.estimate_note}</p>
                      <code>{review.endpoint}</code>
                      {review.issues.length ? (
                        <ul>
                          {review.issues.map((x) => (
                            <li key={x}>{x}</li>
                          ))}
                        </ul>
                      ) : (
                        <p>
                          Timing and model checks passed. Scene-image and
                          creative acceptance still required.
                        </p>
                      )}
                    </div>
                  )}
                </section>
              )}
              {page === "Render" && (
                <section className="d-card">
                  <h2>Rendering connection prepared</h2>
                  <p>
                    The server adapters support exact endpoint requests, queue
                    status and result retrieval. This first release does not
                    submit paid jobs.
                  </p>
                  <ul>
                    <li>
                      Provider credential:{" "}
                      {configured
                        ? "configured, not verified"
                        : "missing on server"}
                    </li>
                    <li>
                      Next integration: durable cost reservation and queue
                      admission
                    </li>
                    <li>
                      Next integration: trimmed audio and approved scene images
                      per shot
                    </li>
                    <li>
                      Next integration: retained MP4 results and final assembly
                    </li>
                  </ul>
                  <button disabled>Render approved shots · not enabled</button>
                </section>
              )}
              {page === "Compare" && (
                <section className="d-card">
                  <h2>Compare completed videos</h2>
                  <p>
                    No hosted renders have been created in this workspace flow.
                  </p>
                  <div className="d-compare">
                    <span>Character fidelity</span>
                    <span>Lip-sync</span>
                    <span>Choreography</span>
                    <span>Camera motion</span>
                    <span>Continuity</span>
                    <span>Cost & elapsed time</span>
                  </div>
                  <p>
                    Each future result will retain its model, provider, exact
                    prompt, timing and downloadable MP4.
                  </p>
                </section>
              )}
            </fieldset>
            <footer className="d-footer">
              <span>
                {pid
                  ? `${brief.shots.length} planned shots · ${time(brief.end_ms - brief.start_ms)} selected`
                  : "Create or select a project to begin"}
              </span>
              <div>
                <button
                  disabled={!pid || busy || !dirty}
                  onClick={() => void act(save)}
                >
                  Save draft
                </button>
                <button
                  className="d-primary"
                  disabled={!pid || busy || brief.end_ms <= brief.start_ms}
                  onClick={() => {
                    if (!brief.shots.length)
                      change({
                        shots: draftShots(brief.start_ms, brief.end_ms),
                      });
                    setPage("Storyboard");
                  }}
                >
                  Build storyboard →
                </button>
              </div>
            </footer>
          </>
        )}
        {(error || message || busy || progress) && (
          <div
            className={`d-feedback ${error ? "error" : ""}`}
            role={error ? "alert" : "status"}
          >
            {error || progress || (busy ? "Working…" : message)}
          </div>
        )}
      </main>
    </div>
  );
}
