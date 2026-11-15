import { useEffect, useRef, useState } from "react";
import { App } from "./App";
import { StudioClient } from "./api";
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
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [create, setCreate] = useState(false);
  const [recovery, setRecovery] = useState<Workspace>();
  function accept(next: Workspace) {
    setWorkspace(next);
    setDirty(false);
    setConflict(false);
    setGeneration((value) => value + 1);
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
    if (!dirty && !recovery) return;
    const preventLoss = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", preventLoss);
    return () => window.removeEventListener("beforeunload", preventLoss);
  }, [dirty, recovery]);
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
  return (
    <>
      <section className="panel" aria-label="Server connection">
        <h1>WAN Studio · Server workspace</h1>
        <p>
          Your projects are saved on the connected server. GPU rendering and
          reference uploads are not enabled in this interface yet.
        </p>
        {error && <p role="alert">{error}</p>}
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
              ? dirty
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
              disabled={busy || !dirty || conflict}
              onClick={() =>
                void action(async () => accept(await api.save(workspace!)))
              }
            >
              Save to server
            </button>
            <button
              disabled={busy}
              onClick={() => void action(async () => accept(await api.load()))}
            >
              {dirty ? "Discard edits and reload server" : "Reload server"}
            </button>
            <button disabled={busy || dirty} onClick={() => setCreate(!create)}>
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
              <input name="title" required disabled={busy || dirty} />
            </label>
            <label>
              New project format{" "}
              <select name="kind" disabled={busy || dirty}>
                <option value="music_video">Music video</option>
                <option value="short_film">Short film</option>
                <option value="cartoon">Cartoon</option>
              </select>
            </label>
            <button disabled={busy || dirty}>Create server project</button>
          </form>
        )}
        {!owner && (
          <a href="?mode=fixture">Open isolated fictional rehearsal</a>
        )}
      </section>
      {owner && workspace && workspace.projects.length > 0 && (
        <fieldset disabled={busy || conflict} className="workspace-fields">
          <App
            key={generation}
            connected={{
              workspace,
              owner,
              onChange: (next) => {
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
