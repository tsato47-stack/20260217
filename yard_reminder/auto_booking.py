import os
from datetime import datetime

try:
    from plyer import notification as plyer_notification
    _PLYER = True
except ImportError:
    _PLYER = False

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
LOGIN_URL = "https://yard.hacomono.jp/login"
INSTRUCTOR = "NAO"
MAX_RETRIES = 3

# Playwrightが使うChromiumの実行パス候補（環境によって異なる）
_CHROMIUM_CANDIDATES = [
    # Linux (Claude Code / CI 環境)
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    # playwright install chromium で標準インストールされる場所
    os.path.expanduser("~/.cache/ms-playwright/chromium-1194/chrome-linux/chrome"),
    os.path.expanduser("~/.cache/ms-playwright/chromium-1223/chrome-linux/chrome"),
    # Windows (Playwright デフォルト) — Noneにして自動検出させる
]


def _find_chromium() -> str | None:
    for path in _CHROMIUM_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None  # Playwright のデフォルト検索に任せる


def _notify(title: str, message: str) -> None:
    if _PLYER:
        try:
            plyer_notification.notify(
                title=title,
                message=message,
                app_name="YARD ヨガ予約リマインダー",
                timeout=10,
            )
        except Exception:
            pass
    print(f"[通知] {title}: {message}")


class AutoBooker:
    def __init__(self, email: str, password: str):
        self._email = email
        self._password = password
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    def book(self, entry: dict) -> bool:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._attempt_book(entry)
            except Exception as exc:
                print(f"[自動予約] 試行 {attempt}/{MAX_RETRIES} 失敗: {exc}")
                if attempt == MAX_RETRIES:
                    _notify(
                        f"【予約エラー】{entry['class_name']}",
                        f"{MAX_RETRIES}回試行しましたが予約できませんでした: {exc}",
                    )
                    self._save_error_log(entry, str(exc))
                    return False
        return False

    def _attempt_book(self, entry: dict) -> bool:
        from playwright.sync_api import sync_playwright

        url = entry.get("url", "")
        class_name = entry.get("class_name", "")

        with sync_playwright() as p:
            launch_kwargs = {"headless": False}
            chrome_path = _find_chromium()
            if chrome_path:
                launch_kwargs["executable_path"] = chrome_path
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                # 1. ログインページを開く
                page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)

                # 2. メールアドレス・パスワード入力
                page.fill(
                    'input[type="email"], input[name="email"], input[id*="email"], input[placeholder*="メール"]',
                    self._email,
                )
                page.fill(
                    'input[type="password"], input[name="password"], input[id*="password"]',
                    self._password,
                )

                # 3. ログインボタンクリック
                page.click(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("ログイン"), button:has-text("サインイン")'
                )
                page.wait_for_load_state("networkidle", timeout=15000)

                # ログイン失敗チェック
                if "login" in page.url.lower():
                    path = self._save_screenshot(page, "login_error")
                    _notify(
                        f"【ログイン失敗】{class_name}",
                        "メールアドレスまたはパスワードが正しくありません。",
                    )
                    return False

                # 4. 予約ページへ遷移
                page.goto(url, wait_until="networkidle", timeout=30000)

                # 5. NAOインストラクターのクラスを探して予約
                booked = self._find_and_book(page, class_name)
                if not booked:
                    self._save_screenshot(page, "no_class_found")
                    _notify(
                        f"【予約失敗】{class_name}",
                        f"インストラクター「{INSTRUCTOR}」のクラスが見つからないか満席です。",
                    )
                    return False

                # 予約確認ダイアログ処理
                self._handle_confirm(page)

                # 6. 完了スクリーンショット保存
                path = self._save_screenshot(page, "completion")

                # 7. 完了通知
                _notify(
                    f"【予約完了】{class_name}",
                    f"予約が完了しました！ スクリーンショット: {os.path.basename(path)}",
                )
                return True

            finally:
                context.close()
                browser.close()

    def _find_and_book(self, page, class_name: str) -> bool:
        # NAO を含む要素の近くにある予約ボタンを探す
        nao_blocks = page.locator(f"text={INSTRUCTOR}").all()
        for locator in nao_blocks:
            try:
                # 親要素をたどって予約ボタンを探す
                for _ in range(6):
                    parent = locator.locator("xpath=..")
                    btn = parent.locator(
                        'button:has-text("予約"), a:has-text("予約"), '
                        'button[class*="reserve"], button[class*="book"]'
                    ).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        return True
                    locator = parent
            except Exception:
                continue
        return False

    def _handle_confirm(self, page) -> None:
        try:
            confirm = page.locator(
                'button:has-text("確認"), button:has-text("はい"), button:has-text("予約する")'
            ).first
            if confirm.count() > 0 and confirm.is_visible():
                confirm.click()
                page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

    def _save_screenshot(self, page, prefix: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"{prefix}_{ts}.png")
        try:
            page.screenshot(path=path, full_page=True)
        except Exception as e:
            print(f"[スクリーンショット] 保存失敗: {e}")
        return path

    def _save_error_log(self, entry: dict, reason: str) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"error_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"クラス: {entry.get('class_name', '')}\n")
            f.write(f"スタジオ: {entry.get('studio', '')}\n")
            f.write(f"受付開始: {entry.get('start_datetime', '')}\n")
            f.write(f"エラー: {reason}\n")
            f.write(f"記録時刻: {ts}\n")
