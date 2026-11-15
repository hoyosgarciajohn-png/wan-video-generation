import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  act,
} from "@testing-library/react";
import axe from "axe-core";
import { App } from "../src/App";
import { STORAGE_KEY } from "../src/model";

afterEach(() => {
  cleanup();
  localStorage.clear();
});
const click = (name: string) =>
  fireEvent.click(screen.getByRole("button", { name }));
const fill = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label, { exact: true }), {
    target: { value },
  });
const saved = () => JSON.parse(localStorage.getItem(STORAGE_KEY)!);

test("DOM creator flow preserves previous selection until explicit replacement", () => {
  render(<App />);
  fill("Shot prompt", "Fictional sunset");
  click("Save new revision");
  assert.equal(saved().projects[0].selectedTakes["shot-1"], "take-1");
  fireEvent.click(screen.getByLabelText("Select Fictional sunset"));
  click("Review render batch");
  click("Approve batch");
  click("Simulate failure");
  click("Prepare unfinished shots again");
  click("Review render batch");
  click("Approve batch");
  click("Advance fixture");
  click("Advance fixture");
  click("Take review");
  const buttons = screen.getAllByRole("button", {
    name: "Use this take instead",
  });
  fireEvent.click(buttons.find((b) => !(b as HTMLButtonElement).disabled)!);
  const state = saved();
  assert.notEqual(state.projects[0].selectedTakes["shot-1"], "take-1");
  assert.equal(
    state.projects[0].bundle.timelines[0].items[0].take_id,
    "take-1",
  );
  assert.equal(state.projects[0].bundle.takes.length, 2);
  cleanup();
  render(<App />);
  click("Take review");
  assert.equal(screen.getAllByText("Accepted selection").length, 1);
});
test("DOM project creation, scenes, editing, script and isolation", () => {
  render(<App />);
  for (const kind of ["music_video", "short_film", "cartoon"]) {
    click("New project");
    fill("Project title", "Fictional " + kind);
    fill("Project type", kind);
    click("Create project");
    fill("New scene", "Forest");
    click("Add scene");
    const state = saved();
    const p = state.projects.at(-1);
    fill("Scene", p.scenes[1].id);
    fill("Shot prompt", "Fictional owl");
    click("Add shot");
  }
  click("References");
  fill("Script or creative brief", "A fictional forest story.");
  const state = saved();
  assert.equal(state.projects.length, 4);
  assert.equal(
    state.projects[0].bundle.shots[0].prompt,
    "A blue studio backdrop",
  );
  assert.equal(
    state.projects[3].bundle.shots[0].scene_id,
    state.projects[3].scenes[1].id,
  );
  cleanup();
  render(<App />);
  fill("Project", state.projects[3].bundle.project.id);
  click("References");
  assert.equal(
    (screen.getByLabelText("Script or creative brief") as HTMLTextAreaElement)
      .value,
    "A fictional forest story.",
  );
});
test("DOM storage conflict disables edits and announces recovery", () => {
  render(<App />);
  act(() =>
    window.dispatchEvent(
      new StorageEvent("storage", { key: STORAGE_KEY, newValue: "{}" }),
    ),
  );
  assert.match(screen.getByRole("alert").textContent!, /newer version/);
  assert.equal(
    screen
      .getByRole("button", { name: "Save new revision" })
      .closest("fieldset")?.disabled,
    true,
  );
  assert.ok(screen.getByRole("button", { name: "Reload saved version" }));
});
test("DOM failed save presents error and retains saved revision", () => {
  render(<App />);
  fill("Shot prompt", "Saved fictional prompt");
  click("Save new revision");
  const before = localStorage.getItem(STORAGE_KEY);
  const prototype = Object.getPrototypeOf(localStorage);
  const original = prototype.setItem;
  try {
    prototype.setItem = () => {
      throw new Error("quota");
    };
    fill("Shot prompt", "Unsaved fictional prompt");
    click("Save new revision");
    assert.match(screen.getByRole("alert").textContent!, /storage is full/);
    assert.equal(localStorage.getItem(STORAGE_KEY), before);
  } finally {
    prototype.setItem = original;
  }
});
test("DOM accessibility rules pass across all sections", async () => {
  render(<App />);
  for (const section of [
    "Storyboard",
    "References",
    "Render batches",
    "Take review",
  ]) {
    click(section);
    const results = await axe.run(document.body, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      rules: { "color-contrast": { enabled: false } },
    });
    assert.deepEqual(
      results.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.html),
      })),
      [],
    );
  }
});
