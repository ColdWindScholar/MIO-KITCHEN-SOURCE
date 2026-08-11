## Todo List
### Formats
##### 

|   Format    | Unpack                                          | Repack                                                                                                     | Tool                                                                                                                        |
|:-----------:|-------------------------------------------------|------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
|   AllWin    | imgRePacker "file.img"                          | imgRePacker "allwinner.img.dump"                                                                           | [imgRePacker.exe](https://xdaforums.com/t/tool-imgrepacker-livesuits-phoenixsuits-firmware-images-unpacker-packer.1753473/) |
|   Amlogic   | amlogic.exe -d "amlogic.img" "Projects\AMLogic" | "amlogic.exe" -r "Projects\AMLogic\image.cfg" "Projects\Project_nam1e\Build\AMLogic" ".\aml_new_build.img" | amlogic.exe                                                                                                                 |
|     lz4     |                                                 | "lz4.exe" -B6 --content-size "image.img" "image.img.lz4"                                                   | lz4.exe                                                                                                                     |
| boot_editor | boot_editor\gradlew.bat unpack                  | boot_editor\gradlew.bat pack                                                                               |                                                                                                                             |

### Features
#### 
* Patch Boot
``` bash

```


* Debloater
