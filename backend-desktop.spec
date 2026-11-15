from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('pymupdf')
a = Analysis(['backend/desktop_entry.py'], pathex=['backend'],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports + [
                 'app.main', 'uvicorn.logging', 'uvicorn.loops.auto',
                 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto',
                 'uvicorn.lifespan.on', 'anyio._backends._asyncio'],
             excludes=['tkinter', 'unittest'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='litlens-backend',
          console=True, debug=False)
coll = COLLECT(exe, a.binaries, a.datas, name='litlens-backend')
