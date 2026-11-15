import { useState, type FormEvent } from "react";
import type { Shot } from "./contract";
import { saveShot, type StudioProject } from "./model";

export function ShotEditor({
  project,
  shot,
  onSave,
}: {
  project: StudioProject;
  shot?: Shot;
  onSave: (input: Parameters<typeof saveShot>[1], shot?: Shot) => void;
}) {
  const [prompt, setPrompt] = useState(shot?.prompt ?? "");
  const [scene, setScene] = useState(shot?.scene_id ?? project.scenes[0].id);
  const [duration, setDuration] = useState(
    (shot?.target_duration_ms ?? 2000) / 1000,
  );
  const [seed, setSeed] = useState(shot?.settings.seed ?? 42);
  const [refs, setRefs] = useState(shot?.reference_asset_ids ?? []);
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave(
      {
        prompt,
        scene_id: scene,
        target_duration_ms: Math.round(duration * 1000),
        reference_asset_ids: refs,
        settings: {
          width: 320,
          height: 180,
          frame_rate: { numerator: 24, denominator: 1 },
          seed,
          steps: 1,
        },
      },
      shot,
    );
  }
  return (
    <form onSubmit={submit} className="editor">
      <h2>{shot ? "Edit shot" : "New shot"}</h2>
      {shot && (
        <p className="muted">
          Revision {shot.revision} ·{" "}
          {project.selectedTakes[shot.id]
            ? "Accepted take saved"
            : "Awaiting an accepted take"}
        </p>
      )}
      <label>
        Scene
        <select value={scene} onChange={(e) => setScene(e.target.value)}>
          {project.scenes.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </label>
      <label>
        Shot prompt
        <textarea
          required
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe the subject, action, camera and lighting"
          rows={5}
        />
      </label>
      <div className="fields">
        <label>
          Target seconds
          <input
            required
            type="number"
            min="0.001"
            step="0.001"
            max={project.bundle.project.runtime_limit_ms / 1000}
            value={duration}
            onChange={(e) => setDuration(e.target.valueAsNumber)}
          />
        </label>
        <label>
          Seed
          <input
            required
            type="number"
            min="0"
            step="1"
            value={seed}
            onChange={(e) => setSeed(e.target.valueAsNumber)}
          />
        </label>
      </div>
      <fieldset>
        <legend>Recurring references</legend>
        {project.bundle.assets
          .filter((a) => a.kind === "image")
          .map((a) => (
            <label className="check" key={a.id}>
              <input
                type="checkbox"
                checked={refs.includes(a.id)}
                onChange={(e) =>
                  setRefs(
                    e.target.checked
                      ? [...refs, a.id]
                      : refs.filter((r) => r !== a.id),
                  )
                }
              />
              {project.assetNames[a.id]}
            </label>
          ))}
        {!project.bundle.assets.some((a) => a.kind === "image") && (
          <p className="muted">
            Add character or location images in References.
          </p>
        )}
      </fieldset>
      <button className="primary" type="submit">
        {shot ? "Save new revision" : "Add shot"}
      </button>
    </form>
  );
}
