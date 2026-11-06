@echo off
cd /d "%~dp0"
if not exist "api_keys.env" (
  echo No api_keys.env found. Copy api_keys.env.example to api_keys.env and fill in your own keys.
  pause
  exit /b 1
)
echo Running real internet, AWS, Azure and four authenticated LLM model-list checks...
python provider_monitor.py --all-tests --llm-all-providers --llm-mode models --env-file "api_keys.env" --minutes 10 --interval 60 --timeout 4 --llm-timeout 15 --output provider_report.html
if errorlevel 1 (echo Test failed. Check error messages above. & pause & exit /b 1)
echo Report: provider_report.html
start "" "%~dp0provider_report.html"
pause
