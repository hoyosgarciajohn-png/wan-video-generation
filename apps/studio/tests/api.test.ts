import { test } from "node:test";
import assert from "node:assert/strict";
import { StudioClient } from "../src/api";
import { initialWorkspace, StudioError } from "../src/model";

test("session and workspace client use same-origin cookies and revision envelopes", async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  const workspace = initialWorkspace();
  const client = new StudioClient(async (url, init) => {
    calls.push({ url: String(url), init });
    return Response.json(
      String(url).endsWith("session")
        ? { owner_id: "fictional-owner" }
        : { id: "default", workspace },
    );
  });
  await client.login("fictional-test-token");
  assert.deepEqual(await client.load(), workspace);
  await client.create("Story", "cartoon", 0);
  await client.save(workspace);
  await client.logout();
  assert.deepEqual(
    calls.map((c) => [c.url, c.init?.method]),
    [
      ["/v1/studio/session", "POST"],
      ["/v1/studio/workspaces/default", "GET"],
      ["/v1/studio/workspaces", "POST"],
      ["/v1/studio/workspaces/default", "PUT"],
      ["/v1/studio/session", "DELETE"],
    ],
  );
  for (const { init } of calls) {
    assert.equal(init?.credentials, "same-origin");
    assert.equal(init?.cache, "no-store");
    if (init?.method !== "GET")
      assert.equal(
        (init?.headers as Record<string, string>)["X-WAN-Request"],
        "studio",
      );
  }
  assert.deepEqual(JSON.parse(String(calls[3].init?.body)), {
    expected_revision: 0,
    workspace,
  });
  assert.ok(
    calls
      .slice(1)
      .every((c) => !JSON.stringify(c).includes("fictional-test-token")),
  );
});
test("client preserves safe HTTP status and masks network/server details", async () => {
  for (const status of [401, 404, 409, 422, 503]) {
    const client = new StudioClient(
      async () => new Response("private details", { status }),
    );
    await assert.rejects(
      client.load(),
      (e) =>
        e instanceof StudioError &&
        e.code === status &&
        !e.message.includes("private"),
    );
  }
  const offline = new StudioClient(async () => {
    throw new Error("private host");
  });
  await assert.rejects(
    offline.session(),
    (e) => e instanceof StudioError && e.code === 503,
  );
  const html = new StudioClient(
    async () => new Response("<html>wrong server</html>"),
  );
  await assert.rejects(
    html.load(),
    (e) => e instanceof StudioError && e.code === 503,
  );
});
