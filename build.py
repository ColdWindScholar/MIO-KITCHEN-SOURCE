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
#!/usr/bin/env python3
# pylint: disable=line-too-long, broad-except
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project


import os
import platform
import shutil
import zipfile
import sys
from pathlib import Path

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
                    elif ret_code != 0 :
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
current_dir_path = Path.cwd()
# .spec файл НЕ используется явно, PyInstaller сгенерирует его
# spec_file_path = current_dir_path / 'tool.spec' 
splash_file_path = current_dir_path / 'splash.png'

base_release_name = ""
if ostype == 'Linux':
    base_release_name = 'MIO-KITCHEN-linux'
elif ostype == 'Darwin':
    base_release_name = 'MIO-KITCHEN-macos-intel' if platform.machine() == 'x86_64' else 'MIO-KITCHEN-macos'
else: # Windows
    base_release_name = 'MIO-KITCHEN-win'

final_release_build_folder_name = base_release_name
final_zip_archive_name = f"{base_release_name}.zip"

entry_script = 'tool.py' # Корневой tool.py
output_executable_name = 'tool' # Имя .exe файла будет tool.exe

# --- Шаг 4: Функция для архивации (без изменений) ---
def zip_folder_contents(folder_to_zip_path_str, output_zip_file_path_str):
    # ... (код функции как в предыдущем полном build.py) ...
    source_path = Path(folder_to_zip_path_str).resolve()
    output_path = Path(output_zip_file_path_str).resolve()
    if not source_path.is_dir():
        print(f"Error: Source for zipping '{source_path}' is not a directory.")
        return
    print(f"Archiving contents of '{source_path}' into '{output_path}'...")
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for item_path in source_path.rglob('*'):
                archive_item_path = item_path.relative_to(source_path)
                if item_path.is_file():
                    archive.write(item_path, archive_item_path)
                elif item_path.is_dir() and not any(item_path.iterdir()):
                    dir_info = zipfile.ZipInfo(str(archive_item_path) + '/')
                    archive.writestr(dir_info, '')
        print(f"Archive '{output_path}' created successfully!")
    except Exception as e_zip:
        print(f"Error during archiving '{output_path}': {e_zip}")

# --- Шаг 5: Сборка PyInstaller (конфигурация через командную строку) ---
print(f"Starting PyInstaller build for {ostype} ({platform.machine()})...")

pyinstaller_args = [
    entry_script,
    '--name', output_executable_name,
    '--onefile',    # -F
    '--windowed',   # -w / --noconsole
    '--icon=icon.ico',
    '--exclude-module=numpy',
    '--clean',      # Очистка перед сборкой
    '--noconfirm',  # Не спрашивать подтверждения
    
    # Добавляем пути поиска для ваших модулей в src/
    f'--paths={current_dir_path / "src"}',

    # --- КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ ДЛЯ PILLOW И ДРУГИХ БИБЛИОТЕК ---
    # Используем --collect-all, если доступно, это более надежно.
    # Если ваша версия PyInstaller старая и не поддерживает --collect-all,
    # используйте --collect-data ИМЯ_ПАКЕТА.
    '--collect-all=PIL',
    '--collect-all=sv_ttk',
    '--collect-all=chlorophyll',
    # Если --collect-all недоступен:
    # '--collect-data=PIL',
    # '--collect-data=sv_ttk',
    # '--collect-data=chlorophyll',

    # Скрытые импорты
    '--hidden-import=PIL', # Для надежности, даже с --collect-all
    '--hidden-import=PIL._imaging',
    '--hidden-import=PIL._imagingtk',
    '--hidden-import=PIL.ImageTk',
    '--hidden-import=PIL._tkinter_finder',
    '--hidden-import=tkinterdnd2',
    '--hidden-import=pygments.lexers',
    # Явное указание ваших основных пакетов/модулей из папки 'src'
    '--hidden-import=tkui',
    '--hidden-import=tkui.tool', # Главный GUI модуль
    '--hidden-import=core',
    '--hidden-import=core.utils',
    # '--hidden-import=requests', # requests обычно находится сам, но можно добавить
    # '--hidden-import=Crypto', # Если используете PyCryptodome
]

# Добавление --add-data для папки bin и LICENSE
# Это упакует их ВНУТРЬ EXE файла, в _MEIPASS.
# Структура: ('источник_в_проекте:путь_внутри_exe')
# Разделитель зависит от ОС: ; для Windows, : для Linux/macOS
data_separator = ';' if ostype == 'Windows' else ':'

# Упаковываем всю папку bin в корень _MEIPASS/bin
# Это может сделать EXE очень большим и не соответствует вашему желанию иметь bin рядом.
# НО, если мы не используем .spec, это один из способов заставить PyInstaller
# узнать о файлах, если они нужны для _MEIPASS.
# Для вашей цели "bin рядом с EXE", этот --add-data для всей папки bin НЕ НУЖЕН.
# PyInstaller при --onefile должен упаковать только то, что импортируется.
# Ваша логика копирования bin рядом с EXE после сборки остается основной.

# Если какие-то файлы из bin нужны для самого раннего старта, их можно добавить точечно:
# pyinstaller_args.append(f'--add-data=LICENSE{data_separator}.') # LICENSE в корень _MEIPASS
# pyinstaller_args.append(f'--add-data=bin/setting.ini{data_separator}bin') # setting.ini в _MEIPASS/bin
# pyinstaller_args.append(f'--add-data=bin/languages/English.json{data_separator}bin/languages')

# Сплэш-экран
if (ostype == 'Windows' or ostype == 'Linux') and splash_file_path.is_file():
    pyinstaller_args.extend(['--splash', str(splash_file_path)])
elif (ostype == 'Windows' or ostype == 'Linux'):
    print(f"Warning: Splash file '{splash_file_path}' not found.")

try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("PyInstaller build completed. Executable in 'dist/' directory.")
except Exception as e_pyinst:
    error_message = str(e_pyinst)
    try:
        if isinstance(error_message, bytes): error_message = error_message.decode(sys.stdout.encoding or 'utf-8', 'replace')
    except Exception: pass
    try: print(f"FATAL ERROR: PyInstaller failed: {error_message}")
    except UnicodeEncodeError:
        safe_error_message = error_message.encode(sys.stdout.encoding or 'utf-8', 'replace').decode(sys.stdout.encoding or 'utf-8', 'replace')
        print(f"FATAL ERROR: PyInstaller failed (unprintable chars): {safe_error_message}")
    sys.exit(1)

# --- Шаг 6: Пост-обработка: копирование папки bin и LICENSE ---
# PyInstaller создаст dist/tool.exe (или tool).
# Копируем bin и LICENSE рядом с ним.
print("Starting post-build file copying...")

dist_output_path = current_dir_path / 'dist'

# 1. Копируем ВСЮ папку `bin` из исходников в `dist/bin`
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
    if target_license_in_dist.exists(): target_license_in_dist.unlink(missing_ok=True)
    print(f"Copying '{source_license_file}' to '{target_license_in_dist}'...")
    shutil.copy2(source_license_file, target_license_in_dist)
else:
    print(f"Warning: LICENSE file not found at '{source_license_file}'.")

# 3. Фильтрация `tkdnd` в `dist/bin/tkdnd` (как в вашем оригинале)
# ... (полный блок фильтрации tkdnd, как в предыдущем ответе, он не меняется) ...
tkdnd_final_path = target_bin_in_dist / 'tkdnd'
if tkdnd_final_path.is_dir():
    dndplat_filter_key = None
    if ostype == 'Darwin':
        dndplat_filter_key = 'osx-x64' if platform.machine() == 'x86_64' else 'osx-arm64'
    elif ostype == 'Linux':
        dndplat_filter_key = 'linux-x64' if platform.machine() == 'x86_64' else 'linux-arm64'
    elif ostype == 'Windows':
        mach = platform.machine()
        arch_32 = platform.architecture()[0] == '32bit'
        if arch_32 and mach == 'AMD64': current_machine_for_tkdnd = 'x86'
        else: current_machine_for_tkdnd = mach
        if current_machine_for_tkdnd == 'x86': dndplat_filter_key = 'win-x86'
        elif current_machine_for_tkdnd == 'AMD64': dndplat_filter_key = 'win-x64'
        elif current_machine_for_tkdnd == 'ARM64': dndplat_filter_key = 'win-arm64'
    if dndplat_filter_key:
        print(f"Filtering tkdnd versions in '{tkdnd_final_path}' for platform: {dndplat_filter_key}")
        if not (tkdnd_final_path / dndplat_filter_key).exists():
             print(f"  Warning: Target tkdnd platform folder '{dndplat_filter_key}' not found. TkDND might not work.")
        for item in tkdnd_final_path.iterdir():
            if item.name == dndplat_filter_key:
                print(f"  Keeping tkdnd version: {item.name}")
                continue
            print(f"  Removing tkdnd version: {item.name}")
            if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
            else: item.unlink(missing_ok=True)
    else:
        print(f"Warning: Could not determine tkdnd platform for filtering. All versions in '{tkdnd_final_path}' might be kept.")
else:
    if source_bin_dir.is_dir():
         print(f"Warning: tkdnd directory not found at '{tkdnd_final_path}'. Skipping tkdnd filtering.")

# 4. Выдача прав на Linux/macOS (для tool в dist/)
executable_final_path_in_dist = dist_output_path / output_executable_name
if ostype == 'Windows':
    if not executable_final_path_in_dist.suffix and (dist_output_path / (output_executable_name + '.exe')).exists():
        executable_final_path_in_dist = dist_output_path / (output_executable_name + '.exe')

if (ostype == 'Linux' or ostype == 'Darwin'):
    if executable_final_path_in_dist.is_file():
        print(f"Setting execute permissions for: {executable_final_path_in_dist}")
        try: os.chmod(executable_final_path_in_dist, 0o755)
        except Exception as e_chmod: print(f"  Warning: Failed to set execute permissions: {e_chmod}")
    else:
        print(f"Warning: Executable '{executable_final_path_in_dist}' not found for setting permissions.")

# --- Шаг 7: Архивация папки dist ---
# Архивируем все содержимое папки dist (tool.exe, bin/, LICENSE)
# Архив будет создан в корне проекта.
# Имя архива берется из переменной final_zip_archive_name, определенной ранее.
if dist_output_path.is_dir() and any(dist_output_path.iterdir()):
    zip_output_target_file = current_dir_path / final_zip_archive_name # Имя архива из начала скрипта
    zip_dist_folder_contents(str(dist_output_path), str(zip_output_target_file))
else:
    print(f"Error: Distribution directory '{dist_output_path}' is empty or not found. Archiving failed.")

print("Build script finished.")
