import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { ConnectedStudio } from "../src/ConnectedStudio";
import { StudioClient } from "../src/api";
import { initialWorkspace, STORAGE_KEY } from "../src/model";
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
