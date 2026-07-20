#!/usr/bin/env python3
import os
import random
import string
import time
import re
import glob
import tempfile
import shutil
import subprocess
import requests
import paramiko
from dataclasses import dataclass

ACCOUNTS_FILE = "accounts.txt"
SSH_KEY_PATH = "ssh.key"
REMOTE_USER = ""
REMOTE_HOST = ""
REMOTE_ACCOUNTS_FILE = "/home/ubuntu/accounts.txt"
USERNAME_LEN = 16
PASSWORD_LEN = 16
TWOFA_TIMEOUT = 60
EMAIL_PROVIDER = "smail"
SMAIL_URL = "https://smailpro.com/temporary-email"
CUSTOM_EMAIL_DOMAINS = [
    "akshjfdbshkfbskdf.xubi.org",
    "hffgdhfghdfgh.flashhub.net",
    "fdsghgfhdfghfghg.theworkpc.com",
    "sdgfdsgdfg.casacam.net",
]

VALORANT_SIGNUP_URL = (
    "https://xsso.playvalorant.com/login"
    "?uri=https://playvalorant.com/en-us/platform-selection/"
    "&prompt=signup&show_region=true&locale=en_US"
)


class TwoFATimeoutError(RuntimeError):
    pass


class CredentialError(RuntimeError):
    pass


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


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def human_sleep(min_sec: float = 0.4, max_sec: float = 1.2) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


@dataclass
class Account:
    username: str
    password: str

    def as_line(self) -> str:
        return f"{self.username}:{self.password}"


class AccountGenerator:
    def __init__(self) -> None:
        self.page = None
        self._tab = None
        self._smail_tab = None
        self._profile_dir = None
        self._catchmail_address = None
        self._current_domain = random.choice(CUSTOM_EMAIL_DOMAINS)

    # ---------- Infrastructure ----------

    def _send_notification(self, title: str, message: str) -> None:
        try:
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n = New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon = [System.Drawing.SystemIcons]::Information;"
                "$n.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info;"
                f"$n.BalloonTipTitle = '{title}';"
                f"$n.BalloonTipText = '{message}';"
                "$n.Visible = $true; $n.ShowBalloonTip(5000);"
                "Start-Sleep -Seconds 5; $n.Dispose()"
            )
            subprocess.run(["powershell", "-Command", ps],
                           capture_output=True, timeout=10)
        except Exception as e:
            log(f"Notification failed: {e}")

    def _transfer_account_via_ssh(self, account_line: str) -> bool:
        try:
            log(f"Sending Account To {REMOTE_USER}@{REMOTE_HOST}...")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
            ssh.connect(REMOTE_HOST, username=REMOTE_USER, pkey=key)
            sftp = ssh.open_sftp()
            try:
                with sftp.file(REMOTE_ACCOUNTS_FILE, 'r') as f:
                    existing = f.read().decode('utf-8')
            except IOError:
                existing = ""
            with sftp.file(REMOTE_ACCOUNTS_FILE, 'w') as f:
                f.write(existing + account_line + "\n")
            sftp.close()
            ssh.close()
            log("Transfer Done +1 Account")
            return True
        except Exception as e:
            log(f"SSH transfer failed: {e}")
            return False

    def _start_browser(self) -> None:
        log("Chrome")
        from DrissionPage import ChromiumPage, ChromiumOptions

        # Fresh profile every run: clean leftovers, make a new dir.
        temp_base = tempfile.gettempdir()
        for old in glob.glob(os.path.join(temp_base, "chromium_fresh_*")):
            shutil.rmtree(old, ignore_errors=True)
        self._profile_dir = tempfile.mkdtemp(prefix="chromium_fresh_")

        co = ChromiumOptions()
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
        self._catchmail_address = None
        self._smail_tab = None

    # ---------- Tab / interaction helpers ----------

    def _new_tab(self, url: str):
        try:
            tab = self.page.new_tab(url)
            if not tab:
                raise RuntimeError("new_tab returned None")
        except Exception as e:
            log(f"new_tab failed ({e}); falling back to get()")
            self.page.get(url)
            tab = self.page
        human_sleep(1.2, 2.2)
        return tab

    def _switch(self, tab) -> None:
        if not tab:
            raise RuntimeError("Cannot switch to None tab")
        try:
            self.page.activate_tab(tab)
        except Exception:
            log("Tab switch failed")
        time.sleep(1.5)

    def _type_text(self, text: str, min_delay: float = 0.05, max_delay: float = 0.15) -> None:
        # Type 3 random characters first
        for _ in range(3):
            random_char = random.choice(string.ascii_letters + string.digits)
            self._tab.actions.key_down(random_char).key_up(random_char)
            time.sleep(random.uniform(min_delay, max_delay))
        
        # Backspace the 3 random characters
        for _ in range(3):
            self._tab.actions.key_down('BACKSPACE').key_up('BACKSPACE')
            time.sleep(random.uniform(min_delay, max_delay))
        
        # Type the actual text
        for char in text:
            self._tab.actions.key_down(char).key_up(char)
            time.sleep(random.uniform(min_delay, max_delay))

    def _press_enter(self) -> None:
        self._tab.actions.key_down('ENTER').key_up('ENTER')
        time.sleep(0.5)

    def _focus_first_input(self) -> None:
        self._tab.run_js("""
            const inputs = document.querySelectorAll("input");
            for (let i = 0; i < inputs.length; i++) {
                if (inputs[i].type !== "hidden") {
                    inputs[i].focus();
                    inputs[i].click();
                    break;
                }
            }
        """)
        time.sleep(0.5)

    def _smooth_scroll(self) -> None:
        try:
            for _ in range(random.randint(4, 7)):
                step = random.randint(700, 1400)
                self._tab.run_js(f"window.scrollBy(0, {step});")
                time.sleep(random.uniform(0.01, 0.03))
            self._tab.run_js("""
                const divs = document.querySelectorAll('div');
                for (let d of divs) {
                    if (d.scrollHeight > d.clientHeight && d.clientHeight > 100) {
                        let current = 0;
                        const target = d.scrollHeight;
                        const interval = setInterval(() => {
                            current += 140;
                            d.scrollTop = current;
                            if (current >= target) clearInterval(interval);
                        }, 5);
                    }
                }
            """)
            time.sleep(0.1)
        except Exception as e:
            log(f"Scroll error: {e}")

    def _get_email(self) -> str:
        if EMAIL_PROVIDER == "smail":
            return self._smail_get_email()
        return self._catchmail_get_email()

    def _catchmail_get_email(self) -> str:
        local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        addr = f"{local}@{self._current_domain}"
        self._catchmail_address = addr
        log(f"Catchmail email: {addr} (domain: {self._current_domain})")
        return addr

    def _smail_get_email(self) -> str:
        log("Page, SmailPro")
        self._smail_tab = self._new_tab(SMAIL_URL)
        self._switch(self._smail_tab)
        human_sleep(1.0, 2.0)
        
        deadline = time.time() + 60
        invalid_count = 0
        while time.time() < deadline:
            html = self._smail_tab.html
            matches = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', html)
            valid = [m for m in matches if not m.startswith('random') and not m.startswith('example')]
            if valid:
                email = valid[0]
                if email.lower() == "william@gmail.com":
                    invalid_count += 1
                    if invalid_count >= 3:
                        raise RuntimeError("Smailpro antibot detected")
                    log("Gay Captcha")
                    self._smail_tab.get(SMAIL_URL)
                    human_sleep(2.0, 3.0)
                    continue
                log(f"Email: {email}")
                return email
            time.sleep(0.5)
        raise TwoFATimeoutError("Timed out waiting for smailpro email")

    def _wait_for_code(self) -> str:
        if EMAIL_PROVIDER == "smail":
            return self._smail_wait_for_code()
        return self._catchmail_wait_for_code()

    def _catchmail_wait_for_code(self) -> str:
        log(f"Waiting catchmail.io code (timeout {TWOFA_TIMEOUT}s)...")
        deadline = time.time() + TWOFA_TIMEOUT
        while time.time() < deadline:
            try:
                r = requests.get("https://api.catchmail.io/api/v1/mailbox",
                                 params={"address": self._catchmail_address},
                                 timeout=10)
                if r.status_code == 200:
                    for msg in r.json().get("messages", []):
                        code = self._extract_code(msg.get("subject", ""))
                        if code:
                            log(f"Code found: {code}")
                            try:
                                mid = msg.get("id")
                                if mid:
                                    requests.delete(
                                        f"https://api.catchmail.io/api/v1/message/{mid}",
                                        params={"mailbox": self._catchmail_address},
                                        timeout=10)
                            except Exception:
                                pass
                            return code
            except Exception as e:
                log(f"Catchmail check error: {e}")
            time.sleep(2)
        raise TwoFATimeoutError(f"No code after {TWOFA_TIMEOUT}s")

    def _smail_wait_for_code(self) -> str:
        log(f"Waiting 2fa Code (timeout {TWOFA_TIMEOUT}s)...")
        deadline = time.time() + TWOFA_TIMEOUT
        while time.time() < deadline:
            self._switch(self._smail_tab)
            html = self._smail_tab.html
            matches = re.findall(r'Login\s*Code:\s*(\d{6})', html, re.IGNORECASE)
            if matches:
                code = matches[0]
                log(f"Code found: {code}")
                return code
            matches = re.findall(r'(?:code|verification|verif)[^\d]{0,20}(\d{6})', html, re.IGNORECASE)
            if matches:
                code = matches[0]
                log(f"Code found (fallback): {code}")
                return code
            try:
                refresh_btn = self._smail_tab.ele("#refresh", timeout=0.5)
                if refresh_btn:
                    refresh_btn.click()
                    human_sleep(0.3, 0.6)
            except Exception:
                pass
            human_sleep(0.5, 1.0)
        raise TwoFATimeoutError(f"No code after {TWOFA_TIMEOUT}s")

    @staticmethod
    def _extract_code(text: str):
        for pattern in (
            r'Login\s*Code:\s*(\d{6})',
            r'code\s*is\s*(\d{6})',
            r'verification\s*code[:\s]*(\d{6})',
            r'\b(\d{6})\b',
        ):
            m = re.findall(pattern, text, re.IGNORECASE)
            if m:
                return m[0]
        return None

    # ---------- Valorant flow ----------

    def _enter_email(self, email: str) -> None:
        log("Entering email...")
        time.sleep(0.5)
        self._focus_first_input()
        self._type_text(email)
        self._press_enter()
        time.sleep(0.5)

    def _enter_2fa(self, code: str) -> None:
        log(f"Entering 2FA: {code}")
        time.sleep(0.5)
        self._focus_first_input()
        self._type_text(code, min_delay=0.01, max_delay=0.02)
        self._press_enter()
        time.sleep(0.5)

    def _enter_birthday(self) -> None:
        self._focus_first_input()
        self._type_text("01/01/2001", min_delay=0.01, max_delay=0.05)
        self._press_enter()
        time.sleep(0.5)

    def _enter_credentials(self, username: str, password: str) -> None:
        log("Entering credentials...")
        time.sleep(0.5)
        self._focus_first_input()
        self._type_text(username)
        self._press_enter()
        time.sleep(0.5)
        self._focus_first_input()
        password_with_prefix = "@" + password
        self._type_text(password_with_prefix)
        self._press_enter()
        time.sleep(0.5)
        self._tab.run_js("""
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
        self._type_text(password_with_prefix)
        self._press_enter()
        time.sleep(0.5)
        time.sleep(0.5)
        self._type_text(password_with_prefix)
        self._press_enter()
        time.sleep(0.5)
    def _accept_tos(self) -> None:
        log("Accepting TOS...")
        time.sleep(0.5)
        try:
            self._smooth_scroll()
            time.sleep(0.5)

            # Handle Checkbox
            checkbox = self._tab.ele("tag:input@type=checkbox", timeout=3)
            if checkbox:
                if not checkbox.states.is_checked:
                    checkbox.click()
            else:
                checkbox = self._tab.ele("[type='checkbox']", timeout=2)
                if checkbox:
                    checkbox.click()
            time.sleep(0.05)

            # Handle Accept Button
            accept_button = self._tab.ele("@data-testid=btn-accept-tos", timeout=5)
            if accept_button:
                accept_button.click()
            else:
                accept_button = self._tab.ele(".fNkmiR", timeout=3)
                if accept_button:
                    accept_button.click()
                else:
                    self._tab.run_js("""
                        const buttons = document.querySelectorAll('button');
                        for (let button of buttons) {
                            const label = button.querySelector('.label');
                            if (label && label.textContent.trim() === 'Accept') {
                                button.click();
                                break;
                            }
                        }
                    """)
            time.sleep(0.5)

            if self._tab.ele('text:Your username or password may be incorrect',
                             timeout=2):
                log("ACCOUNT GENERATION FAILED")
                time.sleep(129)
                raise CredentialError("Incorrect username/password error shown.")
            log("TOS accepted; no error detected.")
        except CredentialError:
            raise
        except Exception as e:
            log(f"TOS error: {e}")
    # ---------- Persistence ----------

    def _save_account(self, account: Account) -> None:
        line = account.as_line()
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        log(f"Saved locally to {ACCOUNTS_FILE}")
        self._transfer_account_via_ssh(line)
        self._send_notification("Account Generated", f"Username: {account.username}")
        time.sleep(240)

    # ---------- Main flow ----------

    def run(self) -> Account:
        try:
            self._start_browser()

            email = self._get_email()
            self._tab = self._new_tab(VALORANT_SIGNUP_URL)
            self._switch(self._tab)

            self._enter_email(email)
            code = self._wait_for_code()
            self._switch(self._tab)
            self._enter_2fa(code)
            self._enter_birthday()

            username = random_string(USERNAME_LEN)
            password = random_string(PASSWORD_LEN)
            log(f"username={username} password=@{password}")

            self._enter_credentials(username, password)
            self._accept_tos()

            account = Account(username=username, password="@" + password)
            self._save_account(account)
            log("Generation Done.")
            return account
        except Exception:
            log("Generation failed")
            raise
        finally:
            time.sleep(5)
            self._quit_browser()


def generate_account():
    try:
        return AccountGenerator().run().as_line()
    except TwoFATimeoutError:
        log("2FA timeout; will retry.")
    except CredentialError as e:
        log(f"Credential error: {e}")
    except Exception as e:
        log(f"Error: {e}")
    return None


def main():
    if not os.path.exists(SSH_KEY_PATH):
        print(f"ERROR: SSH key not found at {SSH_KEY_PATH}")
        return
    if not os.path.exists(ACCOUNTS_FILE):
        open(ACCOUNTS_FILE, "w", encoding="utf-8").close()

    while True:
        try:
            generate_account()
            time.sleep(15)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()