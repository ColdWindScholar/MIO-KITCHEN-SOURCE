# tool.spec

# -*- mode: python ; coding: utf-8 -*-

# УДАЛИТЕ ЭТУ СТРОКУ, ЕСЛИ НЕ ИСПОЛЬЗУЕТЕ SPLASH ИЗ .SPEC:
# from PyInstaller.utils.hooks import Splash # НЕПРАВИЛЬНЫЙ ИМПОРТ БЫЛ ЗДЕСЬ
# ПРАВИЛЬНЫЙ ИМПОРТ ДЛЯ SPLASH (если нужен): from PyInstaller.ूद import Splash
# НО ЕСЛИ ВЫ НЕ ОПРЕДЕЛЯЕТЕ ОБЪЕКТ SPLASH НИЖЕ, ЭТОТ ИМПОРТ НЕ НУЖЕН.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ANALYSIS_TARGET_SCRIPT = ['tool.py']
ANALYSIS_PATHEX = ['src']

ANALYSIS_DATAS = [
    ('LICENSE', '.'),
    ('README.md', '.'),
]
ANALYSIS_DATAS += collect_data_files('PIL', include_py_files=True)
ANALYSIS_DATAS += collect_data_files('sv_ttk')
ANALYSIS_DATAS += collect_data_files('chlorophyll')

HIDDEN_IMPORTS = [
    'PIL', 'PIL._imaging', 'PIL._imagingtk', 'PIL.ImageTk', 'PIL._tkinter_finder',
    'tkinterdnd2',
    'pygments.lexers',
]
HIDDEN_IMPORTS += collect_submodules('requests')
HIDDEN_IMPORTS += collect_submodules('core')
HIDDEN_IMPORTS += collect_submodules('tkui')

EXCLUDES = ['numpy']

a = Analysis(
    ANALYSIS_TARGET_SCRIPT,
    pathex=ANALYSIS_PATHEX,
    binaries=[],
    datas=ANALYSIS_DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

EXE_APP_NAME = 'tool'
EXE_ICON_PATH = 'icon.ico'

exe = EXE(
    pyz,
    a.scripts,
    name=EXE_APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    windowed=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=EXE_ICON_PATH
    # Если вы НЕ используете сплэш из .spec, здесь не должно быть параметра splash=
)

APP_COLLECTION_NAME = 'MIO-Kitchen-AppBase'

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_COLLECTION_NAME
)
