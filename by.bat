@echo off
pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk
::if not exist dist\bin\ md dist\bin\
::copy bin\* dist\bin\
pause