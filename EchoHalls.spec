# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[], datas=[], hiddenimports=[],
    hookspath=['pyi_hooks'], hooksconfig={}, runtime_hooks=[],
    # 只排重型第三方库和坏掉的 pywin32；标准库和 setuptools 绝不能排
    excludes=['matplotlib', 'scipy', 'pandas', 'numpy.f2py',
              'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'IPython', 'notebook',
              'tkinter', 'test', 'unittest',
              'pythoncom', 'pywintypes', 'win32com', 'win32api', 'win32con'],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
          name='EchoHalls', debug=False, strip=False, upx=False,
          runtime_tmpdir=None, console=False)
