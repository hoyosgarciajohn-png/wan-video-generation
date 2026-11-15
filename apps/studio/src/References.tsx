import { useState } from "react";
import type { Asset } from "./contract";
import { OWNER, StudioError, type StudioProject } from "./model";
type Edit = (draft: StudioProject) => void;
const seconds = (ms: number) => `${(ms / 1000).toLocaleString()}s`;

export function References({
  project,
  edit,
  report,
  allowImport = true,
}: {
  project: StudioProject;
  allowImport?: boolean;
  edit: (change: Edit, message: string) => void;
  report: (error: unknown) => void;
}) {
  const [busy, setBusy] = useState(false);
  async function importFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try {
      const image = ["image/png", "image/jpeg", "image/webp"].includes(
        file.type,
      );
      const audio = [
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
      ].includes(file.type);
      if (
        (!image && !audio) ||
        file.size < 1 ||
        file.size > (image ? 1024 * 1024 : 4 * 1024 * 1024)
      )
        throw new StudioError(422);
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      let duration: number | null = null;
      if (image)
        await new Promise<void>((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve();
          img.onerror = reject;
          img.src = data;
        });
      else
        duration = await new Promise<number>((resolve, reject) => {
          const media = document.createElement("audio");
          media.onloadedmetadata = () => {
            const ms = Math.round(media.duration * 1000);
            Number.isSafeInteger(ms) && ms > 0
              ? resolve(ms)
              : reject(new StudioError(422));
          };
          media.onerror = reject;
          media.src = data;
        });
      if (duration && duration > project.bundle.project.runtime_limit_ms)
        throw new StudioError(422);
      const sha = Array.from(
        new Uint8Array(
          await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
        ),
      )
        .map((v) => v.toString(16).padStart(2, "0"))
        .join("");
      const asset: Asset = {
        id: `asset-${crypto.randomUUID()}`,
        project_id: project.bundle.project.id,
        owner_id: OWNER,
        kind: image ? "image" : "audio",
        object_key: `${project.bundle.project.id}/imports/${crypto.randomUUID()}`,
        mime_type: file.type,
        bytes: file.size,
        sha256: sha,
        duration_ms: duration,
      };
      edit((p) => {
        p.bundle.assets.push(asset);
        p.media[asset.id] = data;
        p.assetNames[asset.id] = file.name;
      }, "Reference saved in this browser.");
    } catch (error) {
      report(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-labelledby="refs-heading">
      <h2 id="refs-heading">References and source material</h2>
      <p className="muted">
        {allowImport
          ? "Reuse character and location images across shots. Images up to 1 MB and audio up to 4 MB are saved in this browser for the rehearsal."
          : "Review server references and edit their names or your creative brief. Use Save to server to persist changes."}
      </p>
      {!allowImport && (
        <p>Reference uploads are not connected to the server yet.</p>
      )}
      <label className="upload">
        Add image or soundtrack
        <input
          type="file"
          disabled={busy || !allowImport}
          accept="image/png,image/jpeg,image/webp,audio/wav,audio/mpeg,audio/mp4,audio/ogg"
          onChange={(e) => {
            void importFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </label>
      {busy && <p role="status">Checking and saving file…</p>}
      <div className="assets">
        {project.bundle.assets
          .filter((a) => a.kind !== "video")
          .map((a) => (
            <article className="asset" key={a.id}>
              {a.kind === "image" ? (
                <img src={project.media[a.id]} alt={project.assetNames[a.id]} />
              ) : (
                <audio
                  controls
                  src={project.media[a.id]}
                  aria-label={project.assetNames[a.id]}
                />
              )}
              <label>
                Reference name
                <input
                  value={project.assetNames[a.id] ?? a.id}
                  onChange={(e) =>
                    edit((p) => {
                      p.assetNames[a.id] = e.target.value;
                    }, "Reference name saved.")
                  }
                />
              </label>
              <small>
                {a.kind === "image"
                  ? "Reusable image"
                  : `Soundtrack · ${seconds(a.duration_ms ?? 0)}`}
              </small>
            </article>
          ))}
      </div>
      <label>
        Script or creative brief
        <textarea
          rows={7}
          value={project.script}
          onChange={(e) =>
            edit((p) => {
              p.script = e.target.value;
            }, "Creative brief saved.")
          }
          placeholder="Write or paste your fictional script here"
        />
      </label>
    </section>
  );
}
