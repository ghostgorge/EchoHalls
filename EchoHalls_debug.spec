# -*- mode: python ; coding: utf-8 -*-
# 分流用：onedir + console。debug 能跑而单文件不能 -> 问题在解压到 %TEMP%；
# debug 也挂 -> 控制台会直接给出 traceback。
import os

a = Analysis(['main.py'], pathex=[os.path.abspath('.')], binaries=[], datas=[],
             hiddenimports=[], hookspath=['pyi_hooks'], runtime_hooks=[],
             excludes=['matplotlib', 'scipy', 'pandas', 'PyQt5', 'PyQt6',
                       'PySide2', 'PySide6', 'IPython', 'notebook', 'tkinter',
                       'pythoncom', 'pywintypes', 'win32com', 'win32api',
                       'win32con'],
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='EchoHalls_debug',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False,
               name='EchoHalls_debug')
