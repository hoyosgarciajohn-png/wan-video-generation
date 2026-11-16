import { StudioError, type Workspace } from "./model";
import type { Project } from "./contract";

type Envelope = { id: "default"; workspace: Workspace };
export type UploadProgress = { received: number; total: number };
export type UploadFileCommand = {
  kind: "upload-file";
  projectId: string;
  file: File;
  expected_revision: number;
  idempotency_key: string;
  uploadId?: string;
};
type UploadSession = {
  id: string;
  state: string;
  bytes: number;
  received_bytes: number;
  chunk_size: number;
  next_chunk_index: number;
  chunk_sha256: string[];
};
const CHUNK_BYTES = 1024 * 1024;
export type StudioCommand =
  | UploadFileCommand
  | {
      kind: "submit";
      projectId: string;
      shot_ids: string[];
      expected_revision: number;
      idempotency_key: string;
    }
  | {
      kind: "upload";
      projectId: string;
      name: string;
      mime_type: string;
      data_base64: string;
      expected_revision: number;
      idempotency_key: string;
    }
  | {
      kind: "timeline";
      projectId: string;
      audio_asset_id: string | null;
      expected_revision: number;
      idempotency_key: string;
    }
  | {
      kind: "export";
      projectId: string;
      timeline_id: string;
      timeline_revision: number;
      idempotency_key: string;
    }
  | { kind: "cancel"; projectId: string; batchId: string }
  | {
      kind: "review";
      projectId: string;
      takeId: string;
      decision: "approved" | "rejected";
      expected_revision: number;
      idempotency_key: string;
    };
export class StudioClient {
  constructor(private readonly request: typeof fetch = fetch) {}
  private async call<T>(
    path: string,
    method = "GET",
    body?: unknown,
    binary?: Blob,
  ): Promise<T> {
    let response: Response;
    try {
      response = await this.request(`/v1/studio/${path}`, {
        method,
        credentials: "same-origin",
        cache: "no-store",
        headers:
          method === "GET"
            ? {}
            : {
                "Content-Type": binary
                  ? "application/octet-stream"
                  : "application/json",
                "X-WAN-Request": "studio",
              },
        ...(binary
          ? { body: binary }
          : body === undefined
            ? {}
            : { body: JSON.stringify(body) }),
      });
    } catch {
      console.warn("WAN connection failed before receiving an HTTP response");
      throw new StudioError(503);
    }
    if (!response.ok) {
      console.warn(`WAN connection returned HTTP ${response.status}`);
      throw new StudioError(response.status);
    }
    if (response.status === 204) return undefined as T;
    try {
      return (await response.json()) as T;
    } catch {
      throw new StudioError(503);
    }
  }
  session() {
    return this.call<{ owner_id: string }>("session");
  }
  login(token: string) {
    return this.call<{ owner_id: string }>("session", "POST", { token });
  }
  logout() {
    return this.call<void>("session", "DELETE");
  }
  async load() {
    return (await this.call<Envelope>("workspaces/default")).workspace;
  }
  async create(
    title: string,
    kind: Project["kind"],
    expected_revision: number,
  ) {
    return (
      await this.call<Envelope>("workspaces", "POST", {
        title,
        kind,
        expected_revision,
      })
    ).workspace;
  }
  async uploadFile(
    command: UploadFileCommand,
    progress?: (value: UploadProgress) => void,
  ): Promise<Workspace> {
    const file = command.file;
    const mime_type = file.type === "audio/x-wav" ? "audio/wav" : file.type;
    const image = ["image/png", "image/jpeg", "image/webp"].includes(mime_type);
    if (
      (!image && !["audio/wav", "audio/mpeg"].includes(mime_type)) ||
      file.size < 1 ||
      file.size > (image ? CHUNK_BYTES : 128 * CHUNK_BYTES)
    )
      throw new StudioError(422);
    const prefix = `projects/${encodeURIComponent(command.projectId)}/uploads`;
    let session: UploadSession;
    if (command.uploadId)
      session = (
        await this.call<{ upload: UploadSession }>(
          `${prefix}/${encodeURIComponent(command.uploadId)}`,
        )
      ).upload;
    else {
      session = (
        await this.call<{ upload: UploadSession }>(prefix, "POST", {
          name: file.name,
          mime_type,
          bytes: file.size,
          expected_revision: command.expected_revision,
          idempotency_key: command.idempotency_key,
        })
      ).upload;
      command.uploadId = session.id;
    }
    if (["expired", "aborted"].includes(session.state))
      throw new StudioError(410);
    if (
      session.bytes !== file.size ||
      session.chunk_size !== CHUNK_BYTES ||
      !Array.isArray(session.chunk_sha256) ||
      session.next_chunk_index !== session.chunk_sha256.length ||
      session.received_bytes !==
        Math.min(file.size, session.next_chunk_index * CHUNK_BYTES)
    )
      throw new StudioError(503);
    const hashes: string[] = [];
    progress?.({ received: session.received_bytes, total: file.size });
    for (
      let offset = 0, index = 0;
      offset < file.size;
      offset += CHUNK_BYTES, index++
    ) {
      const chunk = file.slice(
        offset,
        Math.min(file.size, offset + CHUNK_BYTES),
      );
      const bytes =
        typeof chunk.arrayBuffer === "function"
          ? await chunk.arrayBuffer()
          : await new Promise<ArrayBuffer>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(reader.result as ArrayBuffer);
              reader.onerror = () => reject(new StudioError(503));
              reader.readAsArrayBuffer(chunk);
            });
      const hash = Array.from(
        new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      )
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");
      hashes.push(hash);
      if (index < session.next_chunk_index) {
        if (session.chunk_sha256[index] !== hash) throw new StudioError(409);
        continue;
      }
      const next = (
        await this.call<{ upload: UploadSession }>(
          `${prefix}/${encodeURIComponent(command.uploadId!)}/chunks/${index}`,
          "PUT",
          undefined,
          chunk,
        )
      ).upload;
      if (
        next.received_bytes !== offset + chunk.size ||
        next.chunk_sha256[index] !== hash
      )
        throw new StudioError(503);
      session = next;
      progress?.({ received: next.received_bytes, total: file.size });
    }
    return (
      await this.call<{ workspace: Workspace }>(
        `${prefix}/${encodeURIComponent(command.uploadId!)}/finish`,
        "POST",
        { chunk_sha256: hashes },
      )
    ).workspace;
  }
  async command(
    command: StudioCommand,
    progress?: (value: UploadProgress) => void,
  ) {
    if (command.kind === "upload-file")
      return this.uploadFile(command, progress);
    const prefix = `projects/${encodeURIComponent(command.projectId)}`;
    if (command.kind === "upload") {
      const {
        name,
        mime_type,
        data_base64,
        expected_revision,
        idempotency_key,
      } = command;
      return (
        await this.call<{ workspace: Workspace }>(`${prefix}/assets`, "POST", {
          name,
          mime_type,
          data_base64,
          expected_revision,
          idempotency_key,
        })
      ).workspace;
    }
    if (command.kind === "timeline") {
      const { audio_asset_id, expected_revision, idempotency_key } = command;
      return (
        await this.call<{ workspace: Workspace }>(
          `${prefix}/timelines`,
          "POST",
          { audio_asset_id, expected_revision, idempotency_key },
        )
      ).workspace;
    }
    if (command.kind === "export") {
      const { timeline_id, timeline_revision, idempotency_key } = command;
      return (
        await this.call<{ workspace: Workspace }>(`${prefix}/exports`, "POST", {
          timeline_id,
          timeline_revision,
          idempotency_key,
        })
      ).workspace;
    }
    if (command.kind === "submit") {
      const { shot_ids, expected_revision, idempotency_key } = command;
      return (
        await this.call<{ workspace: Workspace }>(`${prefix}/batches`, "POST", {
          shot_ids,
          expected_revision,
          idempotency_key,
        })
      ).workspace;
    }
    if (command.kind === "cancel")
      return (
        await this.call<{ workspace: Workspace }>(
          `${prefix}/batches/${encodeURIComponent(command.batchId)}/cancel`,
          "POST",
          {},
        )
      ).workspace;
    const { decision, expected_revision, idempotency_key } = command;
    return (
      await this.call<{ workspace: Workspace }>(
        `${prefix}/takes/${encodeURIComponent(command.takeId)}/review`,
        "POST",
        { decision, expected_revision, idempotency_key },
      )
    ).workspace;
  }
  async save(workspace: Workspace) {
    return (
      await this.call<Envelope>("workspaces/default", "PUT", {
        expected_revision: workspace.revision,
        workspace,
      })
    ).workspace;
  }
}
