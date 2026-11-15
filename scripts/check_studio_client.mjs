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
import os
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.http_api import StudioAPI, make_server
c=ControlService(os.environ['WAN_TEST_DB'], os.environ['WAN_TEST_ASSETS'])
s=make_server(StudioAPI(StudioWorkspace(c), {os.environ['WAN_TEST_TOKEN']:'client-owner'}), ('127.0.0.1',0))
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
  await client.logout();
  await assert.rejects(client.load(), (error) => error.code === 401);
  console.log('PASS: actual StudioClient login/create/edit/save/conflict/load/logout over local HTTP');
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
