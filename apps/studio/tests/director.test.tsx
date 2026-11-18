import assert from "node:assert/strict";
import { test } from "node:test";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { Director, draftShots } from "../src/Director";

test("director drafts cover the selected interval without timing gaps", () => {
  const shots = draftShots(12000, 72000);
  assert.equal(shots.length, 12);
  assert.equal(shots[0].start_ms, 12000);
  assert.equal(shots.at(-1)!.end_ms, 72000);
  shots.slice(1).forEach((s, i) => assert.equal(s.start_ms, shots[i].end_ms));
  assert.equal(new Set(shots.map((s) => s.camera)).size, 12);
});
test("director persists edits through authenticated endpoint and reveals model limits", async () => {
  const original = globalThis.fetch;
  let saved: any;
  globalThis.fetch = async (input, init) => {
    const path = String(input);
    let data: any;
    if (path.endsWith("/session")) data = { owner_id: "fictional-owner" };
    else if (path.endsWith("/models")) data = { configured: false };
    else if (path.endsWith("/workspaces/default"))
      data = {
        workspace: {
          version: 1,
          revision: 0,
          projects: [
            {
              bundle: {
                project: { id: "project-test", title: "Fictional concert" },
                assets: [],
              },
              assetNames: {},
              media: {},
            },
          ],
        },
      };
    else if (path.endsWith("/director")) {
      if (init?.method === "PUT") {
        saved = JSON.parse(String(init.body));
        data = { revision: 1 };
      } else data = { revision: 0, brief: null };
    } else throw new Error("Unexpected request " + path);
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    const ui = render(<Director />);
    await waitFor(() =>
      assert.ok(ui.getByRole("button", { name: "＋ Create project" })),
    );
    fireEvent.change(ui.getByLabelText("Project"), {
      target: { value: "project-test" },
    });
    await waitFor(() => assert.ok(ui.getByText("Server API key required")));
    fireEvent.change(ui.getByLabelText("Exact model"), {
      target: { value: "kling-image" },
    });
    assert.ok(ui.getByText(/does not accept your song/));
    fireEvent.change(ui.getByLabelText("Your concept"), {
      target: { value: "Fictional edited concept" },
    });
    fireEvent.click(ui.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      assert.equal(saved?.brief.direction, "Fictional edited concept"),
    );
    assert.equal(saved.brief.model_id, "kling-image");
    await waitFor(() => assert.ok(ui.getByText("Saved to your project.")));
    fireEvent.click(ui.getByRole("button", { name: "Build storyboard →" }));
    assert.equal(ui.getAllByLabelText("Action & choreography").length, 12);
  } finally {
    cleanup();
    globalThis.fetch = original;
  }
});
