> [!QUAN TRỌNG]
> Chúng tôi đang viết lại dự án. Dự án này hiện đã ngừng cập nhật!
> Nhưng chúng tôi vẫn sẽ chấp nhận sửa lỗi và yêu cầu kéo (pull request).

# MIO-KITCHEN-SOURCE #
![Banner](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/blob/a9bcfdf613ad28e82f7899e3d420d76ecfea174c/splash.png)

#### Một công cụ ROM được viết bằng Python  
##### Công cụ ROM miễn phí và mã nguồn mở tốt nhất dành cho bạn  
> [!CẢNH BÁO]
> Cấm sử dụng thương mại trái phép  
***
## Công cụ này sử dụng nhiều dự án mã nguồn mở. Cảm ơn các nhà phát triển!  
***
## Đa ngôn ngữ  
### [日本語](README_ja-JP.md) | [中文](README_zh-CN.md) | [Português brasileiro](README_pt-BR.md) | [Deutsch](README_de-DE.md) | [Русский язык](README_ru-RU.md) | [Indonesian](README_id-ID.md) | [Tiếng Việt](README_vi-VN.md)  
***
## Tính năng  
* Unpack `boot, dtbo, ext4, erofs, payload, logo` và nhiều định dạng khác  
* Repack `boot, dtbo, ext4, erofs, logo` và nhiều định dạng khác  
***
## Ưu điểm  
* Tự động vá fs_config và fs_context  
* Giao diện đồ họa GUI  
* Trình quản lý plugin đồ họa, cùng với trình chỉnh sửa tập lệnh plugin. Hỗ trợ cài đặt và xuất plugin  
* Cập nhật nhanh, an toàn, ổn định và hiệu quả  
* Trình thông dịch MSH độc đáo hỗ trợ chạy tập lệnh MSH  
* Tương thích ngược với Android 8 trở xuống và có thể tạo .img cho các phiên bản này  
* Sử dụng API chọn tệp mkc trên Linux, giúp sử dụng dễ dàng hơn  
***
## Hệ điều hành hỗ trợ  

|   Hệ điều hành   | Kiến trúc                          |
|:---------------:|----------------------------------|
|  Linux         | x86_64 arm64                     |
| Windows       | x86_64 x86 amd64 arm64 (bởi sewzj) |
|  MacOS        | Arm64 X86                         |

## Các loại img hỗ trợ  
| Loại img được hỗ trợ |
|--------------------------|
| Android Boot Image       |
| Android Recovery Image   |
| Android Vendor_boot Image |
| Erofs                    |
| Ext4                     |
| F2fs (phiên bản Linux)   |
| Romfs                    |
| Payload                  |

## Các loại tệp hỗ trợ  
| Loại tệp hỗ trợ |
|-----------------|
| Zip            |
| ops            |
| Ozip           |
| tar.md5        |
| kdz/dz         |
| ofp            |
| tar.gz         |

## Bắt đầu sử dụng  
> [!LƯU Ý]
> Hiện tại chỉ hỗ trợ Python 3.8 trở lên!  

### Yêu cầu cài đặt  
<details><summary>macOS</summary>

````shell
brew install python-tk python3 tcl-tk
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
````

</details>

<details><summary>Linux</summary>

````shell
python3 -m pip install -U --force-reinstall pip
pip install -r requirements.txt
sudo apt update -y && sudo apt install python3-tk -y
````

</details>

<details><summary>Windows</summary>

````shell
python -m pip install -U --force-reinstall pip
pip install -r requirements.txt
````

</details>

### Bắt đầu  
````shell
python tool.py
# Để tạo phân phối nhị phân, bạn có thể sử dụng:
python build.py
````
***
# Liên hệ với chúng tôi  
***
### Email nhà phát triển: 3590361911@qq.com  
### Nhóm QQ: 683828484  
### Nhóm phát triển QQ: 777617022  
***
# Người đóng góp:  
***
### [![contributors](https://contrib.rocks/image?repo=ColdWindScholar/MIO-KITCHEN-SOURCE&max=999&column=20)](https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/graphs/contributors)  
### Cảm ơn những người đã đóng góp!  
***
# Giới thiệu  
***
### MIO-KITCHEN  
```
Luôn miễn phí, người dùng là trên hết
Công cụ chất lượng, được giới thiệu tại đây!
Mang đến cho bạn bởi MIO-KITCHEN-TEAM
```
#### ColdWindScholar (3590361911@qq.com) Bảo lưu mọi quyền.  ####
