@echo off
cd /d "%~dp0"
echo Generating a simulated English network + 4 LLM provider dashboard...
python provider_monitor.py --all-tests --llm-all-providers --demo --output demo_report.html
if errorlevel 1 (echo Demo failed. Check that Python 3.9+ is installed. & pause & exit /b 1)
echo Demo complete: demo_report.html
start "" "%~dp0demo_report.html"
pause
