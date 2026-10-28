const { contextBridge, ipcRenderer, webUtils } = require('electron');
contextBridge.exposeInMainWorld('compresso', {
  platform: process.platform,
  health: () => ipcRenderer.invoke('engine:health'),
  restart: () => ipcRenderer.invoke('engine:restart'),
  choose: kind => ipcRenderer.invoke('files:choose', kind),
  drop: files => ipcRenderer.invoke('files:drop', Array.from(files, file => webUtils.getPathForFile(file))),
  start: request => ipcRenderer.invoke('job:start', request),
  status: id => ipcRenderer.invoke('job:status', id),
  cancel: id => ipcRenderer.invoke('job:cancel', id),
  thumbnail: (id, path) => ipcRenderer.invoke('file:thumbnail', id, path),
  preview: path => ipcRenderer.invoke('file:preview', path),
  reveal: path => ipcRenderer.invoke('file:reveal', path),
  lens: (id, index, gain) => ipcRenderer.invoke('lens:start', id, index, gain),
  asset: (id, key) => ipcRenderer.invoke('lens:asset', id, key),
  save: id => ipcRenderer.invoke('result:save', id),
  trash: (id, paths) => ipcRenderer.invoke('files:trash', id, paths),
});
