@echo off
echo Building Video Clipper EXE...
python -m pyinstaller --onefile --noconsole --name "VideoClipGenerator" --clean app.py
echo Build complete! check the 'dist' folder.
pause
