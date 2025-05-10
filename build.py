#!/usr/bin/env python3
# pylint: disable=line-too-long
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
# ... (лицензия) ...

import os
import platform
import shutil
import zipfile
import sys

project_root_dir = os.path.abspath(os.path.dirname(__file__))

# --- Установка зависимостей ---
try:
    from pip._internal.cli.main import main as _pip_main
    print("Checking and installing requirements...")
    requirements_file_path = os.path.join(project_root_dir, 'requirements.txt')
    if os.path.exists(requirements_file_path):
        with open(requirements_file_path, 'r', encoding='utf-8') as req_file:
            for requirement_line in req_file:
                requirement = requirement_line.strip()
                if requirement and not requirement.startswith('#'):
                    print(f"Installing {requirement}...")
                    try:
                        _pip_main(['install', requirement])
                    except Exception as e_pip_install:
                        print(f"Warning: Failed to install {requirement}: {e_pip_install}")
    else:
        print(f"Warning: requirements.txt not found at {requirements_file_path}")
except ImportError:
    print("Warning: pip is not available. Please ensure all dependencies from requirements.txt are installed manually.")

# --- Определение имен ---
current_os_type = platform.system()
app_name_base_for_zip = "MIO-KITCHEN" # Используется для имени ZIP-архива

if current_os_type == 'Linux':
    output_final_zip_name_with_ext = f'{app_name_base_for_zip}-linux.zip'
elif current_os_type == 'Darwin':
    output_final_zip_name_with_ext = f'{app_name_base_for_zip}-macos-intel.zip' if platform.machine() == 'x86_64' else f'{app_name_base_for_zip}-macos.zip'
    try: from tkinter import END
    except ImportError: print("CRITICAL: Tkinter is not available on this macOS system!")
elif current_os_type == 'Windows':
    output_final_zip_name_with_ext = f'{app_name_base_for_zip}-win.zip'
else:
    output_final_zip_name_with_ext = f'{app_name_base_for_zip}-{current_os_type.lower()}.zip'

# Имя папки, которую создаст PyInstaller, И корневой папки в ZIP-архиве
# Это будет имя ZIP-файла без расширения .zip
pyinstaller_output_folder_name = os.path.splitext(output_final_zip_name_with_ext)[0]
# Имя исполняемого файла внутри этой папки
executable_name_in_bundle = "tool" # Если хочешь MIO-KITCHEN.exe, измени на app_name_base_for_zip

print(f"Target PyInstaller output folder (and ZIP root folder): {pyinstaller_output_folder_name}")
print(f"Target executable name inside bundle: {executable_name_in_bundle}")
print(f"Target final ZIP file name: {output_final_zip_name_with_ext}")

# --- Сборка PyInstaller ---
print("Building application with PyInstaller...")
import PyInstaller.__main__

pyinstaller_args = [
    os.path.join(project_root_dir, 'tool.py'),    # Главный скрипт в корне проекта
    '--name', executable_name_in_bundle,         # Имя .exe / исполняемого файла
    # PyInstaller создаст папку с именем executable_name_in_bundle в папке dist/
    # Мы переименуем ее позже или укажем --distpath сразу
    # '--distpath', os.path.join(project_root_dir, 'dist', pyinstaller_output_folder_name), # Указывает куда класть папку сборки
    '--distpath', os.path.join(project_root_dir, 'dist'), # PyInstaller создаст dist/executable_name_in_bundle
    '--workpath', os.path.join(project_root_dir, 'build_pyinstaller'), # Временные файлы сборки
    '--specpath', project_root_dir,              # Где создавать .spec файл
    '-D',                                        # One-dir сборка
    '--console',                                 # Оставляем консоль для отладки. Для релиза: '-w'
    # '-w',                                      # Для релиза без консоли
    '--icon', os.path.join(project_root_dir, 'icon.ico'),
    '--exclude-module', 'numpy',
    '--collect-data', 'sv_ttk',
    '--collect-data', 'chlorophyll',
    '--paths', os.path.join(project_root_dir, 'src'), # Путь к твоим модулям в src/
    '--clean', # Очищать кэш PyInstaller перед сборкой
]

data_to_bundle = [
    (os.path.join(project_root_dir, 'bin'), 'bin'),
    (os.path.join(project_root_dir, 'LICENSE'), '.'),
    (os.path.join(project_root_dir, 'config'), '.'),
    (os.path.join(project_root_dir, 'test'), 'test'),
]
for src_path, dest_in_bundle in data_to_bundle:
    if os.path.exists(src_path):
        pyinstaller_args.append(f'--add-data={src_path}{os.pathsep}{dest_in_bundle}')
    else:
        print(f"Warning: Data source path not found, skipping: {src_path}")

hidden_imports_list = ['tkinter', 'PIL', 'PIL._tkinter_finder', 'requests', 'idna']
for hi in hidden_imports_list:
    pyinstaller_args.extend(['--hidden-import', hi])

splash_file_path = os.path.join(project_root_dir, 'splash.png')
if os.path.exists(splash_file_path) and current_os_type != 'Darwin':
    pyinstaller_args.extend(['--splash', splash_file_path])

print(f"Executing PyInstaller with arguments: {' '.join(pyinstaller_args)}")
try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("PyInstaller build process finished.")
except Exception as e_pyinstaller_run:
    print(f"CRITICAL: PyInstaller execution failed: {e_pyinstaller_run}")
    sys.exit(1)

# --- Пост-обработка ---
dist_path = os.path.join(project_root_dir, 'dist')
# Исходная папка, созданная PyInstaller (например, dist/tool/)
pyinstaller_created_folder_path = os.path.join(dist_path, executable_name_in_bundle)
# Целевое имя папки (например, dist/MIO-KITCHEN-linux/)
final_app_folder_path_in_dist = os.path.join(dist_path, pyinstaller_output_folder_name)

if not os.path.isdir(pyinstaller_created_folder_path):
    print(f"CRITICAL: PyInstaller output directory not found: {pyinstaller_created_folder_path}")
    sys.exit(1)

# Переименовываем папку сборки PyInstaller в финальное имя
if pyinstaller_created_folder_path != final_app_folder_path_in_dist:
    if os.path.exists(final_app_folder_path_in_dist):
        print(f"Removing existing target folder: {final_app_folder_path_in_dist}")
        shutil.rmtree(final_app_folder_path_in_dist)
    print(f"Renaming '{pyinstaller_created_folder_path}' to '{final_app_folder_path_in_dist}'")
    os.rename(pyinstaller_created_folder_path, final_app_folder_path_in_dist)
    app_bundle_path = final_app_folder_path_in_dist # Теперь работаем с переименованной папкой
else:
    app_bundle_path = pyinstaller_created_folder_path

# УДАЛЕНА ОЧИСТКА tkdnd и bin/OS/ARCH, так как нужна структура 1в1

# Установка прав на выполнение для POSIX систем
if os.name == 'posix':
    print(f"Setting executable permissions for POSIX in: {app_bundle_path}")
    main_exe_path_posix = os.path.join(app_bundle_path, executable_name_in_bundle)
    if os.path.exists(main_exe_path_posix):
        try:
            print(f"  chmod +x {main_exe_path_posix}")
            os.chmod(main_exe_path_posix, os.stat(main_exe_path_posix).st_mode | 0o111)
        except Exception as e_chmod_main_posix:
            print(f"  Warning: Failed to chmod main executable {main_exe_path_posix}: {e_chmod_main_posix}")

    bundled_bin_path_posix = os.path.join(app_bundle_path, 'bin')
    if os.path.isdir(bundled_bin_path_posix):
        executables_in_bin = ["exec.sh", "dtc", "magiskboot", "zstd", "brotli", "lpmake", 
                              "mkfs.erofs", "extract.erofs", "make_ext4fs", "mke2fs", 
                              "e2fsdroid", "img2simg", "simg2img", "busybox"] 
        for root, _, files in os.walk(bundled_bin_path_posix):
            for file_item in files:
                is_executable_candidate = file_item.endswith(".sh") or file_item in executables_in_bin
                if not is_executable_candidate:
                    if any(platform_dir in root for platform_dir in ["Linux", "Windows", "Darwin", "Android"]):
                        if '.' not in file_item or file_item.endswith(".exe") or file_item.endswith(".dll") or file_item.endswith(".so") or file_item.endswith(".dylib"):
                             if not (file_item.endswith(".exe") or file_item.endswith(".dll")):
                                is_executable_candidate = True
                if is_executable_candidate:
                    file_path_to_chmod = os.path.join(root, file_item)
                    try:
                        print(f"  chmod +x {file_path_to_chmod}")
                        os.chmod(file_path_to_chmod, os.stat(file_path_to_chmod).st_mode | 0o111)
                    except Exception as e_chmod_bin_posix:
                        print(f"  Warning: Failed to chmod binary {file_path_to_chmod}: {e_chmod_bin_posix}")

# --- Создание финального ZIP архива ---
final_zip_full_path = os.path.join(project_root_dir, output_final_zip_name_with_ext)

print(f"Creating final ZIP archive: {final_zip_full_path}")
# Теперь app_bundle_path это dist/MIO-KITCHEN-VERSION-OS/
# Мы хотим, чтобы в ZIP-архиве была папка MIO-KITCHEN-VERSION-OS/ со всем содержимым.
if os.path.isdir(app_bundle_path): 
    os.chdir(dist_path) 
    try:
        with zipfile.ZipFile(final_zip_full_path, "w", zipfile.ZIP_DEFLATED) as archive:
            # Архивируем папку pyinstaller_output_folder_name (например, MIO-KITCHEN-linux)
            for root, dirnames, files in os.walk(pyinstaller_output_folder_name):
                 if ".git" in dirnames: dirnames.remove(".git")
                 for file_item in files:
                    file_path_to_archive = os.path.join(root, file_item)
                    print(f"  Adding to ZIP: {file_path_to_archive}")
                    archive.write(file_path_to_archive, file_path_to_archive) 
        print(f"Successfully created {final_zip_full_path}")
    except Exception as e_final_zip:
        print(f"Error creating final ZIP archive: {e_final_zip}")
    finally:
        os.chdir(project_root_dir) 
else:
    print(f"Output directory {app_bundle_path} not found for zipping.")

print("Build script finished.")
