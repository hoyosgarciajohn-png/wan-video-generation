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
test("server commands preserve identity revision and idempotency", async () => {
  const calls: { url: string; body: unknown }[] = [];
  const client = new StudioClient(async (url, init) => {
    calls.push({ url: String(url), body: JSON.parse(String(init?.body)) });
    return Response.json({ workspace: initialWorkspace() });
  });
  await client.command({
    kind: "submit",
    projectId: "project 1",
    shot_ids: ["shot-1"],
    expected_revision: 7,
    idempotency_key: "same-key",
  });
  await client.command({
    kind: "cancel",
    projectId: "project 1",
    batchId: "batch/1",
  });
  await client.command({
    kind: "review",
    projectId: "project 1",
    takeId: "take 1",
    decision: "approved",
    expected_revision: 8,
    idempotency_key: "review-key",
  });
  assert.deepEqual(calls, [
    {
      url: "/v1/studio/projects/project%201/batches",
      body: {
        shot_ids: ["shot-1"],
        expected_revision: 7,
        idempotency_key: "same-key",
      },
    },
    {
      url: "/v1/studio/projects/project%201/batches/batch%2F1/cancel",
      body: {},
    },
    {
      url: "/v1/studio/projects/project%201/takes/take%201/review",
      body: {
        decision: "approved",
        expected_revision: 8,
        idempotency_key: "review-key",
      },
    },
  ]);
});
test("protected upload timeline and export commands preserve full payload", async () => {
  const bodies: { url: string; body: unknown }[] = [];
  const client = new StudioClient(async (url, init) => {
    bodies.push({ url: String(url), body: JSON.parse(String(init?.body)) });
    return Response.json({ workspace: initialWorkspace() });
  });
  await client.command({
    kind: "upload",
    projectId: "project-1",
    name: "theme.wav",
    mime_type: "audio/wav",
    data_base64: "YWJj",
    expected_revision: 2,
    idempotency_key: "upload-key",
  });
  await client.command({
    kind: "timeline",
    projectId: "project-1",
    audio_asset_id: "audio-1",
    expected_revision: 3,
    idempotency_key: "timeline-key",
  });
  await client.command({
    kind: "export",
    projectId: "project-1",
    timeline_id: "timeline-1",
    timeline_revision: 2,
    idempotency_key: "export-key",
  });
  assert.deepEqual(bodies, [
    {
      url: "/v1/studio/projects/project-1/assets",
      body: {
        name: "theme.wav",
        mime_type: "audio/wav",
        data_base64: "YWJj",
        expected_revision: 2,
        idempotency_key: "upload-key",
      },
    },
    {
      url: "/v1/studio/projects/project-1/timelines",
      body: {
        audio_asset_id: "audio-1",
        expected_revision: 3,
        idempotency_key: "timeline-key",
      },
    },
    {
      url: "/v1/studio/projects/project-1/exports",
      body: {
        timeline_id: "timeline-1",
        timeline_revision: 2,
        idempotency_key: "export-key",
      },
    },
  ]);
});
test("chunk upload resumes committed chunks and ambiguous finish with bounded reads", async () => {
  const chunkSize = 1024 * 1024;
  const source = new Uint8Array(5 * chunkSize + 3).fill(23);
  const file = new File([source], "long-song.wav", { type: "audio/x-wav" });
  const slice = file.slice.bind(file);
  let maximumRead = 0;
  file.arrayBuffer = async () => {
    throw new Error("whole file read forbidden");
  };
  file.slice = (start, end, type) => {
    const part = slice(start, end, type);
    maximumRead = Math.max(maximumRead, part.size);
    assert.ok(part.size <= chunkSize);
    return part;
  };
  let session = {
    id: "upload-1",
    state: "uploading",
    bytes: file.size,
    received_bytes: 0,
    chunk_size: chunkSize,
    next_chunk_index: 0,
    chunk_sha256: [] as string[],
  };
  const chunks: number[] = [];
  let creates = 0,
    gets = 0,
    finishes = 0;
  let loseChunkResponse = true,
    loseFinishResponse = true;
  const client = new StudioClient(async (url, init) => {
    assert.equal(init?.credentials, "same-origin");
    const path = String(url);
    if (path.endsWith("/uploads")) {
      creates++;
      const body = JSON.parse(String(init?.body));
      assert.deepEqual(body, {
        name: "long-song.wav",
        mime_type: "audio/wav",
        bytes: file.size,
        expected_revision: 0,
        idempotency_key: "stable-upload",
      });
    } else if (init?.method === "PUT") {
      const index = Number(path.split("/").at(-1));
      chunks.push(index);
      assert.equal(
        (init.headers as Record<string, string>)["Content-Type"],
        "application/octet-stream",
      );
      assert.equal(
        (init.headers as Record<string, string>)["X-WAN-Request"],
        "studio",
      );
      const bytes = await (init.body as Blob).arrayBuffer();
      const hash = Array.from(
        new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      )
        .map((v) => v.toString(16).padStart(2, "0"))
        .join("");
      session.chunk_sha256.push(hash);
      session.next_chunk_index++;
      session.received_bytes += bytes.byteLength;
      if (loseChunkResponse) {
        loseChunkResponse = false;
        throw new Error("response lost after commit");
      }
    } else if (path.endsWith("/finish")) {
      finishes++;
      assert.deepEqual(
        JSON.parse(String(init?.body)).chunk_sha256,
        session.chunk_sha256,
      );
      session.state = "completed";
      if (loseFinishResponse) {
        loseFinishResponse = false;
        throw new Error("finish response lost");
      }
      return Response.json({ workspace: initialWorkspace() });
    } else gets++;
    return Response.json({ upload: session });
  });
  const command = {
    kind: "upload-file" as const,
    projectId: "project-1",
    file,
    expected_revision: 0,
    idempotency_key: "stable-upload",
  };
  await assert.rejects(
    client.command(command),
    (e) => e instanceof StudioError && e.code === 503,
  );
  await assert.rejects(
    client.command(command),
    (e) => e instanceof StudioError && e.code === 503,
  );
  await client.command(command);
  assert.deepEqual(chunks, [0, 1, 2, 3, 4, 5]);
  assert.equal(creates, 1);
  assert.equal(gets, 2);
  assert.equal(finishes, 2);
  assert.equal(maximumRead, chunkSize);
});
test("chunk upload rejects changed prefixes expired sessions and oversize before writes", async () => {
  const file = new File(["abc"], "song.mp3", { type: "audio/mpeg" });
  for (const state of ["uploading", "expired"]) {
    let writes = 0;
    const client = new StudioClient(async (_url, init) => {
      if (init?.method !== "GET") writes++;
      return Response.json({
        upload: {
          id: "u",
          state,
          bytes: 3,
          received_bytes: 3,
          chunk_size: 1048576,
          next_chunk_index: 1,
          chunk_sha256: ["0".repeat(64)],
        },
      });
    });
    await assert.rejects(
      client.command({
        kind: "upload-file",
        projectId: "p",
        file,
        expected_revision: 0,
        idempotency_key: "k",
        uploadId: "u",
      }),
      (e) =>
        e instanceof StudioError &&
        e.code === (state === "expired" ? 410 : 409),
    );
    assert.equal(writes, 0);
  }
  const client = new StudioClient(async () => {
    assert.fail("oversize must not reach server");
  });
  await assert.rejects(
    client.command({
      kind: "upload-file",
      projectId: "p",
      file: { type: "audio/wav", size: 129 * 1048576 } as File,
      expected_revision: 0,
      idempotency_key: "k",
    }),
    (e) => e instanceof StudioError && e.code === 422,
  );
});
