# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('D:\\DevProgramme\\ffmpeg-7.1.1-full_build\\ffmpeg-7.1.1-full_build\\bin\\ffmpeg.exe', '.')],
    datas=[('D:\\CSGO2_projekt\\CSGO_REC_PY\\CSGO_REC_AI\\CSGO_REC_AI\\Ressourcen\\kill_signs', 'Ressourcen/kill_signs')],
    hiddenimports=['PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets.QMainWindow', 'PySide6.QtWidgets.QVBoxLayout', 'PySide6.QtWidgets.QHBoxLayout', 'PySide6.QtWidgets.QWidget', 'PySide6.QtWidgets.QPushButton', 'PySide6.QtWidgets.QLineEdit', 'PySide6.QtWidgets.QLabel', 'PySide6.QtWidgets.QCheckBox', 'PySide6.QtWidgets.QTextEdit', 'PySide6.QtWidgets.QFileDialog', 'PySide6.QtWidgets.QSpinBox', 'PySide6.QtWidgets.QGroupBox', 'PySide6.QtWidgets.QGridLayout', 'easyocr', 'torch', 'torchvision', 'PIL', 'websockets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
