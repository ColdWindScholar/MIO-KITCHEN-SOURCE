# -*- mode: python ; coding: utf-8 -*-

# Импорт Splash УДАЛЕН, так как сплэш-экран будет управляться из build.py (через --splash)
# или не будет использоваться, если его там нет.
# from PyInstaller.ूद import Splash # <-- ЭТА СТРОКА УДАЛЕНА

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Точка входа - корневой tool.py
ANALYSIS_TARGET_SCRIPT = ['tool.py']
# Пути для поиска модулей PyInstaller
ANALYSIS_PATHEX = ['src'] # Для импортов из src/

# Данные, которые должны быть ВНУТРИ _MEIPASS
ANALYSIS_DATAS = [
    ('LICENSE', '.'),
    ('README.md', '.'), # Если есть
    # Иконка и сплэш-картинка НЕ добавляются сюда, если они используются для EXE/сборки,
    # а не как ресурсы внутри _MEIPASS, читаемые программой.
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
HIDDEN_IMPORTS += collect_submodules('core') # Собирает все из src/core
HIDDEN_IMPORTS += collect_submodules('tkui') # Собирает все из src/tkui

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
EXE_ICON_PATH = 'icon.ico' # Иконка для tool.exe (лежит в корне проекта)

exe = EXE(
    pyz,
    a.scripts,
    # Параметр splash УДАЛЕН отсюда
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
)

APP_COLLECTION_NAME = 'MIO-Kitchen-AppBase' # Временная папка для PyInstaller

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas, # Включает LICENSE, README, данные PIL, sv_ttk, chlorophyll в _MEIPASS
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_COLLECTION_NAME
)
