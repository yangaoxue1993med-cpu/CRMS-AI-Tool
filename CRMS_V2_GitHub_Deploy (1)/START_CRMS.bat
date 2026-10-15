@echo off
setlocal
cd /d "%~dp0"
py -3.12 -c "import sys; print(sys.executable)" >nul 2>nul
if errorlevel 1 (
    echo Python 3.12 and the Windows py launcher are required.
    echo Install Python 3.12, or follow the manual commands in README.md.
    pause
    exit /b 1
)
echo Installing CRMS dependencies for Python 3.12...
py -3.12 -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo Dependency installation failed. Review the message above.
    pause
    exit /b 1
)
echo Starting CRMS 2.4.1...
py -3.12 -m streamlit run "%~dp0CRMS_AI_Tool.py"
pause
