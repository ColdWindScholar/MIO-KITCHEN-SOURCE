# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ANALYSIS_TARGET_SCRIPT = ['tool.py'] 

a = Analysis(
    ANALYSIS_TARGET_SCRIPT,
    pathex=[],
    binaries=[],
    datas=[
        # Сюда мы включаем только то, что должно быть внутри _MEIPASS.
        # Папку 'bin' целиком мы будем копировать рядом с EXE.
        # Однако, если для самого ПЕРВОГО запуска (до того, как utils.prog_path
        # сможет указать на внешнюю папку bin) нужны какие-то критичные файлы из bin,
        # их нужно добавить сюда. Например, если setting.ini или языки по умолчанию читаются ДО того,
        # как приложение определит свой путь.
        # Для простоты и максимального соответствия "bin рядом", оставим здесь минимум.
        # Пример: если языки нужны сразу:
        # ('bin/languages', 'bin/languages'), # Будет в _MEIPASS/bin/languages
        # ('bin/setting.ini', 'bin'), # Будет в _MEIPASS/bin/setting.ini
        
        ('LICENSE', '.'), # LICENSE будет в _MEIPASS, и мы его еще раз скопируем рядом с EXE
        ('README*.md', '.'), # Если есть
    ] + collect_data_files('PIL', include_py_files=True) \
      + collect_data_files('sv_ttk') \
      + collect_data_files('chlorophyll'),
    hiddenimports=[
        'PIL', 'PIL._imaging', 'PIL._imagingtk', 'PIL.ImageTk', 'PIL._tkinter_finder',
        'tkinterdnd2',
        'pygments.lexers',
    ] + collect_submodules('requests'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Имя исполняемого файла будет tool.exe
exe_app_name = 'tool' 

exe = EXE(
    pyz,
    a.scripts,
    name=exe_app_name,
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
    icon='icon.ico'
)

# Для one-dir сборки, мы указываем, какие компоненты из Analysis и EXE идут в финальную директорию.
# Имя директории будет 'MIO-Kitchen-AppBase' (или как вы назовете).
# PyInstaller сам создаст эту папку в 'dist/'.
app_collection_name = 'MIO-Kitchen-AppBase' # Временное имя папки, куда PyInstaller все соберет

coll = COLLECT(
    exe, # Исполняемый файл, созданный выше
    a.binaries, # Бинарные зависимости
    a.zipfiles, # Zipped-данные (pyz)
    a.datas,    # Данные из Analysis.datas (например, LICENSE из _MEIPASS)
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_collection_name # Имя папки, создаваемой в dist/
)
