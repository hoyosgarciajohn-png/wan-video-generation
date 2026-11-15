import { ShotEditor } from "./ShotEditor";
import { References } from "./References";
import { useEffect, useRef, useState } from "react";
import type { Project } from "./contract";
import {
  STORAGE_KEY,
  StudioError,
  addScene,
  advanceBatch,
  approveBatch,
  batchProgress,
  caps,
  createProject,
  errorMessage,
  initialWorkspace,
  loadWorkspace,
  projectFor,
  requireItem,
  reviewTake,
  saveShot,
  saveWorkspace,
  takeDecision,
  type StudioProject,
  type Workspace,
} from "./model";

const labels = {
  music_video: "Music video",
  short_film: "Short film",
  cartoon: "Cartoon",
};
const seconds = (ms: number) => `${(ms / 1000).toLocaleString()}s`;
type Edit = (draft: StudioProject) => void;

export function App() {
  const [startup] = useState(() => {
    try {
      return { state: loadWorkspace(localStorage), error: "" };
    } catch (e) {
      return { state: initialWorkspace(), error: errorMessage(e) };
    }
  });
  const [state, setState] = useState(startup.state);
  const current = useRef(state);
  current.current = state;
  const [projectId, setProjectId] = useState(
    state.projects[0].bundle.project.id,
  );
  const [tab, setTab] = useState("Storyboard");
  const [shotId, setShotId] = useState<string | undefined>(
    state.projects[0].bundle.shots[0]?.id,
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState(startup.error);
  const [notice, setNotice] = useState("Fictional rehearsal ready.");
  const [locked, setLocked] = useState(Boolean(startup.error));
  const [newProject, setNewProject] = useState(false);
  const [batchKey, setBatchKey] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const project = projectFor(state, projectId);
  const activeShot = project.bundle.shots.find((s) => s.id === shotId);
  const total = project.bundle.shots.reduce(
    (sum, s) => sum + s.target_duration_ms,
    0,
  );
  useEffect(() => {
    const listener = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY || event.key === null) {
        setLocked(true);
        setError(errorMessage(new StudioError(409)));
      }
    };
    addEventListener("storage", listener);
    return () => removeEventListener("storage", listener);
  }, []);
  function commit(change: (next: Workspace) => void, message: string) {
    if (locked) return false;
    try {
      const next = structuredClone(current.current);
      change(next);
      saveWorkspace(localStorage, next, current.current.revision);
      current.current = next;
      setState(next);
      setError("");
      setNotice(message);
      return true;
    } catch (e) {
      setError(errorMessage(e));
      if (e instanceof StudioError && e.code === 409) setLocked(true);
      return false;
    }
  }
  function edit(change: Edit, message = "Saved in this browser.") {
    commit((next) => change(projectFor(next, projectId)), message);
  }
  function switchProject(value: string) {
    setProjectId(value);
    setShotId(undefined);
    setSelected([]);
    setTab("Storyboard");
    if (!locked) setError("");
  }
  function moveShot(id: string, direction: number) {
    edit((p) => {
      const index = p.bundle.shots.findIndex((s) => s.id === id);
      const siblings = p.bundle.shots.filter(
        (shot) => shot.scene_id === p.bundle.shots[index].scene_id,
      );
      const sibling =
        siblings[siblings.findIndex((shot) => shot.id === id) + direction];
      const target = sibling ? p.bundle.shots.indexOf(sibling) : -1;
      if (target >= 0 && target < p.bundle.shots.length) {
        [p.bundle.shots[index], p.bundle.shots[target]] = [
          p.bundle.shots[target],
          p.bundle.shots[index],
        ];
      }
    }, "Storyboard order saved.");
  }
  function downloadBundle() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(project.bundle, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${projectId}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <>
      <a href="#workspace" className="skip">
        Skip to workspace
      </a>
      <header>
        <a className="brand" href="#workspace" aria-label="WAN Studio home">
          WAN <span>STUDIO</span>
        </a>
        <span className="fixture">Fictional rehearsal · $0 GPU cost</span>
        <button onClick={() => setNewProject(!newProject)}>New project</button>
      </header>
      <div className="shell">
        <aside className="sidebar">
          <label>
            Project
            <select
              value={projectId}
              onChange={(e) => switchProject(e.target.value)}
            >
              {state.projects.map((p) => (
                <option key={p.bundle.project.id} value={p.bundle.project.id}>
                  {p.bundle.project.title}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">
            {labels[project.bundle.project.kind]} ·{" "}
            {project.bundle.project.runtime_limit_ms / 60000} min limit
          </p>
          <nav aria-label="Studio sections">
            {["Storyboard", "References", "Render batches", "Take review"].map(
              (name) => (
                <button
                  key={name}
                  aria-current={tab === name ? "page" : undefined}
                  onClick={() => setTab(name)}
                >
                  {name}
                </button>
              ),
            )}
          </nav>
          <div className="project-stats">
            <strong>{project.bundle.shots.length}</strong> shots{" "}
            <span>{seconds(total)} planned</span>
            <strong>{Object.keys(project.selectedTakes).length}</strong>{" "}
            accepted takes
          </div>
          <button className="quiet" onClick={downloadBundle}>
            Download contract bundle
          </button>
          <p className="muted small">
            Fixture outputs use the supplied two-second blue clip. Your planned
            shot durations remain editable.
          </p>
        </aside>
        <main id="workspace" tabIndex={-1}>
          <div className="page-title">
            <div>
              <p className="eyebrow">{labels[project.bundle.project.kind]}</p>
              <h1>{project.bundle.project.title}</h1>
            </div>
            <span className="tag">Contract 0.1.0</span>
          </div>
          <div role="status" className="notice">
            {notice}
          </div>
          {error && (
            <div role="alert" className="error">
              {error}{" "}
              {locked && (
                <button onClick={() => location.reload()}>
                  Reload saved version
                </button>
              )}
            </div>
          )}
          <fieldset disabled={locked} className="workspace-fields">
            {newProject && (
              <form
                className="panel create"
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  let created = "";
                  if (
                    commit((next) => {
                      created = createProject(
                        next,
                        String(data.get("title")),
                        String(data.get("kind")) as Project["kind"],
                      );
                    }, "Project created.")
                  ) {
                    switchProject(created);
                    setNewProject(false);
                  }
                }}
              >
                <h2>Create project</h2>
                <label>
                  Project title
                  <input name="title" required autoFocus />
                </label>
                <label>
                  Project type
                  <select name="kind">
                    {Object.entries(labels).map(([key, label]) => (
                      <option value={key} key={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="primary">Create project</button>
                <button type="button" onClick={() => setNewProject(false)}>
                  Cancel
                </button>
              </form>
            )}
            <details className="project-settings">
              <summary>Project settings</summary>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  edit((p) => {
                    const title = String(data.get("title")).trim();
                    const kind = String(data.get("kind")) as Project["kind"];
                    if (
                      !title ||
                      total > caps[kind] ||
                      p.bundle.timelines.some((t) => t.duration_ms > caps[kind])
                    )
                      throw new StudioError(422);
                    p.bundle.project.title = title;
                    p.bundle.project.kind = kind;
                    p.bundle.project.runtime_limit_ms = caps[kind];
                  }, "Project settings saved.");
                }}
              >
                <label>
                  Rename project
                  <input
                    key={projectId + project.bundle.project.title}
                    name="title"
                    defaultValue={project.bundle.project.title}
                    required
                  />
                </label>
                <label>
                  Format
                  <select
                    key={projectId + project.bundle.project.kind}
                    name="kind"
                    defaultValue={project.bundle.project.kind}
                  >
                    {Object.entries(labels).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <button>Save project</button>
              </form>
            </details>
            {tab === "Storyboard" && (
              <div className="story-layout">
                <section aria-labelledby="board-heading">
                  <div className="toolbar">
                    <h2 id="board-heading">Storyboard</h2>
                    <button onClick={() => setShotId(undefined)}>
                      New shot
                    </button>
                  </div>
                  <form
                    className="scene-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = e.currentTarget;
                      const title = String(new FormData(form).get("scene"));
                      if (
                        commit(
                          (next) =>
                            addScene(projectFor(next, projectId), title),
                          "Scene added.",
                        )
                      )
                        form.reset();
                    }}
                  >
                    <label>
                      New scene
                      <input name="scene" required placeholder="Scene name" />
                    </label>
                    <button>Add scene</button>
                  </form>
                  {project.scenes.map((scene) => (
                    <section className="scene" key={scene.id}>
                      <label className="scene-name">
                        Scene name
                        <input
                          aria-label={`Rename ${scene.title}`}
                          defaultValue={scene.title}
                          onBlur={(e) =>
                            edit((p) => {
                              if (!e.target.value.trim())
                                throw new StudioError(422);
                              requireItem(p.scenes, scene.id).title =
                                e.target.value;
                            }, "Scene name saved.")
                          }
                        />
                      </label>
                      {project.bundle.shots
                        .filter((s) => s.scene_id === scene.id)
                        .map((s) => (
                          <article
                            className={`shot ${shotId === s.id ? "active" : ""}`}
                            key={s.id}
                          >
                            <div className="shot-head">
                              <label className="check">
                                <input
                                  type="checkbox"
                                  aria-label={`Select ${s.prompt}`}
                                  checked={selected.includes(s.id)}
                                  onChange={(e) =>
                                    setSelected(
                                      e.target.checked
                                        ? [...selected, s.id]
                                        : selected.filter((id) => id !== s.id),
                                    )
                                  }
                                />
                                Batch
                              </label>
                              <span
                                className={
                                  project.selectedTakes[s.id]
                                    ? "tag accepted"
                                    : "tag"
                                }
                              >
                                {project.selectedTakes[s.id]
                                  ? "Accepted take"
                                  : "Draft"}
                              </span>
                            </div>
                            <button
                              className="shot-open"
                              onClick={() => setShotId(s.id)}
                            >
                              <strong>{s.prompt}</strong>
                              <span>
                                {seconds(s.target_duration_ms)} · Revision{" "}
                                {s.revision} · {s.reference_asset_ids.length}{" "}
                                references
                              </span>
                            </button>
                            <div className="shot-actions">
                              <button
                                aria-label={`Move ${s.prompt} earlier`}
                                disabled={
                                  project.bundle.shots.filter(
                                    (shot) => shot.scene_id === scene.id,
                                  )[0].id === s.id
                                }
                                onClick={() => moveShot(s.id, -1)}
                              >
                                Move earlier
                              </button>
                              <button
                                aria-label={`Move ${s.prompt} later`}
                                disabled={
                                  project.bundle.shots
                                    .filter(
                                      (shot) => shot.scene_id === scene.id,
                                    )
                                    .at(-1)?.id === s.id
                                }
                                onClick={() => moveShot(s.id, 1)}
                              >
                                Move later
                              </button>
                              <button
                                onClick={() => {
                                  setShotId(s.id);
                                  setTab("Take review");
                                }}
                              >
                                Review takes
                              </button>
                            </div>
                          </article>
                        ))}
                      {!project.bundle.shots.some(
                        (s) => s.scene_id === scene.id,
                      ) && (
                        <p className="empty">
                          Add the first shot to this scene.
                        </p>
                      )}
                    </section>
                  ))}
                  <div className="batch-bar">
                    <span>{selected.length} shots selected</span>
                    <button
                      className="primary"
                      disabled={!selected.length}
                      onClick={() => {
                        setBatchKey(crypto.randomUUID());
                        dialog.current?.showModal();
                      }}
                    >
                      Review render batch
                    </button>
                  </div>
                </section>
                <ShotEditor
                  key={`${projectId}-${shotId}-${activeShot?.revision}`}
                  project={project}
                  shot={activeShot}
                  onSave={(input, old) => {
                    let saved = "";
                    if (
                      commit((next) => {
                        saved = saveShot(
                          projectFor(next, projectId),
                          input,
                          old?.id,
                          old?.revision,
                        );
                      }, "Shot revision saved. Accepted takes are retained.")
                    )
                      setShotId(saved);
                  }}
                />
              </div>
            )}
            {tab === "References" && (
              <References
                key={projectId}
                project={project}
                edit={edit}
                report={(e) => setError(errorMessage(e))}
              />
            )}
            {tab === "Render batches" && (
              <section>
                <h2>Render batches</h2>
                <p className="muted">
                  Advance each fictional batch to rehearse progress and failure
                  recovery.
                </p>
                {[...project.bundle.batches].reverse().map((b) => (
                  <article className="panel batch" key={b.id}>
                    <div className="toolbar">
                      <h3>
                        {b.shot_snapshots.length} shots ·{" "}
                        {new Date(b.approved_at).toLocaleTimeString()}
                      </h3>
                      <span
                        className={`tag ${b.state === "failed" ? "failed" : ""}`}
                      >
                        {b.state}
                      </span>
                    </div>
                    <progress
                      max={b.shot_snapshots.length}
                      value={batchProgress(project, b)}
                      aria-label="Completed shots"
                    />
                    <p>
                      {batchProgress(project, b)} / {b.shot_snapshots.length}{" "}
                      completed · Cleanup {b.cleanup_state}
                    </p>
                    <details>
                      <summary>Frozen shot revisions</summary>
                      {b.shot_snapshots.map((s) => (
                        <p key={s.shot_id}>
                          {s.prompt} · Revision {s.revision} ·{" "}
                          {seconds(s.target_duration_ms)}
                        </p>
                      ))}
                    </details>
                    {["queued", "rendering", "provisioning"].includes(
                      b.state,
                    ) && (
                      <div className="actions">
                        <button
                          className="primary"
                          onClick={() =>
                            edit(
                              (p) => advanceBatch(p, b.id),
                              "Fictional render advanced.",
                            )
                          }
                        >
                          Advance fixture
                        </button>
                        <button
                          onClick={() =>
                            edit((p) => {
                              if (
                                requireItem(p.bundle.batches, b.id).state ===
                                "queued"
                              )
                                advanceBatch(p, b.id);
                              advanceBatch(p, b.id, true);
                            }, "Fictional render failure recorded.")
                          }
                        >
                          Simulate failure
                        </button>
                        <button
                          onClick={() =>
                            edit((p) => {
                              requireItem(p.bundle.batches, b.id).state =
                                "canceled";
                            }, "Batch canceled. Completed takes retained.")
                          }
                        >
                          Cancel batch
                        </button>
                      </div>
                    )}
                    {b.state === "failed" && (
                      <>
                        <p className="error">
                          The fictional render failed or its deadline expired.
                          Completed takes remain available.
                        </p>
                        <button
                          onClick={() => {
                            const missing = b.shot_snapshots
                              .filter(
                                (s) =>
                                  !project.bundle.attempts.some(
                                    (a) =>
                                      a.batch_id === b.id &&
                                      a.shot_id === s.shot_id &&
                                      a.state === "succeeded",
                                  ),
                              )
                              .map((s) => s.shot_id);
                            setSelected(missing);
                            setTab("Storyboard");
                            setNotice(
                              "Review the latest revisions of the unfinished shots for a new batch.",
                            );
                          }}
                        >
                          Prepare unfinished shots again
                        </button>
                      </>
                    )}
                  </article>
                ))}
              </section>
            )}
            {tab === "Take review" && (
              <section>
                <div className="toolbar">
                  <h2>Take review</h2>
                  <label>
                    Show shot
                    <select
                      value={shotId ?? ""}
                      onChange={(e) => setShotId(e.target.value || undefined)}
                    >
                      <option value="">All shots</option>
                      {project.bundle.shots.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.prompt}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="takes">
                  {project.bundle.takes
                    .filter((t) => !shotId || t.shot_id === shotId)
                    .map((t, index) => (
                      <article className="panel" key={t.id}>
                        <video
                          controls
                          preload="metadata"
                          src={project.media[t.asset_id]}
                          aria-label={`Take ${index + 1} preview`}
                        />
                        <h3>
                          Take {index + 1} · {seconds(t.duration_ms)}
                        </h3>
                        <p className="muted">
                          Shot revision{" "}
                          {
                            project.bundle.attempts.find(
                              (a) => a.id === t.attempt_id,
                            )?.shot_revision
                          }
                        </p>
                        <span
                          className={
                            project.selectedTakes[t.shot_id] === t.id
                              ? "tag accepted"
                              : "tag"
                          }
                        >
                          {project.selectedTakes[t.shot_id] === t.id
                            ? "Accepted selection"
                            : takeDecision(project, t)}
                        </span>
                        <div className="actions">
                          <button
                            className="primary"
                            disabled={project.selectedTakes[t.shot_id] === t.id}
                            onClick={() =>
                              edit(
                                (p) => reviewTake(p, t.id, "approved"),
                                "Take accepted. Prior takes and timeline revisions retained.",
                              )
                            }
                          >
                            {project.selectedTakes[t.shot_id]
                              ? "Use this take instead"
                              : "Accept take"}
                          </button>
                          <button
                            disabled={project.selectedTakes[t.shot_id] === t.id}
                            onClick={() =>
                              edit(
                                (p) => reviewTake(p, t.id, "rejected"),
                                "Take rejected for future selection.",
                              )
                            }
                          >
                            Reject take
                          </button>
                        </div>
                      </article>
                    ))}
                </div>
                {!project.bundle.takes.some(
                  (t) => !shotId || t.shot_id === shotId,
                ) && (
                  <p className="empty">
                    Render a batch to create takes for review.
                  </p>
                )}
              </section>
            )}
          </fieldset>
        </main>
      </div>
      <dialog ref={dialog} aria-labelledby="approve-title">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (
              commit((next) => {
                approveBatch(projectFor(next, projectId), selected, batchKey);
              }, "Batch approved. Shot revisions are frozen.")
            ) {
              dialog.current?.close();
              setSelected([]);
              setTab("Render batches");
            }
          }}
        >
          <h2 id="approve-title">Approve fictional render batch</h2>
          <p>{selected.length} shots · $0 GPU cost · Fixture model</p>
          <ul>
            {selected.map((id) => {
              const s = project.bundle.shots.find((s) => s.id === id);
              return (
                s && (
                  <li key={id}>
                    {s.prompt} · Revision {s.revision} ·{" "}
                    {seconds(s.target_duration_ms)}
                  </li>
                )
              );
            })}
          </ul>
          <p>
            Approval captures these prompts, references and settings. Subsequent
            edits create new shot revisions.
          </p>
          <p>Each fixture output is the supplied two-second blue clip.</p>
          <div className="actions">
            <button className="primary" disabled={locked}>
              Approve batch
            </button>
            <button type="button" onClick={() => dialog.current?.close()}>
              Keep editing
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
