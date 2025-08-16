@echo off
py -m nuitka tekdt_bmc.py --standalone --onefile --windows-icon-from-ico=logo.ico --enable-plugin=pyqt6 --output-dir=build --windows-console-mode=disable --remove-output
pause