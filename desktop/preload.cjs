const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('litlens', {
  desktop: true,
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
});
