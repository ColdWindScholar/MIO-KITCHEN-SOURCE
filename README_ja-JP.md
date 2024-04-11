# MIO-KITCHEN-SOURCE #
![Banner](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/a9bcfdf613ad28e82f7899e3d420d76ecfea174c/splash.png)
#### Python言語を使用した、Android ROMツール
***
## このツールは多くのオープンソースプロジェクトを使用しています。開発者に敬意を表します!
***
## Localization
### Chinese: [zh-CN](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_zh-CN.md)
### English: [en-US](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README.md)
### Portuguese (Brazil): [pt-BR](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_pt-BR.md)
### German: [de-DE](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_de-DE.md)
***
## 機能
* `boot、dtbo、ext4、erofs、payload、logo`などをアンパック
* `boot、dtbo、ext4、erofs、payload、logo`などをパッキング
***
## 長所
* コンテキストの自動修復
* GUI (グラフィカルユーザインターフェース)
* プラグインのグラフィカルな解析、プラグインの編集、プラグインのインストール、プラグインのエクスポートをサポート
* 迅速なアップデートと安全かつ安定な提供
* MSHスクリプトの実行をサポートする、独自のMSHインタープリター
* Android 8以下のROMのインストールをサポート、IMGとしてのパッケージング
* LinuxでMKCファイル選択のAPIを使用
***
## * macOSに関するお知らせ
``` shell
# [brotli]を使用する場合はそれが必要になります:
# システム内に入っているかもしれないので確認をしてください
# 
brew install gettext
```
## 使用開始
### 必要となる準備
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

### それではスタート
```` shell
python tool.py
# to create a binary distribution, you could:
python build.py
````
***
# 連絡先
***
### 開発者のメール: 3590361911@qq.com
### QQ グループ: 836898509
### Telegram グループ: [Mio Android Kitchen Chat](https://t.me/mio_android_kitchen_group)
### Telegram チャンネル: [Mio Android Kitchen Updates](https://t.me/mio_android_kitchen)
***
# 貢献者:
***
### macOS prebuilt binary for several tools: [sk](https://github.com/sekaiacg)
### Some part of the code: [Affggh](https://github.com/affggh)
### Logo co-designer: [Shaaim](https://github.com/786-shaaim)
### Japanese translator: [reindex-ot](https://github.com/reindex-ot)
### Portuguese (Brazil) translator: [igor](https://github.com/igormiguell)
### German translator: [keldrion](https://github.com/keldrion)
### And MORE...
### ご協力ありがとうございます!
***
# このアプリケーションについて
***
### MIO-KITCHEN
```
永久に無料、ユーザーファースト
素晴らしいツールが勢揃い!
文章: MIO-KITCHEN-TEAM
```
#### ColdWindScholar (3590361911@qq.com) All Rights Reserved. ####
