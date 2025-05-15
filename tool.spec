# tool.spec

# -*- mode: python ; coding: utf-8 -*-

# Этот импорт может понадобиться, если вы используете сплэш-экран из .spec файла
# from PyInstaller. επίσης.splash import Splash
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# -----------------------------------------------------------------------------
# Анализ: определение того, что нужно включить в сборку
# -----------------------------------------------------------------------------
# Точка входа - корневой tool.py
ANALYSIS_TARGET_SCRIPT = ['tool.py']

# Добавляем папку 'src' в пути поиска модулей, чтобы PyInstaller мог найти
# модули внутри src (например, tkui.tool, core.utils).
# pathex также используется для разрешения относительных путей в Analysis.
PAT ร่วมกันHEX_PATHS = ['src']


# Данные, которые должны быть включены ВНУТРТРЬ структуры приложения (_MEIPASS).
# Папку 'bin' целиком мы НЕ включаем сюда, так как она будет скопирована РЯДОМ с .exe
# на этапе build.py.
# Однако, если для самого ПЕРВОГО запуска (до того, как utils.PROG_PATH
# сможет указать на внешнюю папку bin) нужны какие-то критичные файлы из bin,
# их копии нужно добавить сюда для _MEIPASS.
# Например:
#   ('bin/setting.ini', 'bin'), # Будет в _MEIPASS/bin/setting.ini
#   ('bin/languages/English.json', 'bin/languages'), # Будет в _MEIPASS/bin/languages/English.json
#   ('bin/images/icon.png', 'bin/images'), # Если иконка нужна очень рано из _MEIPASS
# Если таких файлов нет, этот список может быть короче.
ANALYSIS_DATAS = [
    ('LICENSE', '.'),       # LICENSE будет в корне _MEIPASS
    ('README.md', '.'),     # README.md будет в корне _MEIPASS (если есть)
    # ('icon.ico', '.'),    # Если иконка нужна в _MEIPASS (обычно она указывается для EXE)
    # ('splash.png', '.') # Если сплэш-картинка нужна в _MEIPASS
]

# Дополнительные данные, собираемые через утилиты PyInstaller
# (например, для Pillow, sv_ttk, chlorophyll)
ANALYSIS_DATAS += collect_data_files('PIL', include_py_files=True)
ANALYSIS_DATAS += collect_data_files('sv_ttk')
ANALYSIS_DATAS += collect_data_files('chlorophyll')


# Скрытые импорты: модули, которые PyInstaller может не найти автоматически.
HIDDEN_IMPORTS = [
    'PIL', 'PIL._imaging', 'PIL._imagingtk', 'PIL.ImageTk', 'PIL._tkinter_finder',
    'tkinterdnd2',      # Если используется
    'pygments.lexers',  # Включает все лексеры pygments
    
    # Явное указание ваших основных пакетов/модулей из папки 'src'
    # PyInstaller должен их найти благодаря pathex=['src'], но для надежности можно добавить
    # или использовать collect_submodules ниже.
    # 'tkui',
    # 'tkui.tool',
    # 'core',
    # 'core.utils',
    # ... другие важные модули из src ...

    # Если у вас есть зависимости Crypto, раскомментируйте нужные.
    # Убедитесь, что вы используете PyCryptodome, а не старый PyCrypto.
    # 'Crypto.Cipher._raw_ecb',
    # 'Crypto.Cipher.AES',
    # 'Crypto.Hash.SHA256',
    # 'Crypto.Protocol.KDF',
]

# Сбор подмодулей для некоторых пакетов
HIDDEN_IMPORTS += collect_submodules('requests')
HIDDEN_IMPORTS += collect_submodules('core') # Соберет все подмодули из src/core
HIDDEN_IMPORTS += collect_submodules('tkui') # Соберет все подмодули из src/tkui

# Исключаемые модули
EXCLUDES = ['numpy'] # Уже есть в build.py, здесь для полноты

a = Analysis(
    ANALYSIS_TARGET_SCRIPT,
    pathex=PAT ร่วมกันHEX_PATHS,
    binaries=[], # Бинарные файлы (.dll, .so) можно добавлять сюда списком кортежей ('source', 'dest_in_meipass')
    datas=ANALYSIS_DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False # False обычно лучше для отладки, True может немного уменьшить размер
)

# -----------------------------------------------------------------------------
# PYZ (Python Zipped Archive): сжатые .pyc файлы
# -----------------------------------------------------------------------------
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# -----------------------------------------------------------------------------
# EXE: создание исполняемого файла
# -----------------------------------------------------------------------------
# Имя исполняемого файла (например, tool.exe)
EXE_APP_NAME = 'tool'
# Путь к файлу иконки (относительно .spec файла)
EXE_ICON_PATH = 'icon.ico'

exe = EXE(
    pyz,
    a.scripts, # Список скриптов из Analysis (обычно только главный)
    # binaries=a.binaries, # Бинарники уже в Analysis, здесь не нужно дублировать для one-dir
    # datas=a.datas,       # Данные уже в Analysis, здесь не нужно дублировать для one-dir
    # zipfile=None,        # Для one-dir обычно не используется
    name=EXE_APP_NAME,
    debug=False,        # Включение отладочных символов (False для релиза)
    bootloader_ignore_signals=False,
    strip=False,        # Удаление отладочной информации из бинарников (False для лучшей отладки)
    upx=True,           # Использование UPX для сжатия EXE (может вызывать ложные срабатывания антивирусов)
    upx_exclude=[],
    runtime_tmpdir=None,# None - система выберет временную папку для _MEIPASS
    console=False,      # False - не создавать консольное окно (для GUI-приложений)
    windowed=True,      # True - создать оконное приложение (эквивалент флага -w)
    disable_windowed_traceback=False, # Показывать traceback в диалоговом окне при падении
    argv_emulation=False,
    target_arch=None,   # None - архитектура текущей системы
    codesign_identity=None, # Для подписи кода на macOS
    entitlements_file=None, # Для macOS entitlements
    icon=EXE_ICON_PATH
)

# -----------------------------------------------------------------------------
# COLLECT: создание финальной директории приложения (для one-dir сборки)
# -----------------------------------------------------------------------------
# Имя папки, которая будет создана в 'dist/' (например, dist/MIO-Kitchen-AppBase/)
# Внутри этой папки будет лежать tool.exe и все его зависимости.
APP_COLLECTION_NAME = 'MIO-Kitchen-AppBase'

coll = COLLECT(
    exe,                # Исполняемый файл, созданный выше
    a.binaries,         # Все бинарные зависимости, найденные Analysis
    a.zipfiles,         # Все Python модули в PYZ (a.pure) и другие данные из Analysis.zipped_data
    a.datas,            # Все файлы данных из Analysis.datas (например, LICENSE.txt в _MEIPASS)
    strip=False,        # См. EXE -> strip
    upx=True,           # См. EXE -> upx
    upx_exclude=[],
    name=APP_COLLECTION_NAME # Имя создаваемой директории
)

# -----------------------------------------------------------------------------
# SplashScreen (опционально, если не используется --splash в build.py)
# -----------------------------------------------------------------------------
# splash_image_path = 'splash.png'
# splash = Splash(
#    splash_image_path,
#    binaries=a.binaries, # Важно передать, если сплэш их использует
#    datas=a.datas,       # Важно передать, если сплэш их использует
#    text_pos=None,
#    text_size=12,
#    text_color='black',
# )
#
# Если вы используете сплэш-экран из .spec, его нужно добавить в COLLECT вместо EXE:
# coll = COLLECT(
#    exe,
#    splash, # <--- Сплэш добавляется сюда для one-dir
#    a.binaries,
#    a.zipfiles,
#    a.datas,
#    strip=False, upx=True, upx_exclude=[], name=APP_COLLECTION_NAME
# )
# Однако, PyInstaller рекомендует --splash в командной строке для EXE,
# а для COLLECT его добавление может быть не таким прямолинейным.
# Проще оставить --splash в build.py, если он работает для вашего случая.
