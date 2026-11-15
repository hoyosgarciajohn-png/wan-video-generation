// From apps/studio: node --import tsx ../../scripts/check_studio_client.mjs
// Actual TypeScript client + Python HTTP server. No browser or cloud is implied.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { StudioClient } from '../apps/studio/src/api.ts';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const directory = await mkdtemp(join(tmpdir(), 'wan-client-'));
const token = 'synthetic-owner-token-for-local-test-only';
const origin = 'http://127.0.0.1:5173';
const script = `
import os, threading
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.http_api import StudioAPI, make_server
from services.controller.runner import FixtureRunner
c=ControlService(os.environ['WAN_TEST_DB'], os.environ['WAN_TEST_ASSETS'])
s=make_server(StudioAPI(StudioWorkspace(c), {os.environ['WAN_TEST_TOKEN']:'client-owner'}), ('127.0.0.1',0))
threading.Thread(target=FixtureRunner(c).serve,args=(threading.Event(),),daemon=True).start()
print(s.server_port, flush=True)
s.serve_forever()
`;
const server = spawn('python', ['-c', script], {
  cwd: root, stdio: ['ignore', 'pipe', 'pipe'],
  env: { ...process.env, WAN_TEST_DB: join(directory, 'state.sqlite'),
    WAN_TEST_ASSETS: join(directory, 'assets'), WAN_TEST_TOKEN: token },
});
let stderr = '';
server.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
const lines = createInterface({ input: server.stdout });
let timer;
try {
  const port = await Promise.race([
    once(lines, 'line').then(([line]) => Number(line)),
    once(server, 'exit').then(() => { throw new Error('Server exited: ' + stderr); }),
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Server startup timeout')), 10000); }),
  ]);
  clearTimeout(timer);
  assert.ok(port > 0);
  let cookie = '';
  const browserLikeTransport = async (path, init) => {
    const headers = { ...init.headers, Origin: origin, ...(cookie ? { Cookie: cookie } : {}) };
    const response = await fetch(`http://127.0.0.1:${port}${path}`, { ...init, headers });
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) cookie = setCookie.split(';')[0];
    return response;
  };
  const client = new StudioClient(browserLikeTransport);
  await assert.rejects(client.load(), (error) => error.code === 401);
  assert.equal((await client.login(token)).owner_id, 'client-owner');
  assert.equal((await client.load()).projects.length, 0);
  let workspace = await client.create('Connected synthetic project', 'music_video', 0);
  const project = workspace.projects[0];
  project.script = 'Synthetic script persisted through the actual client.';
  const fixture = JSON.parse(await readFile(join(root, 'fixtures/project.json'), 'utf8'));
  project.bundle.shots = [{ ...fixture.shots[0], project_id: project.bundle.project.id,
    scene_id: project.scenes[0].id }];
  workspace = await client.save(workspace);
  const stale = structuredClone(workspace);
  workspace.projects[0].scenes[0].title = 'Updated opening';
  workspace = await client.save(workspace);
  await assert.rejects(client.save(stale), (error) => error.code === 409);
  const loaded = await client.load();
  assert.equal(loaded.projects[0].script, project.script);
  assert.equal(loaded.projects[0].bundle.shots.length, 1);
  assert.equal(loaded.projects[0].scenes[0].title, 'Updated opening');
  assert.equal(loaded.projects[0].bundle.project.owner_id, 'client-owner');
  assert.equal(loaded.projects[0].bundle.takes.length, 0);
  const projectId = loaded.projects[0].bundle.project.id;
  const submit = { kind: 'submit', projectId, shot_ids: ['shot-1'],
    expected_revision: loaded.revision, idempotency_key: 'actual-client-render-1' };
  let rendered = await client.command(submit);
  const batchId = rendered.projects[0].bundle.batches[0].id;
  const deadline = Date.now() + 15000;
  while (rendered.projects[0].bundle.batches[0].state === 'rendering' && Date.now() < deadline) {
    await new Promise((done) => setTimeout(done, 100));
    rendered = await client.load();
  }
  assert.equal(rendered.projects[0].bundle.batches[0].state, 'succeeded');
  assert.equal(rendered.projects[0].bundle.takes.length, 1);
  const replay = await client.command(submit);
  assert.equal(replay.projects[0].bundle.batches.length, 1);
  assert.equal(replay.projects[0].bundle.batches[0].id, batchId);
  const take = rendered.projects[0].bundle.takes[0];
  const media = await browserLikeTransport(rendered.projects[0].media[take.asset_id], { method: 'GET', headers: {} });
  assert.equal(media.status, 200);
  assert.equal(media.headers.get('content-type'), 'video/mp4');
  assert.ok((await media.arrayBuffer()).byteLength > 1000);
  const review = { kind: 'review', projectId, takeId: take.id, decision: 'approved',
    expected_revision: rendered.revision, idempotency_key: 'actual-client-review-1' };
  const reviewed = await client.command(review);
  assert.equal(reviewed.projects[0].selectedTakes['shot-1'], take.id);
  const repeated = await client.command(review);
  assert.equal(repeated.projects[0].bundle.reviews.length, 1);
  assert.equal(repeated.revision, reviewed.revision);
  const cancelCandidate = await client.command({ ...submit, expected_revision: reviewed.revision,
    idempotency_key: 'actual-client-render-2' });
  const second = cancelCandidate.projects[0].bundle.batches.find((batch) => batch.id !== batchId);
  const canceled = await client.command({ kind: 'cancel', projectId, batchId: second.id });
  assert.ok(['canceled', 'succeeded'].includes(canceled.projects[0].bundle.batches.find((batch) => batch.id === second.id).state));
  // Completion can win the race; deterministic pre-claim cancellation is covered in Python.
  await client.logout();
  await assert.rejects(client.load(), (error) => error.code === 401);
  console.log('PASS: actual StudioClient login/save/render/download/review/replay/cancel/logout over local HTTP');
} finally {
  clearTimeout(timer);
  lines.close();
  if (server.exitCode === null) {
    const stopped = once(server, 'exit');
    server.kill('SIGTERM');
    await stopped;
  }
  await rm(directory, { recursive: true, force: true });
}
