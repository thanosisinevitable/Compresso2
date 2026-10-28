import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from 'electron';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { promises as fs } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { Backend } from './electron/backend.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
let window, backend, backendReady, quitting = false;
const allowed = new Set(), roots = new Set(), jobIds = new Set();
const devURL = !app.isPackaged && process.env.COMPRESSO_DEV_URL;
const pageURL = devURL || pathToFileURL(path.join(root, 'dist/index.html')).href;

function trusted(event) {
  if (event.sender !== window?.webContents || event.senderFrame !== window.webContents.mainFrame || event.senderFrame.url !== pageURL) {
    throw new Error('Untrusted application window.');
  }
}
async function realFile(value, directory = false) {
  if (typeof value !== 'string' || !path.isAbsolute(value)) throw new Error('Choose a local file.');
  const absolute = path.normalize(value);
  const info = await fs.lstat(absolute);
  if (info.isSymbolicLink() || (directory ? !info.isDirectory() : !info.isFile())) throw new Error(directory ? 'Choose a folder, not a symbolic link.' : 'Choose a regular file, not a folder or symbolic link.');
  // macOS may expose /var via /private/var; normalize picker paths once.
  return { path: await fs.realpath(absolute), name: path.basename(absolute), size: info.size, directory: info.isDirectory() };
}
async function permitted(value) {
  const record = await realFile(value);
  if (!allowed.has(record.path) && ![...roots].some(base => record.path.startsWith(base + path.sep))) throw new Error('Choose this file in Compresso first.');
  return record.path;
}
function checkedJob(id) {
  if (typeof id !== 'string' || !jobIds.has(id)) throw new Error('Unknown operation.');
  return id;
}
function handle(name, fn) { ipcMain.handle(name, (event, ...args) => { trusted(event); return fn(...args); }); }

function registerIPC() {
  handle('engine:health', async () => { await backendReady; return backend.request('/health'); });
  handle('engine:restart', async () => {
    await backend.stop(); jobIds.clear(); backend = new Backend(root, process.resourcesPath, app.isPackaged);
    backendReady = backend.start(); backendReady.catch(() => {}); await backendReady; window.reload(); return true;
  });
  handle('files:choose', async kind => {
    if (!['compress', 'scan', 'entropy', 'target', 'vault-create', 'vault-open'].includes(kind)) throw new Error('Unknown selection.');
    const selection = await dialog.showOpenDialog(window, {
      title: kind === 'scan' ? 'Choose a folder to scan' : 'Choose files',
      properties: kind === 'scan' ? ['openDirectory'] : ['compress','target','vault-create'].includes(kind) ? ['openFile', 'multiSelections'] : ['openFile'],
      ...(kind === 'vault-open' ? {filters:[{name:'Compresso Version Vault',extensions:['cvault']}]} : kind === 'target' ? {filters:[{name:'Single-frame images',extensions:['png','jpg','jpeg','tif','tiff','webp','bmp']}]} : kind === 'compress' ? { filters: [{ name: 'Images, PDFs and ZIP archives', extensions: ['png', 'jpg', 'jpeg', 'tif', 'tiff', 'webp', 'bmp', 'pdf', 'zip'] }] } : {}),
    });
    return Promise.all(selection.filePaths.map(async value => {
      const record = await realFile(value, kind === 'scan'); allowed.add(record.path); return record;
    }));
  });
  handle('files:drop', async values => {
    if (!Array.isArray(values) || !values.length || values.length > 20000) throw new Error('Drop local files or a folder.');
    const records = [];
    for (const value of values) {
      const info = await fs.lstat(value);
      const record = await realFile(value, info.isDirectory()); allowed.add(record.path); records.push(record);
    }
    return records;
  });
  handle('job:start', async request => {
    await backendReady;
    if (!request || !['compress', 'scan', 'entropy', 'target', 'vault-create', 'vault-open', 'vault-restore'].includes(request.kind) || !Array.isArray(request.paths) || !request.paths.length) throw new Error('Invalid operation.');
    for (const value of request.paths) if (!allowed.has(value)) throw new Error('Choose the input in Compresso first.');
    if (request.kind === 'scan') roots.add((await realFile(request.paths[0], true)).path);
    const result = await backend.request('/jobs', request); jobIds.add(result.id); return result;
  });
  handle('job:status', id => backend.request(`/jobs/${checkedJob(id)}`));
  handle('job:cancel', id => backend.request(`/jobs/${checkedJob(id)}/cancel`, {}));
  handle('lens:start', async (parentId, index, gain = 8) => {
    const parent = await backend.request(`/jobs/${checkedJob(parentId)}`);
    if (parent.state !== 'done' || !['compress','target'].includes(parent.kind) || !Number.isInteger(index)) throw new Error('Choose an image output to compare.');
    const pair = parent.result.lensPairs?.[index];
    if (!pair) throw new Error('This output cannot be compared.');
    const result = await backend.request('/jobs', {kind:'lens',paths:[pair.source,pair.output],options:{identity:pair.identity,gain,parentJob:parentId}});
    jobIds.add(result.id); return result;
  });
  handle('lens:asset', (id, key) => backend.request(`/jobs/${checkedJob(id)}/asset`, {key}));
  handle('file:thumbnail', (id, value) => backend.request(`/jobs/${checkedJob(id)}/thumbnail`, { path: value }));
  handle('file:reveal', async value => { shell.showItemInFolder(await permitted(value)); return true; });
  handle('file:preview', async value => {
    const target = await permitted(value);
    if (process.platform === 'darwin') window.previewFile(target);
    else if (['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.pdf', '.txt', '.webp', '.bmp', '.gif'].includes(path.extname(target).toLowerCase())) {
      const error = await shell.openPath(target); if (error) throw new Error(error);
    } else shell.showItemInFolder(target);
    return true;
  });
  handle('result:save', async id => {
    const job = await backend.request(`/jobs/${checkedJob(id)}`);
    if (!['compress','target','vault-create','vault-restore'].includes(job.kind) || job.state !== 'done' || !job.result.artifact) throw new Error('Finish processing with at least one successful output first.');
    const result = job.result;
    const extension = path.extname(result.name);
    const output = await dialog.showSaveDialog(window, { title: 'Save output', defaultPath: job.kind === 'compress' ? path.basename(result.name, extension) + '-compressed' + extension : result.name });
    if (output.canceled || !output.filePath) return null;
    const destination = path.resolve(output.filePath);
    let existing;
    try { existing = await fs.lstat(destination); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (existing?.isSymbolicLink()) throw new Error('Choose a destination that is not a symbolic link.');
    const parent = await fs.realpath(path.dirname(destination));
    const canonical = path.join(parent, path.basename(destination));
    for (const source of result.sources) {
      const info = await fs.stat(source);
      if (canonical === source || (existing && info.ino === existing.ino && info.dev === existing.dev)) throw new Error('Choose a different output name to preserve your original file.');
    }
    const temporary = path.join(parent, `.compresso-${randomUUID()}.tmp`);
    try { await fs.copyFile(result.artifact, temporary); await fs.rename(temporary, destination); }
    finally { await fs.rm(temporary, { force: true }); }
    allowed.add(canonical); return canonical;
  });
  handle('files:trash', async (id, paths) => {
    checkedJob(id);
    if (!Array.isArray(paths) || !paths.length) throw new Error('Select duplicates first.');
    const plan = await backend.request(`/jobs/${id}/cleanup-check`, { paths }, 120000);
    const answer = await dialog.showMessageBox(window, { type: 'warning', title: 'Move selected files to Trash?',
      message: `Move ${plan.files.length} selected file${plan.files.length === 1 ? '' : 's'} to Trash?`,
      detail: `${plan.hasSimilar ? 'This selection includes visually similar images. They may have different content or quality. Review them carefully.\n\n' : ''}At least one file from each affected group will be kept. Files can be restored from Trash. Space is only freed when Trash is emptied.\n\n${plan.files.slice(0, 8).map(f => f.path).join('\n')}${plan.files.length > 8 ? '\n…' : ''}`,
      buttons: ['Cancel', 'Move to Trash'], defaultId: 0, cancelId: 0, noLink: true });
    if (answer.response !== 1) return { cancelled: true, moved: [], errors: [] };
    // Revalidate after the native confirmation; the user may have changed files while it was open.
    const checked = await backend.request(`/jobs/${id}/cleanup-check`, { paths }, 120000);
    const moved = [], errors = [];
    for (const file of checked.files) {
      try {
        const current = await fs.lstat(file.path, { bigint: true });
        const real = await fs.realpath(file.path);
        const [dev, ino, size, mtime, ctime] = file.identity;
        if (real !== file.path || !current.isFile() || [current.dev, current.ino, current.size, current.mtimeNs, current.ctimeNs].some((n, i) => n.toString() !== [dev, ino, size, mtime, ctime][i])) throw new Error('File changed after confirmation; scan again.');
        // Ensure a retained file still exists immediately before each move.
        for (const keeper of file.keepers) {
          const retained = await fs.lstat(keeper.path, { bigint: true });
          if (!retained.isFile() || [retained.dev, retained.ino, retained.size, retained.mtimeNs, retained.ctimeNs].some((n, i) => n.toString() !== keeper.identity[i])) throw new Error('A retained copy changed. Scan again.');
        }
        await shell.trashItem(file.path); moved.push(file.path);
      } catch (error) { errors.push({ path: file.path, error: error.message }); break; }
    }
    return { cancelled: false, moved, errors };
  });
}

function createWindow() {
  window = new BrowserWindow({ width: 1200, height: 850, minWidth: 860, minHeight: 650,
    title: 'Compresso', backgroundColor: '#09090b', titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 20, y: 22 }, autoHideMenuBar: true,
    webPreferences: { preload: path.join(root, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true } });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, url) => { if (url !== pageURL) event.preventDefault(); });
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  if (devURL) window.loadURL(devURL); else window.loadFile(path.join(root, 'dist/index.html'));
  window.on('closed', () => { window = null; });
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } else createWindow(); });
  app.whenReady().then(() => {
    backend = new Backend(root, process.resourcesPath, app.isPackaged);
    backendReady = backend.start(); backendReady.catch(error => { backend.error = error.message; });
    registerIPC();
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      ...(process.platform === 'darwin' ? [{ label: 'Compresso', submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' }, { role: 'unhide' }, { type: 'separator' }, { role: 'quit' }] }] : []),
      { role: 'editMenu' }, { role: 'viewMenu' }, { role: 'windowMenu' },
    ]));
    createWindow();
    app.on('activate', () => { if (!window) createWindow(); });
  });
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
  app.on('before-quit', event => {
    if (quitting) return;
    event.preventDefault(); quitting = true;
    Promise.resolve(backend?.stop()).finally(() => app.quit());
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => app.quit());
}
