import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
  act,
} from "@testing-library/react";
import { ConnectedStudio } from "../src/ConnectedStudio";
import { StudioClient } from "../src/api";
import { initialWorkspace, STORAGE_KEY, StudioError } from "../src/model";
afterEach(() => {
  cleanup();
  localStorage.clear();
});

test("connected edits stay in memory and server conflicts require explicit reload", async () => {
  const state = initialWorkspace();
  let calls = 0;
  const client = new StudioClient(async (url, init) => {
    if (String(url).endsWith("session"))
      return Response.json({ owner_id: "fictional-owner" });
    if (init?.method === "PUT") {
      calls++;
      return new Response("stale", { status: 409 });
    }
    return Response.json({ id: "default", workspace: state });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.change(screen.getByLabelText("Shot prompt"), {
    target: { value: "Unsaved fictional change" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));
  assert.equal(localStorage.getItem(STORAGE_KEY), null);
  assert.ok(screen.getByText("Unsaved changes in this tab."));
  fireEvent.click(screen.getByRole("button", { name: "Save to server" }));
  await screen.findByRole("alert");
  assert.equal(calls, 1);
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Save to server",
      }) as HTMLButtonElement
    ).disabled,
    true,
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Discard edits and reload server" }),
  );
  await waitFor(() =>
    assert.equal(
      (screen.getByLabelText("Shot prompt") as HTMLTextAreaElement).value,
      "A blue studio backdrop",
    ),
  );
  assert.equal(localStorage.getItem(STORAGE_KEY), null);
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Review render batch",
      }) as HTMLButtonElement
    ).disabled,
    true,
  );
});
test("disconnected login clears token input and creates first server project", async () => {
  let authenticated = false;
  let created = false;
  const state = initialWorkspace();
  const client = new StudioClient(async (url, init) => {
    if (String(url).endsWith("session")) {
      if (init?.method === "POST") {
        authenticated = true;
        assert.equal(JSON.parse(String(init.body)).token, "fictional-token");
      }
      return authenticated
        ? Response.json({ owner_id: "fictional-owner" })
        : new Response("", { status: 401 });
    }
    if (init?.method === "POST") created = true;
    return Response.json({
      id: "default",
      workspace: created ? state : { version: 1, revision: 0, projects: [] },
    });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByText("Disconnected. Sign in to load your projects.");
  fireEvent.change(screen.getByLabelText("Server access token"), {
    target: { value: "fictional-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Connect" }));
  await screen.findByLabelText("New project title");
  fireEvent.change(screen.getByLabelText("New project title"), {
    target: { value: "Fictional story" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Create server project" }),
  );
  await screen.findByLabelText("Shot prompt");
  assert.equal(localStorage.length, 0);
});
test("server owner edits multiple times then saves one shot revision", async () => {
  const state = initialWorkspace();
  state.projects[0].bundle.project.owner_id = "owner-john";
  let submitted: typeof state | undefined;
  const client = new StudioClient(async (url, init) => {
    if (String(url).endsWith("session"))
      return Response.json({ owner_id: "owner-john" });
    if (init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      assert.equal(body.expected_revision, 0);
      submitted = body.workspace;
      submitted!.revision = 1;
      return Response.json({ id: "default", workspace: submitted });
    }
    return Response.json({ id: "default", workspace: state });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  for (const prompt of ["First draft", "Second draft"]) {
    fireEvent.change(screen.getByLabelText("Shot prompt"), {
      target: { value: prompt },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));
  }
  fireEvent.click(screen.getByRole("button", { name: "Save to server" }));
  await waitFor(() => assert.ok(screen.getByText("Saved on server.")));
  assert.equal(submitted!.projects[0].bundle.shots[0].revision, 2);
  assert.equal(submitted!.projects[0].bundle.shots[0].prompt, "Second draft");
  assert.equal(localStorage.length, 0);
});
test("expired session retains unsaved recovery through reauthentication", async () => {
  const state = initialWorkspace();
  const client = new StudioClient(async (url, init) => {
    if (String(url).endsWith("session"))
      return Response.json({ owner_id: "fictional-owner" });
    if (init?.method === "PUT") return new Response("expired", { status: 401 });
    return Response.json({ id: "default", workspace: state });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.change(screen.getByLabelText("Shot prompt"), {
    target: { value: "Preserve this draft" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));
  const before = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(before);
  assert.equal(before.defaultPrevented, true);
  fireEvent.click(screen.getByRole("button", { name: "Save to server" }));
  await screen.findByRole("button", { name: "Download unsaved draft" });
  assert.equal(screen.queryByLabelText("Shot prompt"), null);
  fireEvent.change(screen.getByLabelText("Server access token"), {
    target: { value: "fictional-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Connect" }));
  await screen.findByLabelText("Shot prompt");
  assert.ok(screen.getByRole("button", { name: "Download unsaved draft" }));
  assert.equal(localStorage.length, 0);
  let downloaded: Blob | undefined;
  const createURL = URL.createObjectURL;
  const clickAnchor = window.HTMLAnchorElement.prototype.click;
  try {
    URL.createObjectURL = (blob) => {
      downloaded = blob as Blob;
      return "blob:recovery-test";
    };
    window.HTMLAnchorElement.prototype.click = () => {};
    fireEvent.click(
      screen.getByRole("button", { name: "Download unsaved draft" }),
    );
    const recovered = JSON.parse(await downloaded!.text());
    assert.equal(
      recovered.projects[0].bundle.shots[0].prompt,
      "Preserve this draft",
    );
  } finally {
    URL.createObjectURL = createURL;
    window.HTMLAnchorElement.prototype.click = clickAnchor;
  }
  const recoveryBeforeUnload = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(recoveryBeforeUnload);
  assert.equal(recoveryBeforeUnload.defaultPrevented, true);
});
test("render command retry keeps exact payload and polling preserves the active tab", async () => {
  const state = initialWorkspace();
  const active = structuredClone(state);
  active.projects[0].bundle.batches[0].state = "rendering";
  let posted = 0;
  let loads = 0;
  const bodies: string[] = [];
  const client = new StudioClient(async (url, init) => {
    if (String(url).endsWith("session"))
      return Response.json({ owner_id: "fictional-owner" });
    if (String(url).endsWith("/batches")) {
      bodies.push(String(init?.body));
      posted++;
      return posted === 1
        ? new Response("ambiguous", { status: 503 })
        : Response.json({ workspace: active });
    }
    loads++;
    return Response.json({ id: "default", workspace: state });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.click(screen.getByLabelText("Select A blue studio backdrop"));
  fireEvent.click(screen.getByRole("button", { name: "Review render batch" }));
  fireEvent.click(screen.getByRole("button", { name: "Approve batch" }));
  await screen.findByRole("alert");
  fireEvent.click(
    screen.getByRole("button", { name: "Retry pending command" }),
  );
  await waitFor(() =>
    assert.ok(!screen.queryByRole("button", { name: "Retry pending command" })),
  );
  assert.equal(bodies.length, 2);
  assert.equal(bodies[0], bodies[1]);
  fireEvent.click(screen.getByRole("button", { name: "References" }));
  await waitFor(() => assert.ok(loads >= 2), { timeout: 3000 });
  assert.ok(
    screen.getByRole("heading", { name: "References and source material" }),
  );
});
test("dirty workspaces cannot render and in-flight polling cannot replace edits", async () => {
  const state = initialWorkspace();
  state.projects[0].bundle.batches[0].state = "rendering";
  let loads = 0;
  let release: ((response: Response) => void) | undefined;
  const client = new StudioClient(async (url) => {
    if (String(url).endsWith("session"))
      return Response.json({ owner_id: "fictional-owner" });
    loads++;
    if (loads > 1)
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    return Response.json({ id: "default", workspace: state });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  await waitFor(() => assert.ok(release), { timeout: 3000 });
  fireEvent.change(screen.getByLabelText("Shot prompt"), {
    target: { value: "Keep my draft" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save new revision" }));
  release!(Response.json({ id: "default", workspace: state }));
  await waitFor(() =>
    assert.ok(screen.getByText("Unsaved changes in this tab.")),
  );
  assert.equal(
    (screen.getByLabelText("Shot prompt") as HTMLTextAreaElement).value,
    "Keep my draft",
  );
  fireEvent.click(screen.getByLabelText("Select Keep my draft"));
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Review render batch",
      }) as HTMLButtonElement
    ).disabled,
    true,
  );
});
test("connected cancel and take decisions use server commands", async () => {
  const state = initialWorkspace();
  state.projects[0].bundle.batches[0].state = "rendering";
  const requests: { url: string; body: Record<string, unknown> }[] = [];
  const client = new StudioClient(async (url, init) => {
    if (String(url).endsWith("session"))
      return Response.json({ owner_id: "fictional-owner" });
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      requests.push({ url: String(url), body });
      if (String(url).endsWith("/cancel"))
        state.projects[0].bundle.batches[0].state = "canceled";
      else {
        state.revision++;
        state.projects[0].selectedTakes =
          body.decision === "approved" ? { "shot-1": "take-1" } : {};
        state.projects[0].bundle.reviews.push({
          ...state.projects[0].bundle.reviews[0],
          id: `review-${state.revision}`,
          decision: body.decision,
        });
      }
      return Response.json({ workspace: state });
    }
    return Response.json({ id: "default", workspace: state });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.click(screen.getByRole("button", { name: "Render batches" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel server batch" }));
  await waitFor(() => assert.ok(screen.getByText("canceled", { exact: true })));
  fireEvent.click(screen.getByRole("button", { name: "Take review" }));
  fireEvent.click(screen.getByRole("button", { name: "Reject take" }));
  await waitFor(() => assert.ok(!screen.queryByText("Accepted selection")));
  fireEvent.click(screen.getByRole("button", { name: "Accept take" }));
  await screen.findByText("Accepted selection");
  assert.equal(requests.length, 3);
  assert.ok(requests[0].url.endsWith("/cancel"));
  assert.equal(requests[1].body.decision, "rejected");
  assert.equal(requests[1].body.expected_revision, 0);
  assert.equal(requests[2].body.decision, "approved");
  assert.equal(requests[2].body.expected_revision, 1);
  assert.notEqual(
    requests[1].body.idempotency_key,
    requests[2].body.idempotency_key,
  );
});
test("connected upload forwards File to resumable client and blocks unsupported audio", async () => {
  const state = initialWorkspace();
  let uploaded: File | undefined;
  const client = new StudioClient(async (url) =>
    Response.json(
      String(url).endsWith("session")
        ? { owner_id: "fictional-owner" }
        : { id: "default", workspace: state },
    ),
  );
  client.uploadFile = async (command) => {
    uploaded = command.file;
    assert.equal(command.expected_revision, 0);
    return { ...state, revision: 1 };
  };
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.click(screen.getByRole("button", { name: "References" }));
  const file = new window.File(["abc"], "character.png", { type: "image/png" });
  fireEvent.change(screen.getByLabelText("Add image or soundtrack"), {
    target: { files: [file] },
  });
  await waitFor(() => assert.equal(uploaded, file));
  await waitFor(() =>
    assert.ok(!screen.queryByRole("button", { name: "Retry pending command" })),
  );
  assert.equal(localStorage.length, 0);
  uploaded = undefined;
  fireEvent.change(screen.getByLabelText("Add image or soundtrack"), {
    target: {
      files: [
        new window.File(["abc"], "unsupported.ogg", { type: "audio/ogg" }),
      ],
    },
  });
  await screen.findByRole("alert");
  assert.equal(uploaded, undefined);
});
test("timeline soundtrack export and polling expose protected download", async () => {
  const original = initialWorkspace();
  const state = structuredClone(original);
  state.projects[0].bundle.timelines = [];
  state.projects[0].bundle.exports = [];
  const requests: { url: string; body: Record<string, unknown> }[] = [];
  let queued = false;
  const client = new StudioClient(async (url, init) => {
    if (String(url).endsWith("session"))
      return Response.json({ owner_id: "fictional-owner" });
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      requests.push({ url: String(url), body });
      if (String(url).endsWith("/timelines")) {
        state.projects[0].bundle.timelines = structuredClone(
          original.projects[0].bundle.timelines,
        );
        state.revision++;
      } else {
        state.projects[0].bundle.exports = [
          {
            ...original.projects[0].bundle.exports[0],
            state: "queued",
            output_asset_id: null,
          },
        ];
        queued = true;
      }
      return Response.json({ workspace: state });
    }
    if (queued) {
      state.projects[0].bundle.exports[0].state = "succeeded";
      state.projects[0].bundle.exports[0].output_asset_id = "asset-video";
    }
    return Response.json({ id: "default", workspace: state });
  });
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.click(screen.getByRole("button", { name: "Timeline and export" }));
  fireEvent.input(screen.getByLabelText("Timeline soundtrack"), {
    target: { value: "asset-audio" },
  });
  fireEvent.change(screen.getByLabelText("Timeline soundtrack"), {
    target: { value: "asset-audio" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Assemble selected takes" }),
  );
  await screen.findByRole("button", { name: "Export revision 1" });
  assert.equal(requests[0].body.audio_asset_id, "asset-audio");
  fireEvent.click(screen.getByRole("button", { name: "Export revision 1" }));
  const download = await screen.findByRole(
    "link",
    { name: "Download MP4" },
    { timeout: 3000 },
  );
  assert.ok(
    download.getAttribute("href")!.endsWith("/assets/asset-video/content"),
  );
  assert.ok(download.hasAttribute("download"));
  assert.equal(requests[1].body.timeline_revision, 1);
  assert.ok(screen.getByRole("heading", { name: "Timeline and export" }));
});
test("upload locks creator editing immediately and retries the same File", async () => {
  const state = initialWorkspace();
  let rejectUpload: ((reason: unknown) => void) | undefined;
  const received: File[] = [];
  const client = new StudioClient(async (url) =>
    Response.json(
      String(url).endsWith("session")
        ? { owner_id: "fictional-owner" }
        : { id: "default", workspace: state },
    ),
  );
  client.uploadFile = async (command) => {
    received.push(command.file);
    if (received.length === 1)
      return new Promise((_resolve, reject) => {
        rejectUpload = reject;
      });
    return state;
  };
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.click(screen.getByRole("button", { name: "References" }));
  const file = new window.File(["abc"], "song.wav", { type: "audio/x-wav" });
  fireEvent.change(screen.getByLabelText("Add image or soundtrack"), {
    target: { files: [file] },
  });
  assert.equal(
    screen.getByLabelText("Script or creative brief").closest("main")
      ?.parentElement?.parentElement?.tagName,
    "FIELDSET",
  );
  assert.ok(
    screen.getByLabelText("Script or creative brief").matches(":disabled"),
  );
  await act(async () => rejectUpload!(new Error("interrupted")));
  fireEvent.click(
    screen.getByRole("button", { name: "Retry pending command" }),
  );
  await waitFor(() =>
    assert.ok(!screen.queryByRole("button", { name: "Retry pending command" })),
  );
  assert.equal(received.length, 2);
  assert.equal(received[0], file);
  assert.equal(received[1], file);
  assert.equal(localStorage.length, 0);
});
test("upload identity survives session expiry and reauthentication", async () => {
  const state = initialWorkspace();
  const commands: object[] = [];
  const client = new StudioClient(async (url) =>
    Response.json(
      String(url).endsWith("session")
        ? { owner_id: "fictional-owner" }
        : { id: "default", workspace: state },
    ),
  );
  client.uploadFile = async (command) => {
    commands.push(command);
    if (commands.length === 1) {
      command.uploadId = "staged-upload";
      throw new StudioError(401);
    }
    assert.equal(command.uploadId, "staged-upload");
    return state;
  };
  render(<ConnectedStudio client={client} />);
  await screen.findByLabelText("Shot prompt");
  fireEvent.click(screen.getByRole("button", { name: "References" }));
  fireEvent.change(screen.getByLabelText("Add image or soundtrack"), {
    target: {
      files: [new window.File(["abc"], "song.wav", { type: "audio/wav" })],
    },
  });
  await screen.findByLabelText("Server access token");
  assert.ok(
    (
      screen.getByRole("button", {
        name: "Retry pending command",
      }) as HTMLButtonElement
    ).disabled,
  );
  fireEvent.change(screen.getByLabelText("Server access token"), {
    target: { value: "fictional-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Connect" }));
  await screen.findByLabelText("Shot prompt");
  fireEvent.click(
    screen.getByRole("button", { name: "Retry pending command" }),
  );
  await waitFor(() =>
    assert.ok(!screen.queryByRole("button", { name: "Retry pending command" })),
  );
  assert.equal(commands.length, 2);
  assert.equal(commands[0], commands[1]);
  assert.equal(localStorage.length, 0);
});
