# tool.spec

# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller. επίσης.splash import Splash # Импортируем Splash, если будем использовать

block_cipher = None

# Точка входа - корневой tool.py
ANALYSIS_TARGET_SCRIPT = ['tool.py']
# Пути для поиска модулей PyInstaller
ANALYSIS_PATHEX = ['src'] # ИСПРАВЛЕНО: PAT ร่วมกันHEX_PATHS -> ANALYSIS_PATHEX

# Данные, которые должны быть ВНУТРИ _MEIPASS
ANALYSIS_DATAS = [
    ('LICENSE', '.'),
    ('README.md', '.'),
    # ('icon.ico', '.'), # Иконка указывается в EXE
    # ('splash.png', '.') # Сплэш-картинка будет здесь, если используем Splash из .spec
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
    pathex=ANALYSIS_PATHEX, # ИСПРАВЛЕНО
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
    icon=EXE_ICON_PATH,
    # Добавляем сплэш-экран сюда для EXE, если файл splash.png существует
    # Это предпочтительнее, чем --splash в командной строке, когда используется .spec
    # PyInstaller автоматически найдет splash.png, если он в том же каталоге, что и .spec
    # или можно указать полный путь ('path/to/splash.png', binaries_to_filter_out=[])
    # splash=Splash('splash.png', binaries=a.binaries, datas=a.datas) # Закомментировано, если splash.png нет
)

# Если splash.png существует, раскомментируйте и настройте Splash выше.
# Убедитесь, что splash.png находится там, где его ожидает PyInstaller (обычно рядом со .spec файлом).
# Если вы определяете Splash здесь, то НЕ используйте --splash в build.py.

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
