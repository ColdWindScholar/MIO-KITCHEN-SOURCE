# MIO-KITCHEN-SOURCE #
![Banner](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/a9bcfdf613ad28e82f7899e3d420d76ecfea174c/splash.png)
#### A Rom Tool Written in Python
> [!CAUTION]
> Unauthorized commercial use prohibited
***
## This tool uses many open source projects. Huge shout out to the developers!
***
## Localization
### 日本語: [ja-JP](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_ja-JP.md)
### 中文: [zh-CN](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_zh-CN.md)
### Portuguese (Brazil): [pt-BR](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_pt-BR.md)
### German: [de-DE](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_de-DE.md)
***
## Features
* Unpack `boot, dtbo, ext4, erofs, payload, logo` and so on
* Pack `boot, dtbo, ext4, erofs, payload, logo` and so on
***
## Advantages
* Automatic fs_config and fs_context patch
* GUI graphical interface
* A graphical plugin manager, plus an editor for plugin script editing. Support plugin installing and exporting
* Quick updates, secure, stable and fast
* Unique MSH interpreter that supports running MSH scripts
* Provide backward compatibility with Android 8 and lower and create .img for these versions
* Use mkc file choose api on Linux, making it easier to use
***
## Supported Os

| Os      | Arch                   |
|---------|------------------------|
| Linux   | x86_64 arm64           |
| Windows | x86_64 x86 amd64 arm64 |
| Macos   | Arm64  X86             |

## * macOS Notice
``` shell
# If you want to use [brotli], you need:
# You system may had it already, so check first.
# 
brew install gettext
```
## Start To Use
> [!NOTE]
> Currently Only Support Python 3.8 and Newer!
### Prerequisites
<details><summary>macOS</summary>

```` shell
brew install python-tk python3  tcl-tk
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
````

</details>

<details><summary>Linux</summary>

```` shell
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
sudo apt update -y && sudo apt install python3-tk -y
````

</details>

<details><summary>Windows</summary>

```` shell
python -m pip install -U --force-reinstall pip
pip install -r requirements.txt
````

</details>

### Get started
```` shell
python tool.py
# To create a binary distribution, you could:
python build.py
````
***
# Contact Us
***
### Developer's Email: 3590361911@qq.com
### QQ Group: 836898509
***
# Contributors:
***
### macOS prebuilt binary for several tools: [sk](https://github.com/sekaiacg)
### Some part of the code: [Affggh](https://github.com/affggh)
### Logo co-designer: [Shaaim](https://github.com/786-shaaim)
### Japanese translator: [reindex-ot](https://github.com/reindex-ot)
### Portuguese (Brazil) translator: [igor](https://github.com/igormiguell)
### German translator: [keldrion](https://github.com/keldrion)
### And MORE...
### Thanks to people like you for helping out!
***
# About
***
### MIO-KITCHEN
```
Always free, users first
Quality Tools, presented here!
Brought you by the MIO-KITCHEN-TEAM
```
#### ColdWindScholar (3590361911@qq.com) All Rights Reserved. ####
