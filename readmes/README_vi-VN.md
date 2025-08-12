> [!IMPORTANT]
> Chúng tôi đang viết lại dự án. Hiện tại dự án này đã ngừng cập nhật!
> Tuy nhiên, chúng tôi vẫn chấp nhận sửa lỗi và pull request
# MIO-KITCHEN-SOURCE #
![Banner](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/a9bcfdf613ad28e82f7899e3d420d76ecfea174c/splash.png)
#### Một công cụ Rom viết bằng Python
##### Công cụ Rom miễn phí và mã nguồn mở tốt nhất dành cho bạn
> [!CAUTION]
> Nghiêm cấm sử dụng cho mục đích thương mại khi chưa được cho phép
***
## Dự án sử dụng

|             Tên               | Mục đích sử dụng                             | Liên kết                                                             |     Tác giả |
|:-----------------------------:|----------------------------------------------|----------------------------------------------------------------------|------------:|
|           unpac_py            | Giải nén tệp sprd pac                         | [Link](https://github.com/affggh/unpac_py)                          |      Affggh |
|            fspatch            | Vá file_config trước khi giải nén            | [Link](https://github.com/affggh/fspatch)                           |      Affggh |
|         Logo_dumper           | Giải nén và đóng gói lại Xiaomi lOGO.IMG     | [Link](https://github.com/affggh/logo_dumper)                       |      Affggh |
|     mtk-garbage-porttool      | Hỗ trợ đóng gói lại thư mục Android cũ       | [Link](https://github.com/ColdWindScholar/mtk-garbage-porttool)     |      Affggh |
|      context_pacther          | Vá file_context trước khi đóng gói lại       | [Link](https://github.com/ColdWindScholar/context_patch)            | ColdWindScholar |
|           lpunpack            | Giải nén và phân tích Super Image của Android| [Link](https://github.com/unix3dgforce/lpunpack)                    |  unix3dgforce |
|        android-tools          | Đóng gói lại ext4, chuyển đổi sparse, lpmake | [Link](https://github.com/nmeum/android-tools)                      |       nmeum |
|           cpio_py             | Giải nén và đóng gói lại cpio                | [Link](https://github.com/ColdWindScholar/cpio_py)                  | ColdWindScholar |
|         erofs-utils           | Giải nén và đóng gói image Erofs               | [Link](https://github.com/sekaiacg/erofs-utils)                     |    sekaiacg |
|         make_ext4fs           | Đóng gói lại image ext4 cho thiết bị cũ        | [Link](https://github.com/anpaza/make_ext4fs)                       |      anpaza |
|             ext4              | Phân tích và giải nén image ext4               | [Link](https://github.com/cubinator/ext4)                           |   cubinator |
|         Busybox_w64           | Hỗ trợ plugin                                | [Link](https://frippery.org/busybox/)                               | Ron Yorston |
|           Busybox             | Hỗ trợ plugin                                | [Link](http://busybox.net/)                                         | Erik Andersen |
|            brotli             | Giải nén và đóng gói lại file .br            | [Link](https://github.com/google/brotli)                            |      Google |
|          sdat2img             | Chuyển đổi dat sang img                      | [Link](https://github.com/xpirt/sdat2img)                           |       xpirt |
|          img2sdat             | Chuyển đổi img sang sparse dat               | [Link](https://github.com/xpirt/img2sdat)                           |       xpirt |
|          kdztools             | Giải nén tệp kdz và dz                       | [Link](https://github.com/ehem/kdztools)                            |        ehem |
|             dtc               | Dịch ngược và biên dịch tập tin tree thiết bị| [Link](https://android.googlesource.com/platform/external/dtc/)     | David Gibson |
|        oppo_decrypt           | Giải mã ozip và ofp                          | [Link](https://github.com/bkerler/oppo_decrypt)                     |     bkerler |
|         splituapp             | Phân tích và giải nén UPDATE.APP             | [Link](https://github.com/superr/splituapp)                         |      Superr |
|          libufdt              | Phân tích, giải nén, đóng gói image dtbo       | [Link](https://android.googlesource.com/platform/system/libufdt/)   |      Google |
|       ROMFS_PARSER            | Giải nén tệp Romfs                           | [Link](https://github.com/ddddhm1234/ROMFS_PARSER/tree/main)        |   ddddhm123 |
|        Nh4RomTools            | Code vô hiệu hoá vb                          | [Link](https://github.com/affggh/NH4RomTool)                        |      Affggh |
|             zstd              | Giải nén và đóng gói tệp zstd                | [Link](https://github.com/facebook/zstd)                            |    facebook |
* Và nhiều dự án khác! Xin gửi lời cảm ơn đến các nhà phát triển!

***
## Đa ngôn ngữ
### [日本語](README_ja-JP.md) | [中文](README_zh-CN.md) | [Português brasileiro](README_pt-BR.md) | [Deutsch](README_de-DE.md) | [Русский язык](README_ru-RU.md) | [Indonesian](README_id-ID.md) | [Tiếng Việt](README_vi-VN.md)
***
## Tính năng
* Giải nén `boot, dtbo, ext4, erofs, payload, logo` và nhiều loại khác
* Đóng gói `boot, dtbo, ext4, erofs, logo` và nhiều loại khác
***
## Ưu điểm
* Tự động vá fs_config và fs_context
* Giao diện đồ họa GUI dễ sử dụng
* Quản lý plugin đồ họa, có trình chỉnh sửa script plugin, hỗ trợ cài đặt và xuất plugin
* Cập nhật nhanh, bảo mật, ổn định và tốc độ cao
* Trình thông dịch MSH độc quyền hỗ trợ chạy script MSH
* Hỗ trợ ngược Android 8 và thấp hơn, có thể tạo image .img cho các phiên bản này
* Hỗ trợ chọn tệp kiểu mkc trên Linux, dễ sử dụng hơn
***
## Hệ điều hành được hỗ trợ

|  Hệ điều hành | Kiến trúc                       |
|:-------------:|----------------------------------|
|    Linux      | x86_64 arm64                     |
|   Windows     | x86_64 x86 amd64 arm64 (sewzj)   |
|    Macos      | Arm64 X86                        |

## Loại image được hỗ trợ
| Các loại image được hỗ trợ    |
|-----------------------------|
| Android Boot Image          |
| Android Recovery Image      |
| Android Vendor_boot Image   |
| Erofs                       |
| Ext4                        |
| F2fs (phiên bản Linux)      |
| Romfs                       |
| Payload                     |

## Các định dạng tệp hỗ trợ
| Các định dạng tệp hỗ trợ |
|--------------------------|
| Zip                      |
| Sprd PAC                 |
| ops                      |
| Ozip                     |
| tar.md5                  |
| kdz/dz                   |
| ofp                      |
| tar.gz                   |

## Trình quản lý MIO-KITCHEN
>[!NOTE]
>Là tiện ích quản lý công cụ MIO-KITCHEN.
<details><summary>Cập nhật nhị phân dựng sẵn</summary>

```
python3 config upbin
```

</details>

<details><summary>Kiểm tra máy của tôi có được hỗ trợ không</summary>

```
python3 config chksupd
```

</details>

## Bắt đầu sử dụng
> [!NOTE]
> Hiện tại chỉ hỗ trợ Python 3.8 trở lên!

### Yêu cầu cài đặt

<details><summary>macOS</summary>

```
brew install python3-tk python3 tcl-tk
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
```

</details>

<details><summary>Linux</summary>

```
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
sudo apt update -y && sudo apt install python3-tk -y
```

</details>

<details><summary>Windows</summary>

```
python -m pip install -U --force-reinstall pip
pip install -r requirements.txt
```

</details>

### Khởi chạy

```
python tool.py
# Để tạo bản phân phối nhị phân:
python build.py
```

***
# Liên hệ
***
### Email nhà phát triển: 3590361911@qq.com  
### Nhóm QQ: 683828484  
### Nhóm nhà phát triển QQ: 777617022  
***
# Người đóng góp
***
### [![contributors](https://contrib.rocks/image?repo=ColdWindScholar/MIO-KITCHEN-SOURCE&max=999&column=20)](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/graphs/contributors)
### Cảm ơn những người như bạn đã giúp đỡ!
***
# Giới thiệu
***
### MIO-KITCHEN
```
Luôn miễn phí, người dùng là ưu tiên
Công cụ chất lượng, được giới thiệu tại đây!
Mang đến cho bạn bởi đội ngũ MIO-KITCHEN
```
#### ColdWindScholar (3590361911@qq.com) Bảo lưu mọi quyền. ####
