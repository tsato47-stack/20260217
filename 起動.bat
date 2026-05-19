@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ================================
echo  YARD ヨガ予約リマインダー
echo ================================
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo [エラー] Pythonがインストールされていません。
    echo https://www.python.org/downloads/ からインストールしてください。
    pause
    exit /b 1
)

echo [1/3] 必要なパッケージをインストール中...
pip install -r yard_reminder/requirements.txt -q
if errorlevel 1 (
    echo [エラー] パッケージのインストールに失敗しました。
    pause
    exit /b 1
)

echo [2/3] Chromiumをインストール中（初回のみ時間がかかります）...
playwright install chromium
if errorlevel 1 (
    echo [警告] Chromiumのインストールに失敗しましたが続行します。
)

echo [3/3] アプリを起動します...
echo.
python yard_reminder/main.py

if errorlevel 1 (
    echo.
    echo [エラー] アプリの起動に失敗しました。
    echo 上のエラーメッセージをコピーして開発者に送ってください。
    pause
)
