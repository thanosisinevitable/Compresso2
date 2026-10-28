import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { randomBytes } from 'node:crypto';
import { existsSync } from 'node:fs';
import path from 'node:path';

export class Backend {
  constructor(root, resources, packaged) {
    this.root = root; this.resources = resources; this.packaged = packaged;
    this.child = null; this.port = null; this.token = randomBytes(32).toString('hex');
    this.error = null;
  }
  async start() {
    const python = process.env.COMPRESSO_PYTHON || path.join(this.root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    const executable = this.packaged ? path.join(this.resources, 'backend', process.platform === 'win32' ? 'compresso-backend.exe' : 'compresso-backend') : python;
    if (!existsSync(executable)) throw new Error('Python backend is missing. Run the setup commands in README.md first.');
    const gsRoot = path.join(this.resources, 'ghostscript');
    const env = { ...process.env, COMPRESSO_TOKEN: this.token, PYTHONUNBUFFERED: '1',
      PATH: [process.env.PATH, '/opt/homebrew/bin', '/usr/local/bin'].filter(Boolean).join(path.delimiter) };
    if (this.packaged) {
      env.COMPRESSO_GS = path.join(gsRoot, 'bin', 'gs');
      env.GS_LIB = [path.join(gsRoot, 'share', 'Resource', 'Init'), path.join(gsRoot, 'share', 'lib'), path.join(gsRoot, 'share', 'Resource', 'Font')].join(path.delimiter);
      env.GS_FONTPATH = path.join(gsRoot, 'fonts');
    }
    const args = [...(this.packaged ? [] : ['-u', path.join(this.root, 'backend/main.py')]), '--parent-pid', String(process.pid)];
    this.child = spawn(executable, args, { env, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true, detached: process.platform !== 'win32' });
    this.child.stdin.on('error', () => {});
    let diagnostics = '';
    this.child.stderr.on('data', data => { diagnostics = (diagnostics + data.toString()).slice(-6000); });
    this.child.on('exit', () => { this.port = null; this.error = 'The local processing engine stopped. Restart the engine to continue.'; });
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => { this.child?.kill(); reject(new Error('Backend startup timed out. Check the Python environment.')); }, 45000);
      const lines = createInterface({ input: this.child.stdout });
      const fail = error => { clearTimeout(timeout); reject(new Error(`${error.message}\n${diagnostics.slice(-1500)}`)); };
      this.child.once('error', fail);
      this.child.once('exit', code => fail(new Error(`Backend exited during startup (${code}).`)));
      lines.on('line', line => {
        try {
          const message = JSON.parse(line);
          if (message.event === 'ready' && Number.isInteger(message.port)) {
            this.port = message.port; clearTimeout(timeout); resolve();
          }
        } catch { /* Non-protocol log output is ignored. */ }
      });
    });
    let lastError;
    for (let i = 0; i < 60; i++) {
      try { const health = await this.request('/health'); this.error = null; return health; }
      catch (error) { lastError = error; await new Promise(resolve => setTimeout(resolve, 100)); }
    }
    throw lastError;
  }
  async request(route, body, timeout = 30000) {
    if (!this.port) throw new Error(this.error || 'The processing engine is starting.');
    const response = await fetch(`http://127.0.0.1:${this.port}${route}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'x-compresso-token': this.token, 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(timeout),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'The request could not be processed.');
    return result;
  }
  async stop() {
    const child = this.child;
    if (!child || child.exitCode !== null) return;
    child.stdin.end();
    await new Promise(resolve => {
      const timer = setTimeout(() => {
        try { if (process.platform === 'win32') child.kill('SIGKILL'); else process.kill(-child.pid, 'SIGKILL'); } catch { /* Already exited. */ }
        resolve();
      }, 6000);
      child.once('exit', () => { clearTimeout(timer); resolve(); });
    });
    this.child = null; this.port = null;
  }
}
