import argparse
import os
import zipfile
from functools import wraps
from sys import exit
from time import strftime, time
import json
import requests
import warnings
import re
warnings.warn = lambda *args:...
temp = 'bin/temp'
update_info = 'bin/update.json'
LOGE = lambda info: print('[%s] \033[91m[ERROR]\033[0m%s\n' % (strftime('%H:%M:%S'), info))
LOGS = lambda info: print('[%s] \033[92m[SUCCESS]\033[0m%s\n' % (strftime('%H:%M:%S'), info))
green = lambda info: print(f"\033[32m[{strftime('%H:%M:%S')}]{info}\033[0m")
#青
green_1:print = lambda info, end=None: print(f"\033[36m[{strftime('%H:%M:%S')}]{info}\033[0m", end=end)
log:print = lambda info, end=None: print(f"[{strftime('%H:%M:%S')}]{info}", end=end)
red = lambda info: print(f"\033[31m{info}\033[0m")
yellow = lambda info: print(f"\033[33m{info}\033[0m")
blue = lambda info: print(f"\033[34m{info}\033[0m")
cyan = lambda info: print(f"\033[37m{info}\033[0m")


class JsonEdit:
    def __init__(self, file_path):
        self.file = file_path

    def read(self):
        if not os.path.exists(self.file):
            return {}
        with open(self.file, 'r+', encoding='utf-8') as pf:
            try:
                return json.load(pf)
            except (AttributeError, ValueError, json.decoder.JSONDecodeError):
                return {}

    def write(self, data):
        with open(self.file, 'w+', encoding='utf-8') as pf:
            json.dump(data, pf, indent=4)

    def edit(self, name, value):
        data = self.read()
        data[name] = value
        self.write(data)
# Links
links = {
    "erofs_utils":{
        "link":"https://api.github.com/repos/sekaiacg/erofs-utils/releases/latest",
        "github_json":True,
        # erofs-utils-v1.8.4-gc9629116-Android_arm64-v8a-2501262050.zip
        "name_pattern":r"erofs-utils-(.*?)-(.*?)-(\D+?)_(.*)-\d+(?:-\d+)?.zip$"
    }
}

def download_api(url, path=None, int_=True, size_=0, name:str=None):
    if url is None:
        LOGE("URL not valid.")
        return 1
    if path is None:
        LOGE("The Path Isn't Valid.")
        return 1

    start_time = time()
    response = requests.Session().head(url)
    file_size = int(response.headers.get("Content-Length", 0))
    response = requests.Session().get(url, stream=True, verify=False)
    last_time = time()
    if file_size == 0 and size_:
        file_size = size_
    if not name:
        name = os.path.basename(url)
    with open(path + os.sep + name, "wb") as f:
        chunk_size = 2048576
        chunk_kb = chunk_size / 1024
        bytes_downloaded = 0
        for data in response.iter_content(chunk_size=chunk_size):
            f.write(data)
            bytes_downloaded += len(data)
            elapsed = time() - start_time
            # old method
            # speed = bytes_downloaded / 1024 / elapsed
            used_time = time() - last_time
            speed = chunk_kb / used_time
            last_time = time()
            percentage = (int((bytes_downloaded / file_size) * 100) if int_ else (
                                                                                             bytes_downloaded / file_size) * 100) if file_size != 0 else "None"
            yield percentage, speed, bytes_downloaded, file_size, elapsed

class Caller:
    def __init__(self, ):
        ...
    @staticmethod
    def verity() -> bool:
        if not os.path.exists(temp):
            os.makedirs(temp, exist_ok=True)
        if not os.path.exists(update_info):
            JsonEdit(update_info).write({})
        if not os.path.exists('bin/setting.ini'):
            LOGE("Please Run The Tool under the MIO-KITCHEN/TIK Root Dir.")
            return False
        return True

    def __call__(self, func):
        @wraps(func)
        def call_func(*args, **kwargs):
            if not self.verity():
                return lambda *args: ...
            green(f"Start: [{func.__name__}]")
            func(*args, **kwargs)
        return call_func

caller = Caller()
arch_list = {
    "arm64-v8a":"aarch64",
    "armeabi-v7a":"aarch"
}
system_list = {
    "Cygwin":"Windows"
}
@caller
def update(args):
    for name, content in links.items():
        blue(f"Updating {name}")
        if content.get('github_json', False):
            url = requests.get(content.get('link'))
            json_:dict = json.loads(url.text)
            green_1(f"Found {name}{json_.get('tag_name')}")
            if JsonEdit(update_info).read().get(name) == json_.get('tag_name'):
                yellow(f"{name} was latest already!")
                continue
            assets = json_.get('assets')
            for a in assets:
                browser_download_url = a.get('browser_download_url', None)
                name = a.get('name', None)
                size = a.get("size", None)

                log(f'Downloading {name}')
                for percentage, _, _, _, _ in download_api(url=browser_download_url, name=name, size_=size, path=temp):
                    green_1(f"\rPercentage:{percentage} %", end='')
                downloaded_file = os.path.join(temp, name)
                version, gitid, system, arch = re.search(content.get('name_pattern', "*$"), name).groups()
                system = system_list.get(system, system)
                if os.name == 'nt' and arch == 'x86_64':
                    arch = "AMD64"
                if system == 'Darwin' and arch == 'aarch64':
                    arch = 'arm64'
                else:
                    arch = arch_list.get(arch, arch)
                yellow(f"\nVersion:{version}\nGitid:{gitid}\nSystem:{system}\nArch:{arch}")
                if os.path.exists(downloaded_file):
                    if not zipfile.is_zipfile(downloaded_file):
                        LOGE("Not Update it.Skip")
                        continue
                else:
                    LOGE("Not Update it.Skip")
                    continue
                with zipfile.ZipFile(downloaded_file) as z:
                    for z_name in z.namelist():
                        if os.path.exists(f'bin/{system}/{arch}/{z_name}'):
                            z.extract(z_name, path=f'bin/{system}/{arch}')
                            green(f"Update {z_name}")
                origin_info = JsonEdit(update_info).read()
                origin_info[name] = json_.get('tag_name')
                JsonEdit(update_info).write(origin_info)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='config', description='The tool to config/manage MIO-KITCHEN', exit_on_error=False)
    subparser = parser.add_subparsers(title='Supported subcommands',
                                           description='Valid subcommands')
    unpack_rom_parser = subparser.add_parser('upbin', help="update binary")
    unpack_rom_parser.set_defaults(func=update)
    subcmd, subcmd_args = parser.parse_known_args()
    if not hasattr(subcmd, 'func'):
        parser.print_help()
        exit(1)
    try:
        subcmd.func(subcmd_args)
    except TypeError as e:
        print(e)
        parser.print_help()
