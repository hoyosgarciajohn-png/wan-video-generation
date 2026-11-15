import { useState } from "react";
import type { StudioProject } from "./model";

export function TimelinePanel({
  project,
  clean,
  assemble,
  exportTimeline,
}: {
  project: StudioProject;
  clean: boolean;
  assemble: (audioAssetId: string | null) => void;
  exportTimeline: (id: string, revision: number) => void;
}) {
  const [audio, setAudio] = useState("");
  const complete =
    project.bundle.shots.length > 0 &&
    project.bundle.shots.every((shot) =>
      Boolean(project.selectedTakes[shot.id]),
    );
  return (
    <section aria-labelledby="timeline-heading">
      <h2 id="timeline-heading">Timeline and export</h2>
      <p>
        Assemble the selected approved take for each shot in saved storyboard
        order. Each assembly preserves earlier timelines. Soundtrack audio
        starts at the beginning and is trimmed to the timeline length. If it is
        shorter, the remaining video is silent. This version supports one
        soundtrack without manual trim controls. Exports use the frozen timeline
        revision.
      </p>
      {!clean && <p>Save pending edits before assembling or exporting.</p>}
      {!complete && <p>Accept a take for every shot before assembling.</p>}
      <label>
        Timeline soundtrack
        <select
          data-command-input="true"
          value={audio}
          onChange={(e) => setAudio(e.target.value)}
        >
          <option value="">No soundtrack</option>
          {project.bundle.assets
            .filter((asset) => asset.kind === "audio")
            .map((asset) => (
              <option key={asset.id} value={asset.id}>
                {project.assetNames[asset.id] ?? asset.id}
              </option>
            ))}
        </select>
      </label>
      <button
        disabled={!clean || !complete}
        onClick={() => assemble(audio || null)}
      >
        Assemble selected takes
      </button>
      <h3>Saved timelines</h3>
      {project.bundle.timelines.length === 0 && (
        <p>No assembled timelines yet.</p>
      )}
      {[...project.bundle.timelines].reverse().map((timeline) => (
        <article className="panel" key={`${timeline.id}-${timeline.revision}`}>
          <h4>
            Timeline {timeline.id} · Revision {timeline.revision}
          </h4>
          <p>
            {timeline.items.length} shots ·{" "}
            {(timeline.duration_ms / 1000).toLocaleString()} seconds ·{" "}
            {timeline.audio.length ? "With soundtrack" : "No soundtrack"}
          </p>
          <button
            disabled={!clean}
            onClick={() => exportTimeline(timeline.id, timeline.revision)}
          >
            Export revision {timeline.revision}
          </button>
        </article>
      ))}
      <h3>Exports</h3>
      {project.bundle.exports.length === 0 && <p>No exports yet.</p>}
      {[...project.bundle.exports].reverse().map((item) => (
        <article className="panel" key={item.id}>
          <h4>Export {item.id}</h4>
          <p>
            Timeline {item.timeline_id} · Revision {item.timeline_revision} ·{" "}
            <strong>{item.state}</strong>
          </p>
          {item.state === "succeeded" && item.output_asset_id && (
            <a
              download={`wan-${item.id}.mp4`}
              href={`/v1/studio/projects/${encodeURIComponent(project.bundle.project.id)}/assets/${encodeURIComponent(item.output_asset_id)}/content`}
            >
              Download MP4
            </a>
          )}
          {item.state === "failed" && (
            <p role="status">
              Export failed. The saved timeline and accepted takes are retained.
              You can request a new export.
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
