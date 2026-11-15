import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { resolve } from "node:path";

test("edit, freeze, fail, retry, approve, reload and retain history", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Shot prompt").fill("Fictional sunrise");
  await page.getByRole("button", { name: "Save new revision" }).click();
  await expect(
    page.getByText("Accepted take saved", { exact: false }),
  ).toBeVisible();
  await page.getByLabel("Select Fictional sunrise").check();
  await page.getByRole("button", { name: "Review render batch" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("button", { name: "Approve batch", exact: true })
    .click();
  await page.getByRole("button", { name: "Simulate failure" }).click();
  await page
    .getByRole("button", { name: "Prepare unfinished shots again" })
    .click();
  await page.getByRole("button", { name: "Review render batch" }).click();
  await page
    .getByRole("button", { name: "Approve batch", exact: true })
    .click();
  await page.getByRole("button", { name: "Advance fixture" }).click();
  await page.getByRole("button", { name: "Advance fixture" }).click();
  await page.getByRole("button", { name: "Take review", exact: true }).click();
  await expect(
    page.getByText("Accepted selection", { exact: true }),
  ).toHaveCount(1);
  const newTake = page.locator(".takes article").last();
  await newTake.getByRole("button", { name: "Use this take instead" }).click();
  await expect(newTake.getByText("Accepted selection")).toBeVisible();
  const before = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("wan-studio.fixture.0.1.0")!),
  );
  await page.reload();
  const after = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("wan-studio.fixture.0.1.0")!),
  );
  expect(after).toEqual(before);
  expect(after.projects[0].bundle.timelines[0].items[0].take_id).toBe("take-1");
  expect(after.projects[0].bundle.takes).toHaveLength(2);
  expect(
    after.projects[0].bundle.batches.at(-1).shot_snapshots[0].revision,
  ).toBe(2);
  await page.getByRole("button", { name: "Take review", exact: true }).click();
  await page
    .locator("video")
    .last()
    .evaluate(async (video: HTMLVideoElement) => {
      await video.play();
    });
  await expect
    .poll(() =>
      page
        .locator("video")
        .last()
        .evaluate((v: HTMLVideoElement) => v.currentTime),
    )
    .toBeGreaterThan(0);
});

test("three formats, project isolation, scene editing and references survive reload", async ({
  page,
}) => {
  await page.goto("/");
  for (const kind of ["music_video", "short_film", "cartoon"]) {
    await page
      .getByRole("button", { name: "New project", exact: true })
      .click();
    await page
      .getByLabel("Project title", { exact: true })
      .fill("Fictional " + kind);
    await page.getByLabel("Project type", { exact: true }).selectOption(kind);
    await page
      .getByRole("button", { name: "Create project", exact: true })
      .click();
    await page.getByLabel("New scene", { exact: true }).fill("Forest");
    await page.getByRole("button", { name: "Add scene", exact: true }).click();
    await page
      .getByLabel("Scene", { exact: true })
      .selectOption({ label: "Forest" });
    await page.getByLabel("Shot prompt").fill("Fictional owl");
    await page.getByRole("button", { name: "Add shot", exact: true }).click();
  }
  await page.getByRole("button", { name: "References", exact: true }).click();
  await page
    .getByLabel("Script or creative brief")
    .fill("Fictional forest story.");
  await page.getByLabel("Add image or soundtrack").setInputFiles({
    name: "character.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=",
      "base64",
    ),
  });
  await expect(page.getByAltText("character.png")).toBeVisible();
  await page
    .getByLabel("Add image or soundtrack")
    .setInputFiles(resolve("../../fixtures/media/audio.wav"));
  await expect(page.getByRole("status").first()).toContainText(
    "Reference saved",
  );
  await page.getByRole("button", { name: "Storyboard", exact: true }).click();
  await page.getByLabel("character.png").check();
  await page.getByRole("button", { name: "Save new revision" }).click();
  const data = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("wan-studio.fixture.0.1.0")!),
  );
  expect(data.projects).toHaveLength(4);
  expect(data.projects[0].bundle.shots[0].prompt).toBe(
    "A blue studio backdrop",
  );
  expect(data.projects[3].bundle.shots[0].reference_asset_ids).toHaveLength(1);
  await page.reload();
  await page
    .getByLabel("Project", { exact: true })
    .selectOption({ label: "Fictional cartoon" });
  await page.getByRole("button", { name: "References", exact: true }).click();
  await expect(page.getByAltText("character.png")).toBeVisible();
  await expect(page.getByLabel("Script or creative brief")).toHaveValue(
    "Fictional forest story.",
  );
});

test("keyboard, dialog focus, accessibility and narrow layouts", async ({
  page,
}) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to workspace" }),
  ).toBeFocused();
  for (const name of [
    "Storyboard",
    "References",
    "Render batches",
    "Take review",
  ]) {
    await page.getByRole("button", { name, exact: true }).click();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  }
  await page.getByRole("button", { name: "Storyboard", exact: true }).click();
  await page.getByLabel("Select A blue studio backdrop").check();
  await page.getByRole("button", { name: "Review render batch" }).click();
  await expect(
    page.getByRole("button", { name: "Approve batch", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Review render batch" }),
  ).toBeFocused();
  for (const width of [720, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/studio-${width}.png`,
      fullPage: true,
    });
  }
});

test("another tab triggers a recoverable revision conflict", async ({
  page,
  context,
}) => {
  await page.goto("/");
  const other = await context.newPage();
  await other.goto("/");
  await other.getByLabel("Shot prompt").fill("Other fictional editor");
  await other.getByRole("button", { name: "Save new revision" }).click();
  await expect(page.getByRole("alert")).toContainText("A newer version");
  await expect(
    page.getByRole("button", { name: "Save new revision" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Reload saved version" }).click();
  await expect(page.getByLabel("Shot prompt")).toHaveValue(
    "Other fictional editor",
  );
});
