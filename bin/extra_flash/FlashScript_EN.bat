@ECHO OFF
setlocal enabledelayedexpansion
set fastboot=%cd%\bin\fastboot
set e=%cd%\bin\cho
set zstd=%cd%\bin\zstd
set sg=1^>nul 2^>nul
if exist bin\right_device (
	set /p right_device=<bin\right_device
)
:HOME
cls
%e%   {F9}MIO{F0}KITCHEN{#}{#}{\n}
%e% {02}[1].{01}Keep all data and flash it in{#}{#}{\n}
%e% {02}[2].{01}Format user data.{#}{#}{\n}
if not "!right_device!"=="" %e% {0C}Attention: This ROM is specifically made for [!right_device!], and cannot be flashed on other models.£¡£¡£¡{#}{\n}
%e% {08}Driver program [836898509] download.{#}{\n}
set /p zyxz=Please select the item you wish to operate on£º
if "!zyxz!" == "1" set xz=1&goto FLASH
if "!zyxz!" == "2" set xz=2&goto FLASH
goto HOME&pause
:FLASH
cls
%e% {0D}Your phone must be in Bootloader mode, waiting for the device.{#}{\n}
for /f "tokens=2" %%a in ('!fastboot! getvar product 2^>^&1^|find "product"') do set DeviceCode=%%a
for /f "tokens=2" %%a in ('!fastboot! getvar slot-count 2^>^&1^|find "slot-count" ') do set fqlx=%%a
if "!fqlx!" == "2" (set fqlx=AB)  else (set fqlx=A)
ECHO.Device detected.:[!DeviceCode!]
if not "!DeviceCode!"=="!right_device!" (
		color 4f
		%e% {0C}"This ROM is made for !right_device!, but your device is !DeviceCode!"{#}{\n}
		PAUSE
		GOTO :EOF
)
if "!fqlx!"=="A" (
for /f "delims=" %%b in ( 'dir /b images ^| findstr /v /i "super.img" ^| findstr /v /i "preloader_raw.img" ^| findstr /v /i "cust.img"' ) do (
%e% {09}Flashing %%~nb partition files£¡{#}{\n}
!fastboot! flash %%~nb images\%%~nxb %sg%
if "!errorlevel!"=="0" (echo Flashing %%~nb completed) else (echo An error occurred while flashing %%~nb - Error code!errorlevel!)
)
) else (
for /f "delims=" %%b in ( 'dir /b images ^| findstr /v /i "super.img" ^| findstr /v /i "preloader_raw.img" ^| findstr /v /i "cust.img"' ) do (
%e% {09}Flashing %%~nb partition files£¡{#}{\n}
!fastboot! flash %%~nb_a images\%%~nxb %sg%
!fastboot! flash %%~nb_b images\%%~nxb %sg%
if "!errorlevel!"=="0" (echo Flashing %%~nb completed) else (
	!fastboot! flash %%~nb images\%%~nxb %sg%
	if not "!errorlevel!"=="0" (
	%e% {0C}An error occurred while flashing %%~nb - Error code!errorlevel!{#}{\n})
)
))
if exist images\cust.img !fastboot! flash cust images\cust.img
if exist images\preloader_raw.img (
!fastboot! flash preloader_a images\preloader_raw.img !sg!
!fastboot! flash preloader_b images\preloader_raw.img !sg!
!fastboot! flash preloader1 images\preloader_raw.img !sg!
!fastboot! flash preloader2 images\preloader_raw.img !sg!
)
for /f "delims=" %%a in ('dir /b "images\*.zst"')do (
echo.Converting %%~na
!zstd! --rm -d images/%%~nxa -o images/%%~na
echo Starting to flash %%~na
set name=%%~na
!fastboot! flash !name:~0,-4! images\%%~na
)
if "!xz!" == "1" %e% {0A}All data has been preserved, preparing to restart!{#}{\n}
if "!xz!" == "2" (echo Formatting DATA
!fastboot! erase userdata
!fastboot! erase metadata)
if "!fqlx!"=="AB" (!fastboot! set_active a %sg%)
!fastboot! reboot
%e% {0A}Flashing completed.{#}{\n}
pause
exit