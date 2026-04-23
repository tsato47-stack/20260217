import os
import asyncio
from datetime import datetime

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


def _ensure_screenshots_dir():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


async def _run_booking(email: str, password: str, url: str, class_name: str):
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    _ensure_screenshots_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        async def save_error_shot(label: str):
            path = os.path.join(SCREENSHOTS_DIR, f"error_{label}_{ts}.png")
            await page.screenshot(path=path)
            return path

        try:
            # ログイン
            await page.goto("https://yard.hacomono.jp", timeout=30000)
            await page.wait_for_load_state("networkidle")

            # ログインフォームを探す（hacomono の典型的なセレクター）
            try:
                await page.fill("input[type='email'], input[name='email'], input[id*='email']", email, timeout=10000)
                await page.fill("input[type='password']", password, timeout=5000)
                await page.click("button[type='submit'], input[type='submit']", timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                shot = await save_error_shot("login_form")
                return False, f"ログインフォームが見つかりません。スクリーンショット: {shot}"

            # ログイン失敗検出
            if any(kw in await page.content() for kw in ["ログインに失敗", "パスワードが違", "Invalid"]):
                shot = await save_error_shot("login_failed")
                return False, f"ログインに失敗しました。スクリーンショット: {shot}"

            # 予約ページに遷移
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # NAOインストラクターのクラスを探す
            page_html = await page.content()
            if "NAO" not in page_html:
                shot = await save_error_shot("nao_not_found")
                return False, f"NAOインストラクターのクラスが見つかりません。スクリーンショット: {shot}"

            # NAOクラスの予約ボタンをクリック（hacomono の構造に合わせてセレクターを調整）
            nao_section = page.locator("text=NAO").first
            await nao_section.scroll_into_view_if_needed(timeout=5000)

            # NAO行の近くにある予約ボタンを探す
            reserve_btn = None
            # パターン1: NAOテキストを含む行内のボタン
            try:
                reserve_btn = page.locator(
                    "//tr[contains(., 'NAO')]//button[contains(., '予約') or contains(., '申込')]"
                    " | //div[contains(., 'NAO')]//button[contains(., '予約') or contains(., '申込')]"
                ).first
                await reserve_btn.wait_for(state="visible", timeout=5000)
            except PWTimeout:
                reserve_btn = None

            # パターン2: NAOの近くにある最初の予約ボタン
            if reserve_btn is None:
                try:
                    reserve_btn = page.locator("button:has-text('予約'), button:has-text('申込')").first
                    await reserve_btn.wait_for(state="visible", timeout=5000)
                except PWTimeout:
                    shot = await save_error_shot("reserve_btn_not_found")
                    return False, f"予約ボタンが見つかりません。スクリーンショット: {shot}"

            await reserve_btn.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 確認ボタンがあれば押す
            try:
                confirm_btn = page.locator("button:has-text('確認'), button:has-text('決定'), button:has-text('OK')").first
                await confirm_btn.wait_for(state="visible", timeout=5000)
                await confirm_btn.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass  # 確認ステップなし

            # 満席チェック
            content = await page.content()
            if any(kw in content for kw in ["満席", "キャンセル待ち", "予約できません"]):
                shot = await save_error_shot("full")
                return False, f"満席または予約不可です。スクリーンショット: {shot}"

            # 完了スクリーンショット
            shot_path = os.path.join(SCREENSHOTS_DIR, f"completion_{ts}.png")
            await page.screenshot(path=shot_path)
            return True, shot_path

        except Exception as e:
            try:
                shot = await save_error_shot("exception")
            except Exception:
                shot = "取得失敗"
            return False, f"エラー: {e}  スクリーンショット: {shot}"
        finally:
            await browser.close()


def run_booking(email: str, password: str, url: str, class_name: str,
                on_success=None, on_failure=None):
    """スレッドから呼び出せる同期ラッパー（最大3リトライ）。"""
    import threading

    def _task():
        for attempt in range(1, 4):
            try:
                ok, msg = asyncio.run(_run_booking(email, password, url, class_name))
                if ok:
                    if on_success:
                        on_success(msg)
                    return
                else:
                    if attempt == 3:
                        if on_failure:
                            on_failure(msg)
                    else:
                        import time
                        time.sleep(5 * attempt)
            except Exception as e:
                if attempt == 3:
                    if on_failure:
                        on_failure(str(e))

    threading.Thread(target=_task, daemon=True).start()
