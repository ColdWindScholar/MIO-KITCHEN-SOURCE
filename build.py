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

#!/usr/bin/env python3
# pylint: disable=line-too-long, broad-except
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
# ... (лицензия) ...

import os
import platform
import shutil
import zipfile
import sys
from pathlib import Path # Используем pathlib для путей

# --- Шаг 1: Установка зависимостей ---
try:
    import pip
    if hasattr(pip, '_internal') and hasattr(pip._internal, 'cli') and hasattr(pip._internal.cli, 'main'):
        from pip._internal.cli.main import main as _pip_main
    else:
        import subprocess
        print("Using subprocess for pip commands.")
        def _pip_main_subprocess(args):
            # ... (код _pip_main_subprocess как в предыдущем ответе) ...
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
                    if ret_code == 0: print(f"Successfully processed {requirement}")
                    elif ret_code != 0: print(f"Warning: pip install for {requirement} returned code {ret_code}.")
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
current_dir_path = Path.cwd() # Переименовано из 'local'
# Имя ZIP-архива (переменная 'name' из вашего оригинального кода)
final_zip_archive_name = ""
if ostype == 'Linux':
    final_zip_archive_name = 'MIO-KITCHEN-linux.zip'
elif ostype == 'Darwin':
    final_zip_archive_name = 'MIO-KITCHEN-macos-intel.zip' if platform.machine() == 'x86_64' else 'MIO-KITCHEN-macos.zip'
else: # Windows
    final_zip_archive_name = 'MIO-KITCHEN-win.zip'

# from src.tool_tester import test_main, Test # Если этот путь актуален и файл существует
# if 'Test' in globals() and Test:
#    test_main(exit=False)

entry_script = 'tool.py' # Корневой tool.py
output_executable_name = 'tool' # Имя .exe файла будет tool.exe

# --- Шаг 4: Функция для архивации ---
def zip_folder_contents(folder_to_zip_path_str, output_zip_file_path_str):
    source_path = Path(folder_to_zip_path_str).resolve()
    output_zip_path = Path(output_zip_file_path_str).resolve() # Используем правильное имя переменной

    if not source_path.is_dir():
        print(f"Error: Source for zipping '{source_path}' is not a directory.")
        return

    print(f"Archiving contents of '{source_path}' into '{output_zip_path}'...")
    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for item_path in source_path.rglob('*'):
                archive_item_path = item_path.relative_to(source_path)
                if item_path.is_file():
                    archive.write(item_path, archive_item_path)
                elif item_path.is_dir() and not any(item_path.iterdir()): # Только действительно пустые папки
                    dir_info = zipfile.ZipInfo(str(archive_item_path) + '/')
                    archive.writestr(dir_info, '')
        print(f"Archive '{output_zip_path}' created successfully!")
    except Exception as e_zip:
        print(f"Error during archiving '{output_zip_path}': {e_zip}")


# --- Шаг 5: Сборка PyInstaller ---
print(f"Building {output_executable_name} for {ostype} ({platform.machine()})...")

# Общие аргументы для всех платформ
base_pyinstaller_args = [
    entry_script,
    '--name', output_executable_name,
    '--onefile',  # -F
    '--windowed', # -w
    '--icon=icon.ico',
    '--exclude-module=numpy',
    '--clean',
    '--noconfirm',
    f'--paths={current_dir_path / "src"}', # Путь к вашим модулям в src/

    # --- Улучшенные инструкции для Pillow ---
    '--collect-all=PIL',
    '--hidden-import=PIL',
    '--hidden-import=PIL._imaging',
    '--hidden-import=PIL._imagingtk',
    '--hidden-import=PIL.ImageTk',
    '--hidden-import=PIL._tkinter_finder',
    # ------------------------------------

    '--collect-all=sv_ttk',     # Заменил --collect-data на --collect-all
    '--collect-all=chlorophyll',# Заменил --collect-data на --collect-all
    
    '--hidden-import=tkinterdnd2', # TkinterDnD2 (если это имя пакета)
    '--hidden-import=pygments.lexers',
    # Ваши основные модули (если PyInstaller их не находит автоматически)
    '--hidden-import=tkui',
    '--hidden-import=tkui.tool',
    '--hidden-import=core',
    '--hidden-import=core.utils',
]

# Аргументы, специфичные для ОС
platform_specific_args = []
if ostype == 'Darwin':
    # Ваш оригинальный код для macOS не имел --splash и некоторых hidden-imports.
    # Если tkinter/PIL специфичные hidden-imports для macOS не нужны, их можно убрать из base_args
    # и добавить только нужные здесь. Но обычно они требуются.
    pass # Нет специфичных аргументов для macOS в вашем оригинале, кроме отсутствия сплэша
elif ostype == 'Linux':
    splash_file = current_dir_path / 'splash.png'
    if splash_file.is_file():
        platform_specific_args.extend(['--splash', str(splash_file)])
    else:
        print(f"Warning: Splash file '{splash_file}' not found for Linux.")
elif ostype == 'Windows': # 'nt'
    splash_file = current_dir_path / 'splash.png'
    if splash_file.is_file():
        platform_specific_args.extend(['--splash', str(splash_file)])
    else:
        print(f"Warning: Splash file '{splash_file}' not found for Windows.")
    # Ваш оригинальный код для Windows не включал --hidden-import tkinter, PIL, PIL._tkinter_finder
    # Но они, скорее всего, нужны, поэтому оставлены в base_pyinstaller_args.

final_pyinstaller_args = base_pyinstaller_args + platform_specific_args

try:
    PyInstaller.__main__.run(final_pyinstaller_args)
    print("PyInstaller build completed. Executable in 'dist/' directory.")
except Exception as e_pyinst:
    # ... (обработка UnicodeEncodeError как в предыдущем ответе) ...
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
print("Starting post-build file copying...")
dist_output_path = current_dir_path / 'dist'

# 1. Копируем ВСЮ папку `bin` из исходников в `dist/bin`
target_bin_in_dist = dist_output_path / 'bin'
source_bin_dir = current_dir_path / 'bin' # Путь к вашей папке bin в проекте
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

# 3. Фильтрация `tkdnd` в `dist/bin/tkdnd`
tkdnd_final_path = target_bin_in_dist / 'tkdnd'
if tkdnd_final_path.is_dir():
    dndplat_folder_to_keep = None
    if ostype == 'Darwin':
        dndplat_folder_to_keep = 'osx-x64' if platform.machine() == 'x86_64' else 'osx-arm64'
    elif ostype == 'Linux':
        dndplat_folder_to_keep = 'linux-x64' if platform.machine() == 'x86_64' else 'linux-arm64'
    elif ostype == 'Windows':
        mach = platform.machine() # Оригинальное значение
        # Ваша логика platform.machine = lambda... изменяла глобальное состояние, что не очень хорошо.
        # Лучше определять нужную платформу здесь локально.
        is_32bit_python_on_64bit_windows = platform.architecture()[0] == '32bit' and mach == 'AMD64'

        if is_32bit_python_on_64bit_windows:
            dndplat_folder_to_keep = 'win-x86'
        elif mach == 'x86': # Настоящая 32-битная машина или 32-битный Python на 32-битной ОС
            dndplat_folder_to_keep = 'win-x86'
        elif mach == 'AMD64': # 64-битный Python на 64-битной ОС
            dndplat_folder_to_keep = 'win-x64'
        elif mach == 'ARM64':
            dndplat_folder_to_keep = 'win-arm64'

    if dndplat_folder_to_keep:
        print(f"Filtering tkdnd versions in '{tkdnd_final_path}', keeping: '{dndplat_folder_to_keep}'")
        if not (tkdnd_final_path / dndplat_folder_to_keep).is_dir():
            print(f"  CRITICAL WARNING: Target tkdnd platform folder '{dndplat_folder_to_keep}' not found. Drag'n'Drop will likely NOT work!")
        else:
            for item in tkdnd_final_path.iterdir():
                if item.is_dir() and item.name != dndplat_folder_to_keep:
                    # Восстанавливаем вашу оригинальную логику "не удалять x64, если целевая x86"
                    # if item.name.startswith(dndplat_folder_to_keep[:3]) and item.name.endswith("x64") and dndplat_folder_to_keep.endswith("x86"):
                    #    print(f"  Specific case: Keeping {item.name} for {dndplat_folder_to_keep} compatibility.")
                    #    continue
                    # Эта логика была в вашем оригинале: if i[:3] == dndplat[:3] and i.endswith("x64") and dndplat.endswith('x86'): continue
                    # Если dndplat_folder_to_keep = 'win-x86', а item.name = 'win-x64', то условие будет:
                    # 'win' == 'win' (True) AND 'win-x64'.endswith('x64') (True) AND 'win-x86'.endswith('x86') (True) => continue
                    # То есть, если собираем для x86, папка x64 НЕ удаляется. Это может быть сделано для универсальности сборки,
                    # но обычно оставляют только точную целевую.
                    # Если вы хотите удалить все, КРОМЕ dndplat_folder_to_keep, то код ниже правильный.
                    # Если нужна более сложная логика сохранения, ее нужно реализовать здесь.
                    print(f"  Removing tkdnd platform folder: {item.name}")
                    shutil.rmtree(item, ignore_errors=True)
    else:
        print(f"Warning: Could not determine target tkdnd platform in '{tkdnd_final_path}'. All versions might be kept.")
else:
    if source_bin_dir.is_dir() and (source_bin_dir / 'tkdnd').is_dir():
         print(f"Warning: tkdnd directory was expected but not found at '{tkdnd_final_path}' after copying.")

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
if dist_output_path.is_dir() and any(dist_output_path.iterdir()):
    zip_output_target_file = current_dir_path / final_zip_archive_name
    zip_dist_folder_contents(str(dist_output_path), str(zip_output_target_file))
else:
    print(f"Error: Distribution directory '{dist_output_path}' is empty or not found. Archiving failed.")

print("Build script finished.")
