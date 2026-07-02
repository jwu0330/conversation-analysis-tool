@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   對話紀錄統計分析系統 - 一鍵啟動
echo ============================================

REM --- 找 Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 找不到 Python。請先安裝 Python 3.10 以上：https://www.python.org/downloads/
    echo        安裝時記得勾選 "Add Python to PATH"。
    pause
    exit /b 1
)

REM --- 沒有虛擬環境就自動建立並安裝套件 ---
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 第一次啟動，建立虛擬環境...
    python -m venv .venv
    if errorlevel 1 ( echo [錯誤] 建立虛擬環境失敗 & pause & exit /b 1 )
    echo [2/3] 安裝套件（第一次會比較久，請稍候）...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 ( echo [錯誤] 安裝套件失敗，請截圖上面訊息 & pause & exit /b 1 )
) else (
    echo [略過] 已有虛擬環境。
)

echo [3/3] 啟動網頁... 稍後瀏覽器會自動打開 http://localhost:8501
echo        要關閉請直接關掉這個黑色視窗。
echo.
".venv\Scripts\python.exe" -m streamlit run app.py

pause
