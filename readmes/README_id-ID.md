> [!IMPORTANT]
> Kami menulis ulang proyek. Proyek ini saat ini telah berhenti memperbarui!
> Tapi kami masih akan menerima perbaikan bug dan permintaan menarik
# MIO-KITCHEN-SOURCE #
![spanduk](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/a9bcfdf613ad28e82f7899e3d420d76ecfea174c/splash.png)
#### Alat rom yang ditulis dalam python
##### Alat ROM bebas dan open source terbaik untuk Anda
> [!CAUTION]
> Penggunaan komersial yang tidak sah dilarang
***
## Alat ini menggunakan banyak proyek sumber terbuka.Teriakan besar untuk pengembang!
***
## Localization
### [日本語](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_ja-JP.md) | [中文](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_zh-CN.md) | [Português brasileiro](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_pt-BR.md) | [Deutsch](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_de-DE.md) | [Русский язык](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_ru-RU.md) | [Indonesian](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_id-ID.md) | [Tiếng Việt](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/main/README_vi-VN.md)
***
## Fitur
* Membongkar `boot, dtbo, ext4, erofs, payload, logo` dan sebagainya
* Mengemas `boot, dtbo, ext4, erofs, logo` dan sebagainya
***
## Keuntungan
* Patch Otomatis FS_Config dan FS_Context
* Antarmuka grafis GUI
* Manajer plugin grafis, ditambah editor untuk pengeditan skrip plugin.Dukungan Plugin Memasang dan Mengekspor
* Pembaruan cepat, aman, stabil dan cepat
* Interpreter MSH unik yang mendukung menjalankan skrip MSH
* Memberikan kompatibilitas mundur dengan Android 8 dan lebih rendah dan buat .img untuk versi ini
* Gunakan file MKC Pilih API di Linux, membuatnya lebih mudah digunakan
***
## OS yang didukung

|   Os    | Arch                             |
|:-------:|----------------------------------|
|  Linux  | x86_64 arm64                     |
| Windows | x86_64 x86 amd64 arm64(by sewzj) |
|  Macos  | Arm64  X86                       |
## Jenis gambar yang didukung
| Jenis Gambar yang Didukung |
|----------------------------|
| Android Boot Image         |
| Android Recovery Image     |
| Android Vendor_boot Image  |
| Erofs                      |
| Ext4                       |
| F2fs(Linux Version)        |
| Romfs                      |
| Payload                    |
## Jenis file yang didukung
| Jenis file yang didukung |
|----------------------|
| Zip                  |
| Sprd PAC             |
| ops                  |
| Ozip                 |
| tar.md5              |
| kdz/dz               |
| ofp                  |
| tar.gz               |
## Manajer Mio-Kitchen
>[!NOTE]
>Ini adalah util untuk mengelola alat mio-kitchen.
<details><summary>Perbarui biner Prebulit</summary>

```` shell
python3 config upbin
````

</details>

<details><summary>Periksa apakah didukung mesin saya</summary>

```` shell
python3 config chksupd
````

</details>


## Mulai gunakan
> [!NOTE]
> Saat ini hanya mendukung Python 3.8 dan lebih baru!
### Prasyarat
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

### Mulai
```` shell
python tool.py
# Untuk membuat distribusi biner, Anda bisa:
python build.py
````
***
# Hubungi kami
***
Email pengembang ###: 3590361911@qq.com
### QQ Group: 683828484
### Pengembang QQ Group: 777617022
***
# Contributors:
***
### [![contributors](https://contrib.rocks/image?repo=ColdWindScholar/MIO-KITCHEN-SOURCE&max=999&column=20)](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/graphs/contributors)
### Terima kasih kepada orang -orang seperti Anda yang telah membantu!
***
# Tentang
***
### Mio-kitchen
```
Selalu Gratis, pengguna terlebih dahulu
Alat berkualitas, disajikan di sini!
Membawa Anda dengan tim mio-kitchen
```
#### ColdWindScholar (3590361911@qq.com) Semua hak dilindungi undang -undang. ####
