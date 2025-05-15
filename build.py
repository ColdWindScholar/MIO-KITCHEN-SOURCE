#!/usr/bin/env python3
# pylint: disable=line-too-long, broad-except
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env python3
# pylint: disable=line-too-long, broad-except
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
# ... (лицензия) ...

import os
import platform
import shutil
import zipfile
import sys # Добавлен sys
from pathlib import Path # Рекомендуется для работы с путями

# --- Шаг 1: Установка зависимостей ---
try:
    import pip
    if hasattr(pip, '_internal') and hasattr(pip._internal, 'cli') and hasattr(pip._internal.cli, 'main'):
        from pip._internal.cli.main import main as _pip_main
    else:
        import subprocess
        print("Using subprocess for pip commands.")
        def _pip_main_subprocess(args):
            try:
                result = subprocess.run([sys.executable, "-m", "pip"] + args, check=True, capture_output=True, text=True)
                return 0
            except subprocess.CalledProcessError as e:
                print(f"Error running pip command: {' '.join(args)}\nStderr: {e.stderr}")
                return e.returncode
            except FileNotFoundError:
                print(f"Error: '{sys.executable} -m pip' not found.")
                return -1
        _pip_main = _pip_main_subprocess

    print("Checking and installing requirements...")
    requirements_file = Path('requirements.txt')
    if requirements_file.is_file():
        with open(requirements_file, 'r', encoding='utf-8') as req_file:
            for requirement in req_file:
                requirement = requirement.strip()
                if requirement and not requirement.startswith('#'):
                    print(f"Processing requirement: {requirement}")
                    ret_code = _pip_main(['install', '--upgrade', '--no-cache-dir', '--disable-pip-version-check', '--no-input', requirement])
                    if ret_code == 0:
                        print(f"Successfully processed {requirement}")
                    elif ret_code != 0:
                        print(f"Warning: pip install for {requirement} returned code {ret_code}.")
    else:
        print(f"Warning: '{requirements_file}' not found. Skipping dependency installation.")
except ImportError:
    print("Warning: pip module could not be imported. Skipping dependency installation.")
except Exception as e:
    print(f"Error during dependency installation phase: {e}")

# --- Шаг 2: Импорт PyInstaller ---
try:
    import PyInstaller.__main__
except ImportError:
    print("FATAL ERROR: PyInstaller is not installed. Please install it: pip install pyinstaller")
    sys.exit(1)

# --- Шаг 3: Определение переменных ---
ostype = platform.system()
current_dir_path = Path.cwd() # Переименовано из 'local' для ясности
# Имя ZIP-архива (переменная 'name' из вашего оригинального кода)
final_zip_archive_name = ""
if ostype == 'Linux':
    final_zip_archive_name = 'MIO-KITCHEN-linux.zip'
elif ostype == 'Darwin':
    final_zip_archive_name = 'MIO-KITCHEN-macos-intel.zip' if platform.machine() == 'x86_64' else 'MIO-KITCHEN-macos.zip'
else: # Windows
    final_zip_archive_name = 'MIO-KITCHEN-win.zip'

# Точка входа - корневой tool.py (предполагается, что он вызывает src/tkui/tool.py)
entry_script = 'tool.py'

# Имя исполняемого файла (без расширения)
output_executable_name = 'tool'


# --- Шаг 4: Функция для архивации (адаптирована для архивации содержимого папки dist) ---
def zip_dist_folder_contents(dist_folder_path_str, output_zip_file_path_str):
    source_path = Path(dist_folder_path_str).resolve()
    output_path = Path(output_zip_file_path_str).resolve() # Архив будет в корне проекта

    if not source_path.is_dir():
        print(f"Error: Source for zipping '{source_path}' is not a directory.")
        return

    print(f"Archiving contents of '{source_path}' into '{output_path}'...")
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for item_path in source_path.rglob('*'):
                archive_item_path = item_path.relative_to(source_path)
                if item_path.is_file():
                    # print(f"Adding file: {archive_item_path}")
                    archive.write(item_path, archive_item_path)
                elif item_path.is_dir() and not any(item_path.iterdir()):
                    # print(f"Adding empty directory: {archive_item_path}/")
                    dir_info = zipfile.ZipInfo(str(archive_item_path) + '/')
                    archive.writestr(dir_info, '')
        print(f"Archive '{output_path}' created successfully!")
    except Exception as e_zip:
        print(f"Error during archiving '{output_path}': {e_zip}")


# --- Шаг 5: Сборка PyInstaller ---
print(f"Starting PyInstaller build for {ostype} ({platform.machine()})...")

# Базовые аргументы PyInstaller, соответствующие вашему оригинальному скрипту
# Собираем в один файл (-F) и как оконное приложение (-w)
pyinstaller_args = [
    entry_script,
    '--name', output_executable_name, # Имя исполняемого файла tool.exe
    '--onefile',    # Эквивалент -F
    '--windowed',   # Эквивалент -w (или --noconsole)
    '--icon=icon.ico',
    '--exclude-module=numpy',
    '--clean', # Рекомендуется для чистой сборки
    
    # Данные для библиотек
    '--collect-all=PIL',        # Собирает все для Pillow (более надежно, чем --collect-data)
    '--collect-all=sv_ttk',     # Аналогично для sv_ttk
    '--collect-all=chlorophyll',# Аналогично для chlorophyll
    
    # Скрытые импорты (добавляем необходимые для Pillow и ваших модулей)
    '--hidden-import=PIL', # Часто не нужен при --collect-all, но не повредит
    '--hidden-import=PIL._imaging',
    '--hidden-import=PIL._imagingtk',
    '--hidden-import=PIL.ImageTk',
    '--hidden-import=PIL._tkinter_finder',
    '--hidden-import=tkinterdnd2',
    '--hidden-import=pygments.lexers',
    # Добавляем пути к вашим модулям в src/ для PyInstaller
    # PyInstaller попытается найти импорты из них.
    # Если build.py в корне, а tool.py (основной) в src/tkui:
    '--paths=src', 
    # Явное указание ваших основных пакетов/модулей из папки 'src'
    '--hidden-import=tkui',
    '--hidden-import=tkui.tool',
    '--hidden-import=core',
    '--hidden-import=core.utils',
    # Добавьте другие ваши модули, если они не находятся автоматически
]

# Сплэш-экран (как в вашем оригинале)
splash_file = current_dir_path / 'splash.png'
if (ostype == 'Windows' or ostype == 'Linux') and splash_file.is_file():
    pyinstaller_args.extend(['--splash', str(splash_file)])
elif (ostype == 'Windows' or ostype == 'Linux'):
    print(f"Warning: Splash file '{splash_file}' not found. Splash screen will not be used.")

# Аргументы, специфичные для macOS (из вашего оригинала, если нужны)
# В вашем оригинале для macOS не было --splash, и некоторые hidden-imports отличались.
# Здесь я унифицировал hidden-imports для Pillow.
# if ostype == 'Darwin':
#    pyinstaller_args.remove('--splash') # Пример, если сплэш не для macOS
#    pyinstaller_args.remove('splash.png')
   # macOS может требовать другие --hidden-import или --collect-data
   # Ваш оригинальный код для macOS не включал --hidden-import tkinter, PIL, PIL._tkinter_finder
   # Я их оставил, так как они обычно нужны.

try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("PyInstaller build completed. Executable in 'dist/' directory.")
except Exception as e_pyinst:
    error_message = str(e_pyinst)
    # ... (обработка UnicodeEncodeError как в предыдущем ответе) ...
    try:
        if isinstance(error_message, bytes): error_message = error_message.decode(sys.stdout.encoding or 'utf-8', 'replace')
    except Exception: pass
    try: print(f"FATAL ERROR: PyInstaller failed: {error_message}")
    except UnicodeEncodeError:
        safe_error_message = error_message.encode(sys.stdout.encoding or 'utf-8', 'replace').decode(sys.stdout.encoding or 'utf-8', 'replace')
        print(f"FATAL ERROR: PyInstaller failed (unprintable chars): {safe_error_message}")
    sys.exit(1)

# --- Шаг 6: Пост-обработка: копирование папки bin и LICENSE ---
# PyInstaller создаст dist/tool.exe (или tool для Linux/macOS)
print("Starting post-build file copying...")

dist_output_path = current_dir_path / 'dist' # Папка, куда PyInstaller кладет результат

# 1. Копируем ВСЮ папку `bin` из исходников в `dist/bin` (рядом с tool.exe)
target_bin_in_dist = dist_output_path / 'bin'
source_bin_dir = current_dir_path / 'bin'
if source_bin_dir.is_dir():
    if target_bin_in_dist.exists():
        print(f"Removing existing target 'bin' directory: {target_bin_in_dist}")
        shutil.rmtree(target_bin_in_dist)
    print(f"Copying project 'bin' directory '{source_bin_dir}' to '{target_bin_in_dist}'...")
    shutil.copytree(source_bin_dir, target_bin_in_dist, dirs_exist_ok=True)
else:
    print(f"CRITICAL WARNING: Source 'bin' directory not found at '{source_bin_dir}'. It will be MISSING in the release!")

# 2. Копируем `LICENSE` в `dist/LICENSE`
source_license_file = current_dir_path / 'LICENSE'
target_license_in_dist = dist_output_path / 'LICENSE'
if source_license_file.is_file():
    if target_license_in_dist.exists(): target_license_in_dist.unlink() # Удаляем, если уже есть
    print(f"Copying '{source_license_file}' to '{target_license_in_dist}'...")
    shutil.copy2(source_license_file, target_license_in_dist)
else:
    print(f"Warning: LICENSE file not found at '{source_license_file}'.")


# 3. Фильтрация `tkdnd` в `dist/bin/tkdnd` (логика из вашего оригинального скрипта)
tkdnd_final_path = target_bin_in_dist / 'tkdnd'
if tkdnd_final_path.is_dir():
    dndplat_filter_key = None # Переименовано из dndplat, чтобы не конфликтовать с глобальной
    if ostype == 'Darwin':
        dndplat_filter_key = 'osx-x64' if platform.machine() == 'x86_64' else 'osx-arm64'
    elif ostype == 'Linux':
        dndplat_filter_key = 'linux-x64' if platform.machine() == 'x86_64' else 'linux-arm64'
    elif ostype == 'Windows':
        mach = platform.machine()
        arch_32 = platform.architecture()[0] == '32bit'
        # Ваша оригинальная логика platform.machine = lambda... была для PyInstaller,
        # здесь мы просто определяем ключ для фильтрации.
        if arch_32 and mach == 'AMD64': current_machine_for_tkdnd = 'x86' # WoW64
        else: current_machine_for_tkdnd = mach

        if current_machine_for_tkdnd == 'x86': dndplat_filter_key = 'win-x86'
        elif current_machine_for_tkdnd == 'AMD64': dndplat_filter_key = 'win-x64'
        elif current_machine_for_tkdnd == 'ARM64': dndplat_filter_key = 'win-arm64'
    
    if dndplat_filter_key:
        print(f"Filtering tkdnd versions in '{tkdnd_final_path}' for platform: {dndplat_filter_key}")
        if not (tkdnd_final_path / dndplat_filter_key).exists():
             print(f"  Warning: Target tkdnd platform folder '{dndplat_filter_key}' not found. TkDND might not work.")
        for item in tkdnd_final_path.iterdir():
            # Адаптированная логика из вашего оригинального build.py:
            # if i[:3] == dndplat[:3] and i.endswith("x64") and dndplat.endswith('x86'): continue
            # if i == dndplat: continue
            if item.name == dndplat_filter_key:
                print(f"  Keeping tkdnd version: {item.name}")
                continue
            
            # Ваша оригинальная логика удаления была "удалить если НЕ ( (первые 3 символа совпадают И тек. x64 И целевая x86) ИЛИ точное совпадение )"
            # Это немного запутанно. Давайте сделаем проще: если имя не равно dndplat_filter_key, удаляем.
            # Если вам нужна более сложная логика сохранения нескольких версий, ее нужно будет восстановить.
            # Например, если для win-x86 вы хотите также оставить win-x64.
            # Моя текущая упрощенная логика: удалить всё, что не является dndplat_filter_key.
            
            print(f"  Removing tkdnd version: {item.name}")
            if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
            else: item.unlink(missing_ok=True) # Для файлов
    else:
        print(f"Warning: Could not determine tkdnd platform for filtering. All versions in '{tkdnd_final_path}' might be kept or it might be empty.")
else:
    if source_bin_dir.is_dir(): # Только если папка bin вообще была скопирована
         print(f"Warning: tkdnd directory not found at '{tkdnd_final_path}'. Skipping tkdnd filtering.")


# 4. Выдача прав на Linux/macOS (для tool в dist/)
# Имя исполняемого файла из --name
executable_final_path = dist_output_path / output_executable_name
if ostype == 'Windows': # Для Windows добавляем .exe, если PyInstaller не добавил сам
    if not executable_final_path.suffix and (dist_output_path / (output_executable_name + '.exe')).exists():
        executable_final_path = dist_output_path / (output_executable_name + '.exe')

if (ostype == 'Linux' or ostype == 'Darwin'):
    if executable_final_path.is_file():
        print(f"Setting execute permissions for: {executable_final_path}")
        try: os.chmod(executable_final_path, 0o755)
        except Exception as e_chmod: print(f"  Warning: Failed to set execute permissions: {e_chmod}")
    else:
        print(f"Warning: Executable '{executable_final_path}' not found for setting permissions.")

# --- Шаг 7: Архивация папки dist ---
# Архивируем все содержимое папки dist (tool.exe, bin/, LICENSE)
# Архив будет создан в корне проекта.
if dist_output_path.is_dir() and any(dist_output_path.iterdir()): # Проверяем, что папка не пуста
    zip_output_target_file = current_dir_path / final_zip_archive_name
    zip_dist_folder_contents(str(dist_output_path), str(zip_output_target_file))
else:
    print(f"Error: Distribution directory '{dist_output_path}' is empty or not found. Archiving failed.")

print("Build script finished.")
