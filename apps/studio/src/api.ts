import { StudioError, type Workspace } from "./model";
import type { Project } from "./contract";

type Envelope = { id: "default"; workspace: Workspace };
export type StudioCommand =
  | {
      kind: "submit";
      projectId: string;
      shot_ids: string[];
      expected_revision: number;
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
                "Content-Type": "application/json",
                "X-WAN-Request": "studio",
              },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch {
      throw new StudioError(503);
    }
    if (!response.ok) throw new StudioError(response.status);
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
  async command(command: StudioCommand) {
    const prefix = `projects/${encodeURIComponent(command.projectId)}`;
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
