from __future__ import annotations

import os
import random
import re
import shutil
import string
import sys
import time
import tempfile
import subprocess
import webbrowser
from dataclasses import dataclass
from typing import Callable, Optional

from DrissionPage import ChromiumPage, ChromiumOptions
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, pyqtProperty,
    QPropertyAnimation, QEasingCurve, QRectF, QPointF, QPoint, QSize, QTimer,
)
from PyQt5.QtGui import QPainterPath
from PyQt5 import sip
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen, QIcon, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QGraphicsOpacityEffect, QMessageBox, QLabel,
)

HEADLESS_MODE = True

VALORANT_SIGNUP_URL = (
    "https://xsso.playvalorant.com/login"
    "?uri=https://playvalorant.com/en-us/platform-selection/"
    "&prompt=signup&show_region=true&locale=en_US"
)
SMAIL_URL = "https://smailpro.com/temporary-email"
ACCOUNTS_FILE = os.path.join(os.path.expanduser("~"), "accounts.txt")

USERNAME_LEN = 16
PASSWORD_LEN = 16
TYPING_MIN_DELAY = 0.05
TYPING_MAX_DELAY = 0.15
TWOFA_TIMEOUT = 30

ProgressCallback = Callable[[int, str], None]

DISCORD_SVG = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="white" d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>"""
GITHUB_SVG = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="white" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>"""

class TwoFATimeoutError(RuntimeError):
    pass

def _log_default(pct: int, msg: str) -> None:
    print(f"[{pct:>3}%] {msg}")

def random_string(length: int = 16) -> str:
    pool = string.ascii_letters + string.digits
    must = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
    ]
    rest = [random.choice(pool) for _ in range(length - len(must))]
    out = must + rest
    random.shuffle(out)
    return "".join(out)

@dataclass
class Account:
    username: str
    password: str

    def as_line(self) -> str:
        return f"{self.username}:{self.password}"

class AccountGenerator:
    def __init__(
        self,
        progress: Optional[ProgressCallback] = None,
        notify: Optional[Callable[[str, str], None]] = None,
        headless: bool = False,
    ) -> None:
        self.progress = progress or _log_default
        self._notify = notify or (lambda t, y: None)
        self.headless = headless
        self.page: Optional[ChromiumPage] = None
        self._valorant_tab = None
        self._smail_tab = None
        self._profile_dir: Optional[str] = None

    def _say(self, pct: int, msg: str) -> None:
        try:
            self.progress(pct, msg)
        except Exception:
            pass

    def _start_browser(self) -> None:
        self._say(5, "Launching Chrome with a fresh profile…")
        import glob
        temp_base = tempfile.gettempdir()
        for old_dir in glob.glob(os.path.join(temp_base, "chromium_fresh_*")):
            try:
                if os.path.isdir(old_dir):
                    shutil.rmtree(old_dir, ignore_errors=True)
            except Exception:
                pass
        self._profile_dir = tempfile.mkdtemp(prefix="chromium_fresh_")
        co = ChromiumOptions()
        if self.headless:
            co.set_argument("--window-position=-32000,-32000")
            co.set_argument("--window-size=1920,1080")
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--start-maximized")
        co.set_user_data_path(self._profile_dir)
        co.set_argument("--incognito")
        co.set_argument("--no-first-run")
        co.set_argument("--no-default-browser-check")
        co.set_argument("--disable-extensions")
        co.set_argument("--disable-sync")
        co.set_argument("--disable-default-apps")
        co.set_argument("--disable-features=TranslateUI")
        co.set_argument("--disable-popup-blocking")
        co.set_argument("--metrics-recording-only")
        co.set_argument("--no-pings")
        co.set_argument("--disable-disk-cache")
        co.set_argument("--disable-media-cache")
        co.set_argument("--disable-offline-load-stale-cache")
        co.set_argument("--disk-cache-size=0")
        co.set_argument("--media-cache-size=0")
        co.set_argument("--disable-local-storage")
        co.set_argument("--disable-session-storage")
        co.set_argument("--disable-shared-workers")
        co.set_argument("--disable-service-workers")
        co.set_argument("--disable-background-networking")
        co.set_argument("--disable-background-timer-throttling")
        co.set_argument("--disable-backgrounding-occluded-windows")
        co.set_argument("--disable-renderer-backgrounding")
        co.set_argument("--disable-component-extensions-with-background-pages")
        self.page = ChromiumPage(co)

    def _quit_browser(self) -> None:
        if self.page is not None:
            try:
                self.page.quit()
            except Exception:
                pass
            self.page = None
        if self._profile_dir and os.path.isdir(self._profile_dir):
            shutil.rmtree(self._profile_dir, ignore_errors=True)
        self._profile_dir = None

    def _new_tab(self, url: str):
        self._say(0, f"Creating new tab for {url}…")
        try:
            tab = self.page.new_tab(url)
            if not tab:
                raise RuntimeError("Failed to create new tab")
            return tab
        except Exception as e:
            self._say(0, f"Error creating tab: {e}, trying alternative method")
            self.page.get(url)
            self.page.wait.doc_loaded(timeout=30)
            return self.page

    def _switch(self, tab) -> None:
        if not tab:
            raise RuntimeError("Cannot switch to None tab")
        try:
            self.page.activate_tab(tab)
        except Exception:
            self._say(0, "Tab switch failed")
        time.sleep(1.5)

    def _type_text(self, text: str, min_delay: float = None, max_delay: float = None) -> None:
        if min_delay is None:
            min_delay = TYPING_MIN_DELAY
        if max_delay is None:
            max_delay = TYPING_MAX_DELAY
        for char in text:
            self._valorant_tab.actions.key_down(char).key_up(char)
            time.sleep(random.uniform(min_delay, max_delay))

    def _press_enter(self) -> None:
        self._valorant_tab.actions.key_down('ENTER').key_up('ENTER')
        time.sleep(0.5)

    def _press_tab(self) -> None:
        self._valorant_tab.actions.key_down('\t').key_up('\t')
        time.sleep(0.5)

    def _focus_first_input(self) -> None:
        self._valorant_tab.run_js("""
            const inputs = document.querySelectorAll('input:not([type="hidden"])');
            if (inputs.length > 0) {
                inputs[0].focus();
                inputs[0].click();
            }
        """)
        time.sleep(0.5)

    def _smail_get_email(self) -> str:
        self._say(15, "Waiting for smailpro to assign a Gmail address…")
        deadline = time.time() + 60
        while time.time() < deadline:
            html = self._smail_tab.html
            matches = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', html)
            valid = [m for m in matches if not m.startswith('random') and not m.startswith('example')]
            if valid:
                email = valid[0]
                self._say(20, f"Found temporary email: {email}")
                return email
            time.sleep(0.5)
        raise RuntimeError("Timed out waiting for smailpro to display a Gmail address.")

    def _smail_wait_for_login_code(self, timeout: int = TWOFA_TIMEOUT) -> str:
        self._say(55, f"Waiting for Riot verification email (timeout: {timeout}s)...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._switch(self._smail_tab)
            html = self._smail_tab.html
            matches = re.findall(r'Login\s*Code:\s*(\d{6})', html, re.IGNORECASE)
            if matches:
                code = matches[0]
                self._say(60, f"Found login code: {code}")
                return code
            matches = re.findall(r'(?:code|verification|verif)[^\d]{0,20}(\d{6})', html, re.IGNORECASE)
            if matches:
                code = matches[0]
                self._say(60, f"Found verification code (fallback): {code}")
                return code
            try:
                refresh_btn = self._smail_tab.ele("#refresh", timeout=0.5)
                if refresh_btn:
                    refresh_btn.click()
                    time.sleep(0.5)
            except Exception:
                pass
            time.sleep(0.5)
        raise TwoFATimeoutError(f"Timed out ({timeout}s) waiting for 2FA email. Exiting...")

    def _valorant_enter_email(self, email: str) -> None:
        self._say(30, "Entering email on Valorant signup page…")
        time.sleep(0.5)
        self._say(32, "Focusing email input...")
        self._focus_first_input()
        self._say(35, f"Typing email: {email}")
        self._type_text(email)
        self._say(37, "Pressing Enter to submit email...")
        self._press_enter()
        time.sleep(0.5)

    def _valorant_enter_2fa(self, code: str) -> None:
        self._say(65, f"Entering 2FA code: {code}")
        time.sleep(0.5)
        self._focus_first_input()
        self._type_text(code, min_delay=0.01, max_delay=0.02)
        self._say(68, "Pressing Enter to submit 2FA code...")
        self._press_enter()
        time.sleep(0.5)

    def _birthday(self) -> None:
        self._say(70, "Entering birthday...")
        self._focus_first_input()
        self._type_text("01/01/2001", min_delay=0.01, max_delay=0.05)
        self._say(72, "Pressing Enter to submit birthday...")
        self._press_enter()
        time.sleep(0.5)

    def _valorant_enter_credentials(self, username: str, password: str) -> None:
        self._say(75, "Entering credentials...")
        time.sleep(0.5)
        self._focus_first_input()
        self._say(77, f"Typing username: {username}")
        self._type_text(username)
        self._say(79, "Pressing Enter after username...")
        self._press_enter()
        time.sleep(0.5)
        self._focus_first_input()
        password_with_prefix = "@" + password
        self._say(82, "Typing password...")
        self._type_text(password_with_prefix)
        self._say(84, "Pressing Enter after password...")
        self._press_enter()
        time.sleep(0.5)
        self._say(86, "Focusing password confirmation field...")
        self._valorant_tab.run_js("""
            const inputs = document.querySelectorAll('input:not([type="hidden"])');
            for (let i = inputs.length - 1; i >= 0; i--) {
                if (inputs[i].type === 'password' || inputs[i].type === 'text') {
                    inputs[i].focus();
                    inputs[i].click();
                    break;
                }
            }
        """)
        time.sleep(0.5)
        self._say(88, "Typing password confirmation...")
        self._type_text(password_with_prefix)
        self._say(90, "Pressing Enter after password confirmation...")
        self._press_enter()
        time.sleep(0.5)

    def _valorant_accept_tos(self) -> None:
        self._say(92, "Accepting Terms of Service...")
        time.sleep(0.5)
        self._say(93, "Scrolling Terms of Service to bottom...")
        try:
            scrollable_div = self._valorant_tab.ele("#tos-scrollable-area", timeout=3)
            if scrollable_div:
                self._valorant_tab.run_js("""
                    const tosDiv = document.getElementById('tos-scrollable-area');
                    if (tosDiv) { tosDiv.scrollTop = tosDiv.scrollHeight; }
                """)
                time.sleep(0.5)
            else:
                scrollable_div = self._valorant_tab.ele(".sc-eIrltS", timeout=2)
                if scrollable_div:
                    self._valorant_tab.run_js("""
                        const divs = document.querySelectorAll('div');
                        for (let div of divs) {
                            if (div.classList.contains('sc-eIrltS') || div.classList.contains('irqGIN')) {
                                div.scrollTop = div.scrollHeight;
                                break;
                            }
                        }
                    """)
                    time.sleep(0.5)
                else:
                    for _ in range(20):
                        self._valorant_tab.scroll.down(500)
                        time.sleep(0.5)
        except Exception as e:
            self._say(0, f"Error scrolling TOS: {e}, using fallback...")
            for _ in range(20):
                try:
                    self._valorant_tab.scroll.down(500)
                    time.sleep(0.5)
                except Exception:
                    break

        self._say(94, "Finding and clicking the first checkbox...")
        time.sleep(0.5)
        try:
            checkbox = self._valorant_tab.ele("tag:input@type=checkbox", timeout=3)
            if checkbox:
                if not checkbox.states.is_checked:
                    checkbox.click()
            else:
                checkbox = self._valorant_tab.ele("[type='checkbox']", timeout=2)
                if checkbox:
                    checkbox.click()
        except Exception as e:
            self._say(0, f"Checkbox handling failed: {e}")
        time.sleep(0.05)

        self._say(96, "Finding and clicking the Accept button...")
        try:
            accept_button = self._valorant_tab.ele("@data-testid=btn-accept-tos", timeout=5)
            if accept_button:
                accept_button.click()
            else:
                accept_button = self._valorant_tab.ele(".fNkmiR", timeout=3)
                if accept_button:
                    accept_button.click()
                else:
                    self._valorant_tab.run_js("""
                        const buttons = document.querySelectorAll('button');
                        for (let button of buttons) {
                            const label = button.querySelector('.label');
                            if (label && label.textContent.trim() === 'Accept') {
                                button.click();
                                break;
                            }
                        }
                    """)
        except Exception as e:
            self._say(0, f"Button click failed: {e}")
            try:
                self._valorant_tab.run_js("""
                    const button = document.querySelector('[data-testid="btn-accept-tos"]');
                    if (button) { button.click(); }
                """)
            except Exception:
                self._say(0, "All button click methods failed")
        self._say(98, "Terms of Service acceptance completed!")
        time.sleep(0.5)

    def _save_account(self, account: Account) -> None:
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as fh:
            fh.write(account.as_line() + "\n")
        self._say(99, f"Saved account to {ACCOUNTS_FILE}")

    def run(self) -> Account:
        try:
            self._start_browser()

            self._say(10, "Opening smailpro temporary email…")
            self._smail_tab = self._new_tab(SMAIL_URL)
            self._switch(self._smail_tab)
            time.sleep(0.05)
            
            invalid_email_count = 0
            while True:
                email = self._smail_get_email()
                if email.lower() == "william@gmail.com":
                    invalid_email_count += 1
                    if invalid_email_count >= 3:
                        raise RuntimeError("Reopen Generator")
                    self._notify("Invalid Email, Refreshing", "error")
                    time.sleep(5)
                    self._smail_tab.get(SMAIL_URL)
                    time.sleep(2)
                    continue
                self._say(20, f"Using email: {email}")
                break

            self._say(25, "Opening Valorant signup page…")
            self._valorant_tab = self._new_tab(VALORANT_SIGNUP_URL)
            self._switch(self._valorant_tab)
            time.sleep(0.05)
            self._valorant_enter_email(email)

            self._say(50, "Switching to smailpro to wait for 2FA code...")
            code = self._smail_wait_for_login_code()
            self._say(60, f"Got 2FA code: {code}")

            self._say(62, "Switching back to Valorant...")
            self._switch(self._valorant_tab)
            self._valorant_enter_2fa(code)
            self._birthday()

            username = random_string(USERNAME_LEN)
            password = random_string(PASSWORD_LEN)
            self._say(75, f"Generated username: {username}")
            self._say(75, f"Generated password: @{password}")
            self._valorant_enter_credentials(username, password)

            self._valorant_accept_tos()
            time.sleep(3)
            account = Account(username=username, password="@" + password)
            self._save_account(account)
            self._say(100, "Done!")
            return account
        finally:
            self._quit_browser()

class GeneratorWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)
    notify = pyqtSignal(str, str)

    def __init__(self, headless: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.headless = headless

    def run(self) -> None:
        def cb(pct: int, msg: str) -> None:
            self.progress.emit(pct, msg)
        def notify_cb(text: str, ntype: str) -> None:
            self.notify.emit(text, ntype)
        try:
            gen = AccountGenerator(progress=cb, notify=notify_cb, headless=self.headless)
            account = gen.run()
            self.finished_ok.emit(account.as_line())
        except TwoFATimeoutError:
            self.failed.emit("2FA_TIMEOUT")
        except Exception as exc:
            self.failed.emit(str(exc))

class SegmentedProgressBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fade = 0.0
        self._progress = 0.0
        self._completion_fade = 0.0
        self.setMinimumHeight(34)

    def getFade(self) -> float:
        return self._fade

    def setFade(self, v: float) -> None:
        self._fade = max(0.0, min(1.0, float(v)))
        self.update()

    fade = pyqtProperty(float, getFade, setFade)

    def getProgress(self) -> float:
        return self._progress

    def setProgress(self, v: float) -> None:
        self._progress = max(0.0, min(1.0, float(v)))
        self.update()

    progress = pyqtProperty(float, getProgress, setProgress)

    def getCompletionFade(self) -> float:
        return self._completion_fade

    def setCompletionFade(self, v: float) -> None:
        self._completion_fade = max(0.0, min(1.0, float(v)))
        self.update()

    completion_fade = pyqtProperty(float, getCompletionFade, setCompletionFade)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        bg_col = QColor("#2A2A35")
        bg_col.setAlphaF(self._fade * 0.6)
        p.setBrush(QBrush(bg_col))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 8, 8)

        fill_w = (w - 4) * self._progress
        fill_col = QColor("#6A6A75")
        fill_col.setAlphaF(self._fade)
        p.setBrush(QBrush(fill_col))
        p.setPen(Qt.NoPen)
        if fill_w > 0:
            p.drawRoundedRect(QRectF(2, 2, fill_w, h - 4), 8, 8)

        if self._completion_fade > 0:
            green_col = QColor("#4CAF50")
            green_col.setAlphaF(self._completion_fade)
            p.setBrush(QBrush(green_col))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 8, 8)

            text_col = QColor("#FFFFFF")
            text_col.setAlphaF(self._completion_fade)
            p.setPen(text_col)
            p.setFont(QFont("Segoe UI", 11, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, "Completed")

def make_history_icon(size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#9A9AA6"), 1.4)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(size/2, size/2), size*0.35, size*0.35)
    p.drawLine(QPointF(size/2, size/2), QPointF(size/2, size*0.3))
    p.drawLine(QPointF(size/2, size/2), QPointF(size*0.65, size/2))
    path = QPainterPath()
    path.moveTo(size*0.15, size*0.3)
    path.lineTo(size*0.3, size*0.15)
    path.lineTo(size*0.35, size*0.35)
    p.setBrush(QBrush(QColor("#9A9AA6")))
    p.drawPath(path)
    p.end()
    return pm

def make_user_icon(size: int = 16) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#9A9AA6"), 1.2)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    center_x = size * 0.5
    head_y = size * 0.35
    head_radius = size * 0.22
    painter.drawEllipse(QPointF(center_x, head_y), head_radius, head_radius)
    path = QPainterPath()
    path.moveTo(size * 0.22, size * 0.82)
    path.quadTo(
        QPointF(center_x, size * 0.55),
        QPointF(size * 0.78, size * 0.82),
    )
    painter.drawPath(path)
    painter.end()
    return pixmap

def make_lock_icon(size: int = 16) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#9A9AA6"), 1.2)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(size*0.2, size*0.5, size*0.6, size*0.35), 3, 3)
    p.drawArc(QRectF(size*0.3, size*0.15, size*0.4, size*0.5), 0, 180*16)
    p.end()
    return pm

def make_close_icon(size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#9A9AA6"), 1.4))
    m = 5
    p.drawLine(QPointF(m, m), QPointF(size - m, size - m))
    p.drawLine(QPointF(size - m, m), QPointF(m, size - m))
    p.end()
    return pm

def make_info_icon(size: int = 14) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    center = size / 2
    radius = size / 2 - 1
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#6A6A75")))
    p.drawEllipse(QPointF(center, center), radius, radius)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", int(size * 0.6), QFont.Bold)
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignCenter, "i")
    p.end()
    return pm

def make_svg_icon(svg_str: str, size: int = 18) -> QPixmap:
    renderer = QSvgRenderer(bytes(svg_str, 'utf-8'))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap

class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(320, 160)
        self._drag_pos: Optional[QPointF] = None
        self.worker: Optional[GeneratorWorker] = None
        self._progress_anim: Optional[QPropertyAnimation] = None
        self._first_time = True
        self._failed = False
        self._restart_needed = False
        self._current_username = ""
        self._current_password = ""
        self._build_ui()

    def getTargetHeight(self) -> int:
        return self.height()

    def setTargetHeight(self, h: int) -> None:
        self.resize(self.width(), int(h))

    targetHeight = pyqtProperty(int, getTargetHeight, setTargetHeight)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(4)

        self.btn_notepad = QPushButton()
        self.btn_notepad.setObjectName("iconbtn")
        self.btn_notepad.setIcon(QIcon(make_history_icon(18)))
        self.btn_notepad.setIconSize(QSize(18, 18))
        self.btn_notepad.setFixedSize(26, 26)
        self.btn_notepad.setCursor(Qt.PointingHandCursor)
        self.btn_notepad.setToolTip("Accounts History")
        self.btn_notepad.clicked.connect(self.on_open_accounts)
        top.addWidget(self.btn_notepad)

        top.addStretch()

        text_container = QHBoxLayout()
        text_container.setSpacing(0)

        branding = QLabel("Accounts")
        branding.setFont(QFont("Segoe UI", 13, QFont.Bold))
        branding.setAlignment(Qt.AlignLeft)
        branding.setStyleSheet("color: #6A6A75;")
        text_container.addWidget(branding)

        self.btn_info = QPushButton()
        self.btn_info.setObjectName("iconbtn")
        self.btn_info.setIcon(QIcon(make_info_icon(12)))
        self.btn_info.setIconSize(QSize(12, 12))
        self.btn_info.setFixedSize(16, 16)
        self.btn_info.setCursor(Qt.PointingHandCursor)
        self.btn_info.setToolTip(
            "Valorant Fresh (Brand New), Saved to accounts.txt"
        )
        text_container.addWidget(self.btn_info)

        top.addLayout(text_container)

        top.addStretch()

        self.btn_close = QPushButton()
        self.btn_close.setObjectName("iconbtn")
        self.btn_close.setIcon(QIcon(make_close_icon(18)))
        self.btn_close.setIconSize(QSize(18, 18))
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Close (Esc)")
        self.btn_close.clicked.connect(self.close)
        top.addWidget(self.btn_close)

        layout.addLayout(top)
        
        layout.addStretch(1)

        self.account_container = QWidget()
        account_layout = QVBoxLayout(self.account_container)
        account_layout.setContentsMargins(0, 0, 0, 0)
        account_layout.setSpacing(8)
        
        self.uname_btn = QPushButton(" Username")
        self.uname_btn.setObjectName("accountfield")
        self.uname_btn.setFixedHeight(36)
        self.uname_btn.setCursor(Qt.PointingHandCursor)
        self.uname_btn.setIcon(QIcon(make_user_icon(16)))
        self.uname_btn.setIconSize(QSize(16, 16))
        self.uname_btn.clicked.connect(lambda: self.copy_to_clipboard(self.uname_btn.text().strip()))
        account_layout.addWidget(self.uname_btn)
        
        self.pwd_btn = QPushButton(" Password")
        self.pwd_btn.setObjectName("accountfield")
        self.pwd_btn.setFixedHeight(36)
        self.pwd_btn.setCursor(Qt.PointingHandCursor)
        self.pwd_btn.setIcon(QIcon(make_lock_icon(16)))
        self.pwd_btn.setIconSize(QSize(16, 16))
        self.pwd_btn.clicked.connect(lambda: self.copy_to_clipboard(self.pwd_btn.text().strip()))
        account_layout.addWidget(self.pwd_btn)
        
        self.account_container.hide()
        layout.addWidget(self.account_container)

        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setObjectName("generate")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_opacity = QGraphicsOpacityEffect(self.btn_generate)
        self.btn_opacity.setOpacity(1.0)
        self.btn_generate.setGraphicsEffect(self.btn_opacity)
        self.btn_generate.clicked.connect(self.on_start)
        layout.addWidget(self.btn_generate)

        self.progress_bar = SegmentedProgressBar()
        self.progress_bar.setFixedHeight(40)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        social_layout = QHBoxLayout()
        social_layout.setSpacing(8)
        
        self.btn_discord = QPushButton(" Discord")
        self.btn_discord.setObjectName("discord")
        self.btn_discord.setFixedHeight(36)
        self.btn_discord.setCursor(Qt.PointingHandCursor)
        self.btn_discord.setIcon(QIcon(make_svg_icon(DISCORD_SVG, 18)))
        self.btn_discord.setIconSize(QSize(18, 18))
        self.btn_discord.clicked.connect(lambda: self.open_url("https://discord.com/users/1368264423806074910"))
        social_layout.addWidget(self.btn_discord)
        
        self.btn_github = QPushButton(" Github")
        self.btn_github.setObjectName("github")
        self.btn_github.setFixedHeight(36)
        self.btn_github.setCursor(Qt.PointingHandCursor)
        self.btn_github.setIcon(QIcon(make_svg_icon(GITHUB_SVG, 18)))
        self.btn_github.setIconSize(QSize(18, 18))
        self.btn_github.clicked.connect(lambda: self.open_url("https://github.com/fiukdsbfksdfd/"))
        social_layout.addWidget(self.btn_github)
        
        layout.addLayout(social_layout)
        
        self.notif_pill = QLabel(self)
        self.notif_pill.setAlignment(Qt.AlignCenter)
        self.notif_pill.hide()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor("#1A1A22")))
        p.setPen(QPen(QColor("#2A2A35"), 1))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e) -> None:
        if self._drag_pos is not None and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e) -> None:
        self._drag_pos = None

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            self.close()

    def _anim(self, target, prop, start, end, ms, on_finished=None) -> QPropertyAnimation:
        a = QPropertyAnimation(target, prop, self)
        a.setDuration(ms)
        a.setStartValue(start)
        a.setEndValue(end)
        a.setEasingCurve(QEasingCurve.InOutCubic)
        a.finished.connect(a.deleteLater)
        if on_finished:
            a.finished.connect(on_finished)
        a.start(QPropertyAnimation.DeleteWhenStopped)
        return a

    def show_notification(self, text: str, ntype: str = "info") -> None:
        colors = {
            "info": "#5865F2",
            "success": "#4CAF50",
            "error": "#F44336",
            "copy": "#3A3A45"
        }
        self.notif_pill.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: {colors.get(ntype, '#2A2A35')};
                padding: 4px 12px;
                border-radius: 10px;
                font-family: 'Segoe UI';
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        self.notif_pill.setText(text)
        self.notif_pill.adjustSize()
        x = (self.width() - self.notif_pill.width()) // 2
        y_target = self.height() - self.notif_pill.height() - 10
        y_start = self.height() + 10
        self.notif_pill.move(x, y_start)
        self.notif_pill.show()
        self.notif_pill.raise_()
        
        anim = QPropertyAnimation(self.notif_pill, b"pos", self)
        anim.setDuration(300)
        anim.setStartValue(QPoint(x, y_start))
        anim.setEndValue(QPoint(x, y_target))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        
        QTimer.singleShot(2500, lambda: self.hide_notification(x, y_target, y_start))

    def hide_notification(self, x: int, y_target: int, y_start: int) -> None:
        anim = QPropertyAnimation(self.notif_pill, b"pos", self)
        anim.setDuration(300)
        anim.setStartValue(QPoint(x, y_target))
        anim.setEndValue(QPoint(x, y_start))
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self.notif_pill.hide)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def copy_to_clipboard(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.show_notification("Copied to clipboard!", "copy")

    def open_url(self, url: str) -> None:
        webbrowser.open(url)

    def on_start(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self._failed = False
        self.btn_generate.setEnabled(False)
        self._anim(self.btn_opacity, b'opacity', 1.0, 0.0, 250, self._show_bar)

    def _show_bar(self) -> None:
        self.btn_generate.hide()
        self.progress_bar.setFade(0.0)
        self.progress_bar.setProgress(0.0)
        self.progress_bar.show()
        self._anim(self.progress_bar, b'fade', 0.0, 1.0, 250)
        self.worker = GeneratorWorker(headless=HEADLESS_MODE, parent=self)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.notify.connect(self.show_notification)
        self.worker.finished.connect(self._on_thread_finished)
        self.worker.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        print(f"[{pct:>3}%] {msg}")
        if self._progress_anim is not None:
            try:
                if sip.isdeleted(self._progress_anim):
                    self._progress_anim = None
                else:
                    self._progress_anim.stop()
            except (RuntimeError, ReferenceError):
                self._progress_anim = None
        cur = self.progress_bar.getProgress()
        target = max(cur, pct / 100.0)
        self._progress_anim = self._anim(
            self.progress_bar, b'progress', cur, target, 300
        )

    def _on_done(self, account_line: str) -> None:
        print(f"[done] {account_line}")
        parts = account_line.split(":")
        if len(parts) == 2:
            self._current_username = parts[0]
            self._current_password = parts[1]
        self.show_notification("Account generated!", "success")

    def _on_failed(self, err: str) -> None:
        print(f"[failed] {err}")
        self._failed = True
        if err == "2FA_TIMEOUT":
            self._restart_needed = True
            self.show_notification("2FA timeout, restarting...", "error")
        elif err == "Reopen Generator":
            self.show_notification("Reopen Generator", "error")
        else:
            self.show_notification(f"Error: {err}", "error")

    def _on_thread_finished(self) -> None:
        if self.worker:
            self.worker = None
        if self._failed:
            self._failed = False
            self.progress_bar.hide()
            self.btn_generate.show()
            self.btn_opacity.setOpacity(1.0)
            self.btn_generate.setEnabled(True)
            if self._restart_needed:
                self._restart_needed = False
                QTimer.singleShot(1000, self.on_start)
            return
        self._anim(
            self.progress_bar, b'completion_fade',
            0.0, 1.0, 300, self._wait_then_hide_completion
        )

    def _wait_then_hide_completion(self) -> None:
        QTimer.singleShot(2000, lambda: self._anim(
            self.progress_bar, b'completion_fade',
            1.0, 0.0, 300, self._show_button
        ))

    def _show_button(self) -> None:
        self.progress_bar.hide()
        self.btn_generate.show()
        self.btn_opacity.setOpacity(0.0)
        self._anim(self.btn_opacity, b'opacity', 0.0, 1.0, 250)
        self.btn_generate.setEnabled(True)
        
        if self._current_username:
            if self._first_time:
                self._first_time = False
                start_h = self.height()
                end_h = start_h + 90
                self._anim(self, b'targetHeight', start_h, end_h, 1500, self._fade_in_account)
            else:
                self._fade_in_account()

    def _fade_in_account(self) -> None:
        self.uname_btn.setText(" " + self._current_username)
        self.pwd_btn.setText(" " + self._current_password)
        self.account_container.show()
        self.account_opacity = QGraphicsOpacityEffect(self.account_container)
        self.account_container.setGraphicsEffect(self.account_opacity)
        self.account_opacity.setOpacity(0.0)
        self._anim(self.account_opacity, b'opacity', 0.0, 1.0, 500)

    def on_open_accounts(self) -> None:
        if not os.path.exists(ACCOUNTS_FILE):
            QMessageBox.information(self, "accounts.txt", "accounts.txt does not exist yet.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(ACCOUNTS_FILE)
            elif sys.platform == "darwin":
                subprocess.run(["open", ACCOUNTS_FILE], check=False)
            else:
                subprocess.run(["xdg-open", ACCOUNTS_FILE], check=False)
        except Exception as exc:
            QMessageBox.warning(self, "Open failed", str(exc))

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(2000)
        event.accept()

STYLESHEET = """
QWidget { color: #E8E8EE; }
QPushButton#generate {
    background-color: #6A6A75;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    font-family: "Segoe UI", "SF Pro Display", sans-serif;
}
QPushButton#generate:hover { background-color: #7A7A85; }
QPushButton#generate:disabled { background-color: #3A3A45; color: #A0A0A8; }
QPushButton#iconbtn {
    background: transparent;
    border: none;
    border-radius: 6px;
}
QPushButton#iconbtn:hover { background-color: #2A2A35; }
QPushButton#discord {
    background-color: #5865F2;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    padding-left: 10px;
    font-family: "Segoe UI", "SF Pro Display", sans-serif;
}
QPushButton#discord:hover { background-color: #4752C4; }
QPushButton#github {
    background-color: #0D1117;
    color: #FFFFFF;
    border: 1px solid #2A2A35;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    padding-left: 10px;
    font-family: "Segoe UI", "SF Pro Display", sans-serif;
}
QPushButton#github:hover { background-color: #1F242B; }
QPushButton#accountfield {
    background-color: #2A2A35;
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    padding-left: 12px;
    color: #E8E8EE;
    font-family: "Segoe UI", "SF Pro Display", sans-serif;
}
QPushButton#accountfield:hover { background-color: #34343F; }
"""

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Valorant Account Generator")
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())