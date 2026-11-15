import { useEffect, useRef, useState } from "react";
import { App } from "./App";
import { StudioClient, type StudioCommand, type UploadProgress } from "./api";
import { errorMessage, StudioError, type Workspace } from "./model";
import type { Project } from "./contract";

export function ConnectedStudio({
  client = new StudioClient(),
}: {
  client?: StudioClient;
}) {
  const api = useRef(client).current;
  const [owner, setOwner] = useState("");
  const [workspace, setWorkspace] = useState<Workspace>();
  const [dirty, setDirty] = useState(false);
  const [editing, setEditing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>();
  const [pending, setPending] = useState<StudioCommand>();
  const freshness = useRef(0);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [create, setCreate] = useState(false);
  const [recovery, setRecovery] = useState<Workspace>();
  const commandState = useRef({ dirty, editing, busy, conflict, pending });
  commandState.current = { dirty, editing, busy, conflict, pending };
  function accept(next: Workspace, remount = true) {
    freshness.current++;
    setWorkspace(next);
    setDirty(false);
    setEditing(false);
    setConflict(false);
    if (remount) setGeneration((value) => value + 1);
  }
  function failed(e: unknown) {
    setError(errorMessage(e));
    if (e instanceof StudioError && e.code === 409) setConflict(true);
    if (e instanceof StudioError && e.code === 401) {
      if (dirty && workspace) setRecovery(structuredClone(workspace));
      setOwner("");
      setWorkspace(undefined);
      setDirty(false);
    }
  }
  useEffect(() => {
    if (!dirty && !editing && !recovery && !pending) return;
    const preventLoss = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", preventLoss);
    return () => window.removeEventListener("beforeunload", preventLoss);
  }, [dirty, editing, recovery, pending]);
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const session = await api.session();
        const loaded = await api.load();
        if (active) {
          setOwner(session.owner_id);
          accept(loaded);
        }
      } catch (e) {
        if (active) failed(e);
      } finally {
        if (active) setBusy(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [api]);
  async function action(run: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await run();
    } catch (e) {
      failed(e);
    } finally {
      setBusy(false);
    }
  }
  async function runCommand(command: StudioCommand) {
    const latest = commandState.current;
    if (
      latest.dirty ||
      latest.editing ||
      latest.busy ||
      latest.conflict ||
      (latest.pending && latest.pending !== command)
    ) {
      setError("Save pending edits before sending a server command.");
      return;
    }
    freshness.current++;
    setPending(command);
    if (command.kind !== "upload-file") setUploadProgress(undefined);
    await action(async () => {
      try {
        const next = await api.command(command, setUploadProgress);
        accept(next, false);
        setPending(undefined);
      } catch (e) {
        if (
          e instanceof StudioError &&
          ([404, 409, 410, 422].includes(e.code) ||
            (e.code === 401 && command.kind !== "upload-file"))
        )
          setPending(undefined);
        throw e;
      }
    });
  }
  const active =
    workspace?.projects.some((p) =>
      [...p.bundle.batches, ...p.bundle.exports].some(
        (b) => !["succeeded", "failed", "canceled"].includes(b.state),
      ),
    ) ?? false;
  useEffect(() => {
    if (!owner || dirty || editing || busy || conflict || pending || !active)
      return;
    let stopped = false;
    let running = false;
    const timer = setInterval(async () => {
      if (running) return;
      running = true;
      const version = freshness.current;
      try {
        const next = await api.load();
        if (!stopped && freshness.current === version) accept(next, false);
      } catch (e) {
        if (!stopped && freshness.current === version) failed(e);
      } finally {
        running = false;
      }
    }, 1500);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [api, owner, dirty, editing, busy, conflict, pending, active]);
  return (
    <>
      <section className="panel" aria-label="Server connection">
        <h1>WAN Studio · Server workspace</h1>
        <p>
          Server fixture rendering produces silent synthetic test clips up to
          five seconds (320×180, 24 fps), with no reference images or GPU
          rental. These are not Wan-generated results. Upload references,
          assemble accepted takes and export a soundtrack-backed video using the
          server.
        </p>
        {error && <p role="alert">{error}</p>}
        {pending?.kind === "upload-file" && uploadProgress && (
          <p role="status">
            Uploaded {(uploadProgress.received / 1048576).toFixed(1)} of{" "}
            {(uploadProgress.total / 1048576).toFixed(1)} MiB. Interrupted
            uploads resume from verified server chunks while this tab stays
            open.
          </p>
        )}
        {pending && (
          <div role="status">
            <p>
              A server command is awaiting confirmation. Retry the same request
              to avoid duplicate work.
            </p>
            <button
              disabled={busy || !owner}
              onClick={() => void runCommand(pending)}
            >
              Retry pending command
            </button>
          </div>
        )}
        {recovery && (
          <div className="notice">
            <p>
              Your session expired with unsaved changes. A recovery draft
              remains in this tab, including after signing in again. Download it
              before closing the tab.
            </p>
            <button
              onClick={() => {
                const url = URL.createObjectURL(
                  new Blob([JSON.stringify(recovery, null, 2)], {
                    type: "application/json",
                  }),
                );
                const link = document.createElement("a");
                link.href = url;
                link.download = "wan-unsaved-workspace.json";
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
              }}
            >
              Download unsaved draft
            </button>
          </div>
        )}
        <p role="status">
          {busy
            ? "Connecting or saving…"
            : owner
              ? dirty || editing
                ? "Unsaved changes in this tab."
                : "Saved on server."
              : "Disconnected. Sign in to load your projects."}
        </p>
        {!owner && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const token = String(new FormData(form).get("token") ?? "");
              form.reset();
              void action(async () => {
                const session = await api.login(token);
                const loaded = await api.load();
                setOwner(session.owner_id);
                accept(loaded);
              });
            }}
          >
            <label>
              Server access token{" "}
              <input
                name="token"
                type="password"
                required
                autoComplete="off"
                disabled={busy}
              />
            </label>
            <button disabled={busy}>Connect</button>
            <p>
              The token is exchanged for a session cookie and is not saved in
              browser storage.
            </p>
          </form>
        )}
        {owner && (
          <div className="actions">
            <button
              disabled={busy || !dirty || conflict || Boolean(pending)}
              onClick={() =>
                void action(async () => accept(await api.save(workspace!)))
              }
            >
              Save to server
            </button>
            <button
              disabled={busy || Boolean(pending)}
              onClick={() => {
                freshness.current++;
                void action(async () => accept(await api.load()));
              }}
            >
              {dirty ? "Discard edits and reload server" : "Reload server"}
            </button>
            <button
              disabled={busy || dirty || editing || Boolean(pending)}
              onClick={() => setCreate(!create)}
            >
              New server project
            </button>
            <button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  await api.logout();
                  setOwner("");
                  setWorkspace(undefined);
                  setDirty(false);
                  setCreate(false);
                })
              }
            >
              Sign out
            </button>
          </div>
        )}
        {owner && (create || workspace?.projects.length === 0) && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void action(async () => {
                accept(
                  await api.create(
                    String(data.get("title")),
                    String(data.get("kind")) as Project["kind"],
                    workspace!.revision,
                  ),
                );
                setCreate(false);
              });
            }}
          >
            <label>
              New project title{" "}
              <input
                name="title"
                required
                disabled={busy || dirty || editing || Boolean(pending)}
              />
            </label>
            <label>
              New project format{" "}
              <select
                name="kind"
                disabled={busy || dirty || editing || Boolean(pending)}
              >
                <option value="music_video">Music video</option>
                <option value="short_film">Short film</option>
                <option value="cartoon">Cartoon</option>
              </select>
            </label>
            <button disabled={busy || dirty || editing || Boolean(pending)}>
              Create server project
            </button>
          </form>
        )}
        {!owner && (
          <a href="?mode=fixture">Open isolated fictional rehearsal</a>
        )}
      </section>
      {owner && workspace && workspace.projects.length > 0 && (
        <fieldset
          disabled={busy || conflict || Boolean(pending)}
          className="workspace-fields"
        >
          <App
            key={generation}
            connected={{
              workspace,
              owner,
              upload: (projectId, file) =>
                runCommand({
                  kind: "upload-file",
                  projectId,
                  file,
                  expected_revision: workspace.revision,
                  idempotency_key: crypto.randomUUID(),
                }),
              assemble: (projectId, audio_asset_id) =>
                void runCommand({
                  kind: "timeline",
                  projectId,
                  audio_asset_id,
                  expected_revision: workspace.revision,
                  idempotency_key: crypto.randomUUID(),
                }),
              exportTimeline: (projectId, timeline_id, timeline_revision) =>
                void runCommand({
                  kind: "export",
                  projectId,
                  timeline_id,
                  timeline_revision,
                  idempotency_key: crypto.randomUUID(),
                }),
              clean: !dirty && !editing && !busy && !conflict && !pending,
              onEditing: () => {
                freshness.current++;
                setEditing(true);
              },
              submit: (projectId, shot_ids, idempotency_key) =>
                void runCommand({
                  kind: "submit",
                  projectId,
                  shot_ids,
                  expected_revision: workspace.revision,
                  idempotency_key,
                }),
              cancel: (projectId, batchId) =>
                void runCommand({ kind: "cancel", projectId, batchId }),
              review: (projectId, takeId, decision) =>
                void runCommand({
                  kind: "review",
                  projectId,
                  takeId,
                  decision,
                  expected_revision: workspace.revision,
                  idempotency_key: crypto.randomUUID(),
                }),
              onChange: (next) => {
                freshness.current++;
                setWorkspace(next);
                setDirty(true);
              },
            }}
          />
        </fieldset>
      )}
    </>
  );
}
