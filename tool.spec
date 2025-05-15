# tool.spec

# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.splash import Splash # <<< ИСПРАВЛЕННЫЙ ИМПОРТ

block_cipher = None

ANALYSIS_TARGET_SCRIPT = ['tool.py']
ANALYSIS_PATHEX = ['src']

ANALYSIS_DATAS = [
    ('LICENSE', '.'),
    ('README.md', '.'),
    ('splash.png', '.') # Добавляем splash.png в datas, чтобы Splash мог его найти в _MEIPASS
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

# Создаем объект Splash
# PyInstaller будет использовать 'splash.png' из ANALYSIS_DATAS (т.е. из _MEIPASS)
# text_pos, text_size, text_color - опциональные параметры для текста на сплэш-экране
splash = Splash(
   'splash.png', # Имя файла, как оно будет в _MEIPASS (благодаря ANALYSIS_DATAS)
   binaries=a.binaries, # Передаем, если сплэш их использует (маловероятно для простого PNG)
   datas=a.datas,       # Передаем, чтобы Splash мог найти splash.png
   # text_font=None,    # Можно указать шрифт
   # text_pos=None,     # Позиция текста (x, y) или None для автоматического
   # text_size=12,      # Размер текста
   # text_color='black' # Цвет текста
)

exe = EXE(
    pyz,
    a.scripts,
    splash, # <--- ДОБАВЛЯЕМ ОБЪЕКТ SPLASH СЮДА
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

APP_COLLECTION_NAME = 'MIO-Kitchen-AppBase'

coll = COLLECT(
    exe, # EXE уже содержит конфигурацию Splash
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_COLLECTION_NAME
)
