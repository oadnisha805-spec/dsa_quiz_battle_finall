@echo off
REM Makes DSAQuizBattle.exe (run this on a Windows computer that has Python installed).
REM The finished file appears in the "dist" folder. Give that one .exe to anyone: no Python needed.
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name DSAQuizBattle main.py
echo.
echo Done! Your game is: dist\DSAQuizBattle.exe
pause
