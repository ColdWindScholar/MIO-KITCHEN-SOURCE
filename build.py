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

current_os_type = platform.system()
# Имена, как в твоем оригинальном скрипте
if current_os_type == 'Linux':
    output_final_zip_name = 'MIO-KITCHEN-linux.zip'
elif current_os_type == 'Darwin':
    if platform.machine() == 'x86_64': # Используем platform.machine() напрямую
        output_final_zip_name = 'MIO-KITCHEN-macos-intel.zip'
    else:
        output_final_zip_name = 'MIO-KITCHEN-macos.zip'
    try: from tkinter import END 
    except ImportError: print("CRITICAL: Tkinter is not available on this macOS system!")
elif current_os_type == 'Windows':
    output_final_zip_name = 'MIO-KITCHEN-win.zip'
else:
    print(f"Warning: Unsupported OS type: {current_os_type}. Using generic zip name.")
    output_final_zip_name = f'MIO-KITCHEN-{current_os_type.lower()}.zip'

# Имя для исполняемого файла и папки, создаваемой PyInstaller (можно оставить простым)
pyinstaller_output_name = "tool" 

print("Building application with PyInstaller...")
import PyInstaller.__main__

pyinstaller_args = [
    os.path.join(project_root_dir, 'tool.py'), 
    '--name', pyinstaller_output_name,
    '-D',                                    # One-dir build
    '--console',                             # Отладочная консоль
    # '-w',                                  # Для релиза без консоли
    '--icon', os.path.join(project_root_dir, 'icon.ico'),
    '--exclude-module', 'numpy',
    '--collect-data', 'sv_ttk',
    '--collect-data', 'chlorophyll',
    '--paths', os.path.join(project_root_dir, 'src'),
]

# Файлы и папки для включения в сборку
# Источник относительно project_root_dir, назначение относительно корня сборки
data_to_bundle = [
    # Вся папка bin из корня проекта копируется в папку 'bin' внутри сборки
    (os.path.join(project_root_dir, 'bin'), 'bin'),
    # Файл LICENSE из корня проекта копируется в корень сборки
    (os.path.join(project_root_dir, 'LICENSE'), '.'),
    # Файл config из корня проекта копируется в корень сборки
    (os.path.join(project_root_dir, 'config'), '.'),
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
# Это папка, созданная PyInstaller, например, dist/tool/
app_build_output_folder = os.path.join(dist_path, pyinstaller_output_name) 

if not os.path.isdir(app_build_output_folder):
    print(f"CRITICAL: PyInstaller output directory not found: {app_build_output_folder}")
    sys.exit(1)

# Очистка ненужных версий tkdnd
tkdnd_path_in_bundle = os.path.join(app_build_output_folder, 'bin', 'tkdnd')
dndplat_to_keep = None
current_machine_arch_for_dnd = platform.machine()

if current_os_type == 'Darwin':
    dndplat_to_keep = 'osx-arm64' if current_machine_arch_for_dnd == 'arm64' else 'osx-x64'
elif current_os_type == 'Linux':
    dndplat_to_keep = 'linux-arm64' if current_machine_arch_for_dnd == 'aarch64' else 'linux-x64'
elif current_os_type == 'Windows':
    win_py_arch, _ = platform.architecture()
    # Корректное определение для 32-битного Python на 64-битной Windows
    if win_py_arch == '32bit' and current_machine_arch_for_dnd == 'AMD64':
        dndplat_to_keep = 'win-x86'
    elif current_machine_arch_for_dnd == 'x86': # Нативный 32-bit или уже скорректированный
        dndplat_to_keep = 'win-x86'
    elif current_machine_arch_for_dnd == 'AMD64': # Нативный 64-bit
        dndplat_to_keep = 'win-x64'
    elif current_machine_arch_for_dnd == 'ARM64':
        dndplat_to_keep = 'win-arm64'

if dndplat_to_keep and os.path.isdir(tkdnd_path_in_bundle):
    print(f"Cleaning tkdnd libraries in bundle, keeping only for: {dndplat_to_keep}")
    for item_name in os.listdir(tkdnd_path_in_bundle):
        item_full_path = os.path.join(tkdnd_path_in_bundle, item_name)
        if os.path.isdir(item_full_path) and item_name != dndplat_to_keep:
            print(f"Removing: {item_full_path}")
            shutil.rmtree(item_full_path, ignore_errors=True)
elif not dndplat_to_keep:
    print(f"Warning: Could not determine specific tkdnd platform for {current_os_type}/{current_machine_arch_for_dnd}. All tkdnd versions will be kept.")
else:
    print(f"Warning: TkDnD path not found in bundle: {tkdnd_path_in_bundle}. Skipping tkdnd cleanup.")

# Установка прав на выполнение для POSIX систем
if os.name == 'posix':
    print(f"Setting executable permissions for POSIX in: {app_build_output_folder}")
    main_exe_path_posix = os.path.join(app_build_output_folder, pyinstaller_output_name)
    if os.path.exists(main_exe_path_posix):
        try:
            print(f"  chmod +x {main_exe_path_posix}")
            os.chmod(main_exe_path_posix, os.stat(main_exe_path_posix).st_mode | 0o111)
        except Exception as e_chmod_main_posix:
            print(f"  Warning: Failed to chmod main executable {main_exe_path_posix}: {e_chmod_main_posix}")

    bundled_bin_path_posix = os.path.join(app_build_output_folder, 'bin')
    if os.path.isdir(bundled_bin_path_posix):
        # Список бинарников, которым нужны права на выполнение
        executables_in_bin = ["exec.sh", "dtc", "magiskboot", "zstd", "brotli", "lpmake", 
                              "mkfs.erofs", "extract.erofs", "make_ext4fs", "mke2fs", 
                              "e2fsdroid", "img2simg", "simg2img"] 
        # Добавь сюда другие специфичные для платформ исполняемые файлы, если они есть в bin/<OS>/
        for root, _, files in os.walk(bundled_bin_path_posix):
            for file_item in files:
                # Проверяем по имени или расширению
                if file_item.endswith(".sh") or file_item in executables_in_bin or \
                   (current_os_type == 'Linux' and file_item in ["busybox"]) or \
                   (current_os_type == 'Darwin' and file_item in ["busybox"]): # Пример
                    file_path_to_chmod = os.path.join(root, file_item)
                    try:
                        print(f"  chmod +x {file_path_to_chmod}")
                        os.chmod(file_path_to_chmod, os.stat(file_path_to_chmod).st_mode | 0o111)
                    except Exception as e_chmod_bin_posix:
                        print(f"  Warning: Failed to chmod binary {file_path_to_chmod}: {e_chmod_bin_posix}")

# Создание финального ZIP архива с именем, как в оригинале
final_zip_full_path = os.path.join(project_root_dir, output_final_zip_name) # ZIP будет в корне проекта
print(f"Creating final ZIP archive: {final_zip_full_path}")

if os.path.isdir(app_build_output_folder): # Для one-dir сборки
    # Чтобы в архиве была папка MIO-KITCHEN-.../tool.exe, MIO-KITCHEN-.../bin/, и т.д.
    # мы можем временно переименовать app_build_output_folder (например, dist/tool)
    # в имя нашего ZIP-архива без расширения, заархивировать, а потом вернуть имя обратно.
    # Или проще: архивировать содержимое app_build_output_folder, но в ZIP класть это в папку
    # с именем output_final_zip_name (без .zip).

    # Вариант 1: Архивируем папку app_build_output_folder (например, 'tool') как есть
    # Тогда при распаковке будет папка 'tool'. Пользователь может переименовать.
    # os.chdir(dist_path)
    # try:
    #     with zipfile.ZipFile(final_zip_full_path, "w", zipfile.ZIP_DEFLATED) as archive:
    #         for root, _, files in os.walk(pyinstaller_app_name): 
    #             for file_item in files:
    #                 file_path_in_dist = os.path.join(root, file_item)
    #                 archive.write(file_path_in_dist, file_path_in_dist) 
    #     print(f"Successfully created {final_zip_full_path}")
    # except Exception as e_zip_dir:
    #     print(f"Error creating ZIP for one-dir: {e_zip_dir}")
    # finally:
    #     os.chdir(project_root_dir)

    # Вариант 2: Создаем структуру MIO-KITCHEN-os/ внутри ZIP
    # Для этого нужно архивировать каждый файл с измененным путем.
    # Проще всего создать временную папку с нужным именем, скопировать туда содержимое
    # app_build_output_folder, заархивировать эту временную папку и удалить ее.
    
    temp_archive_folder_name = os.path.splitext(output_final_zip_name)[0] # e.g., "MIO-KITCHEN-linux"
    temp_archive_folder_path = os.path.join(dist_path, temp_archive_folder_name)

    if os.path.exists(temp_archive_folder_path):
        shutil.rmtree(temp_archive_folder_path) # Удаляем, если существует от предыдущей сборки
    
    try:
        shutil.copytree(app_build_output_folder, temp_archive_folder_path) # Копируем dist/tool в dist/MIO-KITCHEN-linux
        
        os.chdir(dist_path) # Переходим в dist, чтобы архивировать MIO-KITCHEN-linux/
        with zipfile.ZipFile(final_zip_full_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, dirnames, files in os.walk(temp_archive_folder_name):
                 if ".git" in dirnames: dirnames.remove(".git")
                 for file_item in files:
                    file_path_in_temp_archive_folder = os.path.join(root, file_item)
                    print(f"  Adding to ZIP: {file_path_in_temp_archive_folder}")
                    archive.write(file_path_in_temp_archive_folder, file_path_in_temp_archive_folder)
        print(f"Successfully created {final_zip_full_path}")
        
    except Exception as e_zip_final:
        print(f"Error creating final ZIP structure: {e_final_zip}")
    finally:
        if os.path.exists(temp_archive_folder_path):
            shutil.rmtree(temp_archive_folder_path) # Удаляем временную папку
        os.chdir(project_root_dir) # Возвращаемся в корень проекта

else:
    print(f"Output directory {app_bundle_path} not found for zipping.")

print("Build script finished.")
