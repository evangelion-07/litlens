const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');
const { isSafeExternal } = require('./links.cjs');

let backend, window, quitting = false, base, backendError = '';
if (process.env.LITLENS_SMOKE_TEST === '1' && process.env.LITLENS_DATA_DIR) {
  const smokeData = path.join(process.env.LITLENS_DATA_DIR, 'electron');
  fs.mkdirSync(smokeData, {recursive: true});
  app.setPath('userData', smokeData);
}
const acquired = app.requestSingleInstanceLock();
if (!acquired) app.quit();
app.on('second-instance', () => { if (window) { window.restore(); window.focus(); } });

async function availablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => { const port = server.address().port; server.close(() => resolve(port)); });
  });
}

async function start() {
  const root = path.resolve(__dirname, '..');
  const data = process.env.LITLENS_DATA_DIR || (app.isPackaged ? path.join(app.getPath('userData'), 'data') : path.join(root, 'data'));
  fs.mkdirSync(data, { recursive: true });
  const frontend = app.isPackaged ? path.join(process.resourcesPath, 'frontend') : path.join(root, 'frontend', 'dist');
  const icon = app.isPackaged ? path.join(process.resourcesPath, 'assets', 'litlens.ico') : path.join(root, 'assets', 'litlens.ico');
  const executable = app.isPackaged ? path.join(process.resourcesPath, 'backend', 'litlens-backend.exe') : path.join(root, 'backend', '.venv', 'Scripts', 'python.exe');
  const port = await availablePort();
  base = `http://127.0.0.1:${port}`;
  const secret = crypto.randomBytes(32).toString('hex');
  backend = spawn(executable, app.isPackaged ? [] : [path.join(root, 'backend', 'desktop_entry.py')], {
    cwd: app.isPackaged ? app.getPath('userData') : path.join(root, 'backend'),
    windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, LITLENS_PORT: String(port), LITLENS_DATA_DIR: data,
      LITLENS_DATABASE_PATH: '', LITLENS_FRONTEND_DIR: frontend,
      LITLENS_DESKTOP_SECRET: secret, PYTHONUTF8: '1' },
  });
  backend.on('error', error => { backendError = error.message; });
  backend.stderr.on('data', chunk => { backendError = (backendError + chunk.toString()).slice(-2000); });
  backend.stdout.on('data', () => {});
  backend.on('exit', () => {
    if (!quitting && window) {
      dialog.showErrorBox('LitLens service stopped', 'Please restart LitLens. Your saved papers are still available.');
      app.quit();
    }
  });
  let ready = false;
  for (let i = 0; i < 120; i++) {
    if (backend.exitCode !== null) break;
    try { const r = await fetch(base + '/health', { signal: AbortSignal.timeout(800) }); if (r.ok) { ready = true; break; } } catch {}
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  if (!ready) throw new Error('Could not start the local research service. ' + backendError);
  window = new BrowserWindow({ width: 1440, height: 940, minWidth: 1050, minHeight: 700, icon,
    title: 'LitLens', backgroundColor: '#f4f6f8', show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), nodeIntegration: false,
      contextIsolation: true, sandbox: true, webSecurity: true },
  });
  window.removeMenu();
  const session = window.webContents.session;
  session.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  session.webRequest.onBeforeSendHeaders({ urls: [base + '/*'] }, (details, callback) => {
    details.requestHeaders['X-LitLens-Desktop'] = secret;
    callback({ requestHeaders: details.requestHeaders });
  });
  session.webRequest.onHeadersReceived({ urls: [base + '/*'] }, (details, callback) => {
    callback({ responseHeaders: { ...details.responseHeaders,
      'Content-Security-Policy': ["default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-src 'self' blob:"],
    } });
  });
  window.webContents.setWindowOpenHandler(({ url }) => { if (isSafeExternal(url)) void shell.openExternal(url); return { action: 'deny' }; });
  window.webContents.on('will-navigate', (event, url) => { if (new URL(url).origin !== base) { event.preventDefault(); if (isSafeExternal(url)) void shell.openExternal(url); } });
  ipcMain.handle('open-external', async (event, url) => {
    if (event.sender !== window.webContents || typeof url !== 'string' || !isSafeExternal(url)) return false;
    await shell.openExternal(url); return true;
  });
  await window.loadURL(base);
  if (process.env.LITLENS_SMOKE_TEST !== '1') window.show();
}
if (acquired) app.whenReady().then(start).catch(error => { dialog.showErrorBox('LitLens could not open', error.message); app.quit(); });
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { quitting = true; if (backend && backend.exitCode === null) backend.kill(); });
