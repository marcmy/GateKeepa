from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import keyring
import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import messagebox, ttk

from spapi import Config, SpApiClient


APP_NAME = "Gate Keepa"
APP_VERSION = "0.2.3"
SERVICE_NAME = "SourcingCockpit"
NATIVE_HOST_NAME = "com.marcmy.gatekeepa"
AMAZON_SETUP_DOCS = "https://developer-docs.amazon.com/sp-api/docs/self-authorization"
UPDATE_API = "https://api.github.com/repos/marcmy/GateKeepa/releases?per_page=50"
UPDATE_TAG_PREFIX = "gate-keepa-v"
MUTEX_NAME = "Local\\SourcingCockpitHelper"
SHOW_EVENT_NAME = "Local\\SourcingCockpitShowSettings"


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    path = root / "SourcingCockpit"
    path.mkdir(parents=True, exist_ok=True)
    return path


APP_DIR = app_data_dir()
SETTINGS_PATH = APP_DIR / "settings.json"
LOG_PATH = APP_DIR / "helper.log"
NATIVE_LOG_PATH = APP_DIR / "native-host.log"


def configure_logging() -> None:
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    if sys.stdout is None:
        sys.stdout = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout


def _kernel32() -> Any:
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.OpenEventW.restype = ctypes.c_void_p
    return kernel32


def acquire_single_instance() -> Any:
    if os.name != "nt":
        return object()
    kernel32 = _kernel32()
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return None
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return None
    return handle


def signal_existing_instance() -> bool:
    if os.name != "nt":
        return False
    event_modify_state = 0x0002
    kernel32 = _kernel32()
    for _ in range(15):
        handle = kernel32.OpenEventW(event_modify_state, False, SHOW_EVENT_NAME)
        if handle:
            try:
                return bool(kernel32.SetEvent(handle))
            finally:
                kernel32.CloseHandle(handle)
        time.sleep(0.1)
    return False


def load_settings() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "client_id": "",
        "seller_id": "",
        "marketplace_id": "ATVPDKIKX0DER",
        "region": "NA",
        "lwa_rotation_saved_at": "",
    }
    if not SETTINGS_PATH.exists():
        return defaults
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            defaults.update(payload)
            legacy_rotation_key = "".join(("client_", "sec", "ret_saved_at"))
            if not str(defaults.get("lwa_rotation_saved_at", "")).strip():
                defaults["lwa_rotation_saved_at"] = str(payload.get(legacy_rotation_key, "")).strip()
            defaults.pop(legacy_rotation_key, None)
    except Exception:
        logging.exception("Could not read settings")
    return defaults


def save_settings(settings: dict[str, Any]) -> None:
    public = {
        "client_id": str(settings.get("client_id", "")).strip(),
        "seller_id": str(settings.get("seller_id", "")).strip(),
        "marketplace_id": str(settings.get("marketplace_id", "ATVPDKIKX0DER")).strip(),
        "region": str(settings.get("region", "NA")).strip().upper(),
        "lwa_rotation_saved_at": str(settings.get("lwa_rotation_saved_at", "")).strip(),
    }
    temp = SETTINGS_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(public, indent=2), encoding="utf-8")
    temp.replace(SETTINGS_PATH)


def get_secret(name: str) -> str:
    return keyring.get_password(SERVICE_NAME, name) or ""


def set_secret(name: str, value: str) -> None:
    value = value.strip()
    if value:
        keyring.set_password(SERVICE_NAME, name, value)
    else:
        try:
            keyring.delete_password(SERVICE_NAME, name)
        except keyring.errors.PasswordDeleteError:
            pass


def remove_legacy_bridge_secret() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, "bridge_token")
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception:
        logging.exception("Could not remove legacy localhost bridge token")


def configured(settings: dict[str, Any] | None = None) -> bool:
    settings = settings or load_settings()
    return all([
        str(settings.get("client_id", "")).strip(),
        str(settings.get("seller_id", "")).strip(),
        str(settings.get("marketplace_id", "")).strip(),
        get_secret("client_secret"),
        get_secret("refresh_token"),
    ])


def make_spapi_config(settings: dict[str, Any] | None = None) -> Config:
    settings = settings or load_settings()
    client_secret = get_secret("client_secret")
    refresh_token = get_secret("refresh_token")
    missing = []
    for key, value in [
        ("client_id", settings.get("client_id")),
        ("client_secret", client_secret),
        ("refresh_token", refresh_token),
        ("seller_id", settings.get("seller_id")),
        ("marketplace_id", settings.get("marketplace_id")),
    ]:
        if not str(value or "").strip():
            missing.append(key)
    if missing:
        raise ValueError("Missing Amazon setup values: " + ", ".join(missing))
    return Config(
        client_id=str(settings["client_id"]).strip(),
        client_secret=client_secret,
        refresh_token=refresh_token,
        seller_id=str(settings["seller_id"]).strip(),
        marketplace_id=str(settings["marketplace_id"]).strip(),
        region=str(settings.get("region", "NA")).strip().upper() or "NA",
        user_agent=f"GateKeepa/{APP_VERSION} (Language=Python/3.12; Platform=Windows)",
    )


def marketplace_name(marketplace_id: str) -> str:
    return {
        "ATVPDKIKX0DER": "United States",
        "A2EUQ1WTGCTBG2": "Canada",
        "A1F83G8C2ARO7P": "United Kingdom",
    }.get(marketplace_id, marketplace_id or "Unknown")


def mask_value(value: str, head: int = 3, tail: int = 3) -> str:
    value = str(value or "")
    if not value:
        return "Not configured"
    if len(value) <= head + tail + 1:
        return "•" * len(value)
    return f"{value[:head]}…{value[-tail:]}"


def version_tuple(version: str) -> tuple[int, int, int]:
    parts = version.strip().lstrip("v").split(".")
    values: list[int] = []
    for part in parts[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        values.append(int(digits or 0))
    while len(values) < 3:
        values.append(0)
    return values[0], values[1], values[2]


def native_host_registered() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        key_path = rf"Software\Mozilla\NativeMessagingHosts\{NATIVE_HOST_NAME}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            manifest_path, _ = winreg.QueryValueEx(key, None)
        manifest = Path(str(manifest_path))
        if not manifest.is_file():
            return False
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        return payload.get("name") == NATIVE_HOST_NAME
    except (OSError, ImportError, AttributeError, ValueError, json.JSONDecodeError):
        return False


def lwa_rotation_status(settings: dict[str, Any] | None = None) -> tuple[str, int | None]:
    settings = settings or load_settings()
    raw = str(settings.get("lwa_rotation_saved_at", "")).strip()
    if not raw:
        return "Rotation date unknown", None
    try:
        saved = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if saved.tzinfo is None:
            saved = saved.replace(tzinfo=timezone.utc)
        age_days = max(0, (datetime.now(timezone.utc) - saved.astimezone(timezone.utc)).days)
    except ValueError:
        return "Rotation date unknown", None
    remaining = 180 - age_days
    if remaining <= 0:
        return f"Rotation overdue by {-remaining} days", remaining
    if remaining <= 30:
        return f"Rotate within {remaining} days", remaining
    return f"{remaining} days remaining", remaining


def find_firefox_executable() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe"
        access_modes = [winreg.KEY_READ]
        for flag_name in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
            flag = getattr(winreg, flag_name, 0)
            if flag:
                access_modes.append(winreg.KEY_READ | flag)
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for access in access_modes:
                try:
                    with winreg.OpenKey(root, key_path, 0, access) as key:
                        value, _ = winreg.QueryValueEx(key, None)
                    candidate = Path(str(value).strip().strip(chr(34)))
                    if candidate.is_file():
                        return candidate
                except OSError:
                    pass
    except (ImportError, AttributeError):
        pass

    candidates: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(env_name)
        if root:
            candidates.append(Path(root) / "Mozilla Firefox" / "firefox.exe")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.extend([
            Path(local) / "Mozilla Firefox" / "firefox.exe",
            Path(local) / "Programs" / "Mozilla Firefox" / "firefox.exe",
        ])
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def open_firefox_target(target: str) -> bool:
    firefox = find_firefox_executable()
    if firefox is None:
        return False
    try:
        subprocess.Popen([str(firefox), target], close_fds=True)
        return True
    except OSError:
        logging.exception("Could not launch Firefox")
        return False


def make_tray_image() -> Image.Image:
    image = Image.new("RGBA", (64, 64), (25, 29, 36, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=12, fill=(41, 122, 91, 255))
    draw.text((15, 20), "GK", fill=(255, 255, 255, 255))
    return image


class HelperApp:
    def __init__(self, show_configure: bool = False):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.settings_window: tk.Toplevel | None = None
        self.status_window: tk.Toplevel | None = None
        self.status_label: ttk.Label | None = None
        self.status_vars: dict[str, tk.StringVar] = {}
        self.status = "Ready · native messaging" if configured() else "Not configured"
        self.update_status = "Not checked"
        self._quitting = False
        self.activation_event: Any = None
        self._start_activation_listener()

        self.tray = pystray.Icon(
            "GateKeepa",
            make_tray_image(),
            APP_NAME,
            menu=pystray.Menu(
                pystray.MenuItem("Status…", self._tray_status, default=True),
                pystray.MenuItem("Settings…", self._tray_settings),
                pystray.MenuItem("Test Amazon connection", self._tray_test),
                pystray.MenuItem("Install Firefox extension…", self._tray_firefox, visible=self._xpi_available),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Create diagnostics bundle…", self._tray_diagnostics),
                pystray.MenuItem("Check for updates", self._tray_update),
                pystray.MenuItem("Open log", self._tray_log),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._tray_quit),
            ),
        )
        self.tray.run_detached()
        if configured():
            self.root.after(1200, self._maybe_warn_lwa_rotation)
        if show_configure or not configured():
            self.root.after(150, self.show_settings)

    def _start_activation_listener(self) -> None:
        if os.name != "nt":
            return
        kernel32 = _kernel32()
        self.activation_event = kernel32.CreateEventW(None, True, False, SHOW_EVENT_NAME)
        if not self.activation_event:
            logging.warning("Could not create activation event")
            return

        def wait_for_activation() -> None:
            while not self._quitting and self.activation_event:
                if kernel32.WaitForSingleObject(self.activation_event, 1000) == 0:
                    kernel32.ResetEvent(self.activation_event)
                    self.root.after(0, self.show_settings)

        threading.Thread(target=wait_for_activation, name="activation-listener", daemon=True).start()

    def _xpi_path(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().with_name("GateKeepa.xpi")
        return Path(__file__).resolve().parent / "build" / "firefox" / "GateKeepa.xpi"

    def _xpi_available(self, _item: pystray.MenuItem) -> bool:
        return self._xpi_path().exists()

    def _tray_status(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.show_status)

    def _tray_settings(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.show_settings)

    def _tray_test(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.test_amazon_async)

    def _tray_firefox(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.install_firefox_extension)

    def _tray_diagnostics(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.create_diagnostics_bundle)

    def _tray_update(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, lambda: self.check_updates_async(show_no_update=True))

    def _tray_log(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.open_log)

    def _tray_quit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.root.after(0, self.quit)

    def notify(self, message: str) -> None:
        try:
            self.tray.notify(message, APP_NAME)
        except Exception:
            logging.info("Tray notification: %s", message)

    def set_status(self, status: str) -> None:
        self.status = status
        self.tray.title = f"{APP_NAME} — {status}"
        try:
            self.tray.update_menu()
        except Exception:
            pass
        if self.status_label is not None and self.status_label.winfo_exists():
            self.status_label.configure(text=status)
        self.refresh_status_window()

    def _maybe_warn_lwa_rotation(self) -> None:
        text, remaining = lwa_rotation_status()
        if remaining is not None and remaining <= 30:
            self.notify(f"Amazon LWA client secret: {text}. Rotate it in Seller Central and save the new secret in Gate Keepa.")

    def show_status(self) -> None:
        if self.status_window and self.status_window.winfo_exists():
            self.status_window.deiconify()
            self.status_window.lift()
            self.status_window.focus_force()
            self.refresh_status_window()
            return
        window = tk.Toplevel(self.root, name="statusWindow")
        self.status_window = window
        window.title(f"{APP_NAME} Status")
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        outer = ttk.Frame(window, padding=18)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(1, weight=1)
        ttk.Label(outer, text="Gate Keepa status", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        fields = [
            ("Version", "version"), ("Helper", "helper"), ("Amazon", "amazon"),
            ("Transport", "transport"), ("Marketplace", "marketplace"), ("Seller", "seller"),
            ("LWA secret", "lwa_rotation"), ("Updates", "updates"),
        ]
        self.status_vars = {key: tk.StringVar(value="…") for _, key in fields}
        for row, (label, key) in enumerate(fields, start=1):
            ttk.Label(outer, text=label).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=4)
            ttk.Label(outer, textvariable=self.status_vars[key]).grid(row=row, column=1, sticky="w", pady=4)
        buttons = ttk.Frame(outer)
        buttons.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(buttons, text="Refresh", command=self.refresh_status_window).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Test Amazon", command=self.test_amazon_async).pack(side="left", padx=6)
        ttk.Button(buttons, text="Diagnostics", command=self.create_diagnostics_bundle).pack(side="left", padx=6)
        ttk.Button(buttons, text="Check updates", command=lambda: self.check_updates_async(True)).pack(side="left", padx=6)
        self.refresh_status_window()
        window.update_idletasks()
        width = window.winfo_reqwidth()
        height = window.winfo_reqheight()
        x = max(0, (window.winfo_screenwidth() - width) // 2)
        y = max(0, (window.winfo_screenheight() - height) // 3)
        window.geometry(f"+{x}+{y}")
        window.deiconify()
        window.lift()
        window.focus_force()

    def refresh_status_window(self) -> None:
        if not self.status_vars:
            return
        settings = load_settings()
        rotation, _remaining = lwa_rotation_status(settings)
        values = {
            "version": APP_VERSION,
            "helper": self.status,
            "amazon": "Configured" if configured(settings) else "Setup incomplete",
            "transport": "Firefox Native Messaging" if native_host_registered() else "Native host not registered",
            "marketplace": marketplace_name(str(settings.get("marketplace_id", ""))),
            "seller": mask_value(str(settings.get("seller_id", ""))),
            "lwa_rotation": rotation,
            "updates": self.update_status,
        }
        for key, value in values.items():
            var = self.status_vars.get(key)
            if var:
                var.set(str(value))

    def show_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.deiconify()
            self.settings_window.lift()
            self.settings_window.focus_force()
            return
        values = load_settings()
        window = tk.Toplevel(self.root, name="settingsWindow")
        self.settings_window = window
        window.title(f"{APP_NAME} {APP_VERSION}")
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        outer = ttk.Frame(window, padding=18)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(1, weight=1)
        ttk.Label(outer, text="Amazon connection", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        ttk.Label(
            outer,
            text="One-time setup. Paste the values from your private Amazon SP-API app.\n"
                 "The client secret and refresh token are stored in Windows Credential Manager.\n"
                 "Firefox uses Native Messaging; Gate Keepa does not open a localhost HTTP port.",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 14))
        client_id_var = tk.StringVar(value=str(values.get("client_id", "")))
        client_secret_var = tk.StringVar(value=get_secret("client_secret"))
        refresh_var = tk.StringVar(value=get_secret("refresh_token"))
        seller_var = tk.StringVar(value=str(values.get("seller_id", "")))
        marketplace_var = tk.StringVar(value=str(values.get("marketplace_id", "ATVPDKIKX0DER")))
        row = 2
        fields = [
            ("Client ID", client_id_var, False), ("Client secret", client_secret_var, True),
            ("Refresh token", refresh_var, True), ("Seller ID", seller_var, False),
        ]
        for label, variable, secret in fields:
            ttk.Label(outer, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
            ttk.Entry(outer, textvariable=variable, width=54, show="•" if secret else "").grid(
                row=row, column=1, columnspan=2, sticky="ew", pady=5
            )
            row += 1
        ttk.Label(outer, text="Marketplace").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
        ttk.Combobox(
            outer, textvariable=marketplace_var, width=51, state="readonly",
            values=["ATVPDKIKX0DER", "A2EUQ1WTGCTBG2", "A1F83G8C2ARO7P"],
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=5)
        row += 1
        ttk.Button(outer, text="Amazon setup instructions", command=lambda: webbrowser.open(AMAZON_SETUP_DOCS)).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=5
        )
        row += 1
        ttk.Separator(outer).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 10))
        row += 1
        self.status_label = ttk.Label(outer, text=self.status)
        self.status_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 10))
        row += 1
        buttons = ttk.Frame(outer)
        buttons.grid(row=row, column=0, columnspan=3, sticky="ew")
        buttons.columnconfigure(0, weight=1)

        def save_and_connect() -> None:
            try:
                existing = load_settings()
                new_secret = client_secret_var.get().strip()
                previous_secret = get_secret("client_secret")
                saved_at = str(existing.get("lwa_rotation_saved_at", "")).strip()
                if new_secret and (new_secret != previous_secret or not saved_at):
                    saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                settings = {
                    "client_id": client_id_var.get(),
                    "seller_id": seller_var.get(),
                    "marketplace_id": marketplace_var.get(),
                    "region": "EU" if marketplace_var.get() == "A1F83G8C2ARO7P" else "NA",
                    "lwa_rotation_saved_at": saved_at,
                }
                save_settings(settings)
                set_secret("client_secret", new_secret)
                set_secret("refresh_token", refresh_var.get())
                remove_legacy_bridge_secret()
                if not configured(settings):
                    raise ValueError("Fill in all Amazon fields first.")
                self.set_status("Ready · native messaging")
                self.notify("Amazon settings saved. Testing authorization…")
                self.test_amazon_async()
            except Exception as exc:
                messagebox.showerror(APP_NAME, str(exc), parent=window)

        ttk.Button(buttons, text="Status", command=self.show_status).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(buttons, text="Save & connect", command=save_and_connect).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Test Amazon", command=self.test_amazon_async).grid(row=0, column=2, padx=4)
        if self._xpi_path().exists():
            ttk.Button(buttons, text="Install Firefox extension", command=self.install_firefox_extension).grid(
                row=0, column=3, padx=4
            )
        ttk.Button(buttons, text="Hide", command=window.withdraw).grid(row=0, column=4, padx=(12, 0))
        window.update_idletasks()
        width = window.winfo_reqwidth()
        height = window.winfo_reqheight()
        x = max(0, (window.winfo_screenwidth() - width) // 2)
        y = max(0, (window.winfo_screenheight() - height) // 3)
        window.geometry(f"+{x}+{y}")
        window.deiconify()
        window.lift()
        window.focus_force()

    def test_amazon_async(self) -> None:
        if not configured():
            self.show_settings()
            self.set_status("Amazon setup is incomplete")
            return
        self.set_status("Testing Amazon authorization…")

        def worker() -> None:
            try:
                client = SpApiClient(make_spapi_config())
                client.access_token()
            except Exception as exc:
                logging.exception("Amazon authorization test failed")
                self.root.after(0, lambda: self._amazon_test_done(False, str(exc)))
            else:
                self.root.after(0, lambda: self._amazon_test_done(True, ""))

        threading.Thread(target=worker, name="amazon-test", daemon=True).start()

    def _amazon_test_done(self, ok: bool, error: str) -> None:
        if ok:
            self.set_status("Amazon connected · native messaging ready")
            self.notify("Amazon connection verified.")
        else:
            self.set_status("Amazon authorization failed")
            messagebox.showerror(
                APP_NAME,
                "Amazon authorization failed. Check the values in Settings.\n\n" + error,
                parent=self.settings_window if self.settings_window else self.root,
            )

    def install_firefox_extension(self) -> None:
        xpi = self._xpi_path()
        if not xpi.exists():
            messagebox.showinfo(
                APP_NAME, "The signed Firefox extension is not bundled in this build yet.",
                parent=self.settings_window if self.settings_window else self.root,
            )
            return
        try:
            if not open_firefox_target(xpi.resolve().as_uri()):
                os.startfile(xpi)  # type: ignore[attr-defined]
        except Exception:
            logging.exception("Could not open Firefox extension package")
            messagebox.showerror(
                APP_NAME, f"Could not open:\n{xpi}",
                parent=self.settings_window if self.settings_window else self.root,
            )

    def create_diagnostics_bundle(self) -> None:
        try:
            for handler in logging.getLogger().handlers:
                try:
                    handler.flush()
                except Exception:
                    pass
            settings = load_settings()
            now = datetime.now(timezone.utc)
            path = APP_DIR / f"GateKeepa-Diagnostics-{now.strftime('%Y%m%d-%H%M%SZ')}.zip"
            rotation, remaining = lwa_rotation_status(settings)
            diagnostics = {
                "generatedAt": now.isoformat(timespec="seconds"),
                "app": {"name": APP_NAME, "version": APP_VERSION},
                "runtime": {
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "frozen": bool(getattr(sys, "frozen", False)),
                    "executable": str(Path(sys.executable).resolve()),
                },
                "settings": {
                    "clientIdMasked": mask_value(str(settings.get("client_id", "")), 4, 4),
                    "sellerIdMasked": mask_value(str(settings.get("seller_id", ""))),
                    "marketplaceId": str(settings.get("marketplace_id", "")),
                    "marketplace": marketplace_name(str(settings.get("marketplace_id", ""))),
                    "region": str(settings.get("region", "")),
                    "lwaRotationSavedAt": str(settings.get("lwa_rotation_saved_at", "")),
                },
                "credentialsPresent": {
                    "clientSecret": bool(get_secret("client_secret")),
                    "refreshToken": bool(get_secret("refresh_token")),
                },
                "nativeMessaging": {
                    "registered": native_host_registered(),
                    "host": NATIVE_HOST_NAME,
                },
                "lwaSecretRotation": {"status": rotation, "daysRemaining": remaining},
                "currentStatus": self.status,
                "updateStatus": self.update_status,
            }
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("diagnostics.json", json.dumps(diagnostics, indent=2, ensure_ascii=False))
                if LOG_PATH.exists():
                    archive.write(LOG_PATH, arcname="helper.log")
                if NATIVE_LOG_PATH.exists():
                    archive.write(NATIVE_LOG_PATH, arcname="native-host.log")
            logging.info("Diagnostics bundle created: %s", path)
            try:
                os.startfile(APP_DIR)  # type: ignore[attr-defined]
            except Exception:
                pass
            messagebox.showinfo(
                APP_NAME,
                f"Diagnostics bundle created:\n\n{path}\n\nNo Amazon secrets are included.",
                parent=self.status_window if self.status_window else self.root,
            )
        except Exception as exc:
            logging.exception("Could not create diagnostics bundle")
            messagebox.showerror(APP_NAME, f"Could not create diagnostics bundle:\n\n{exc}")

    def check_updates_async(self, show_no_update: bool = False) -> None:
        self.update_status = "Checking…"
        self.refresh_status_window()

        def worker() -> None:
            try:
                request = urllib.request.Request(
                    UPDATE_API,
                    headers={"Accept": "application/vnd.github+json", "User-Agent": f"GateKeepa/{APP_VERSION}"},
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    releases = json.loads(response.read().decode("utf-8"))
                candidates: list[tuple[tuple[int, int, int], str, str]] = []
                if isinstance(releases, list):
                    for release in releases:
                        if not isinstance(release, dict) or release.get("draft"):
                            continue
                        tag = str(release.get("tag_name") or "")
                        if not tag.startswith(UPDATE_TAG_PREFIX):
                            continue
                        version = tag[len(UPDATE_TAG_PREFIX):]
                        candidates.append((version_tuple(version), version, str(release.get("html_url") or "")))
                candidates.sort(reverse=True)
                latest = candidates[0] if candidates else None
            except Exception as exc:
                logging.exception("Update check failed")
                self.root.after(0, lambda: self._update_check_done(None, show_no_update, str(exc)))
            else:
                self.root.after(0, lambda: self._update_check_done(latest, show_no_update, ""))

        threading.Thread(target=worker, name="update-check", daemon=True).start()

    def _update_check_done(
        self,
        latest: tuple[tuple[int, int, int], str, str] | None,
        show_no_update: bool,
        error: str,
    ) -> None:
        if error:
            self.update_status = "Check failed"
            self.refresh_status_window()
            if show_no_update:
                messagebox.showerror(APP_NAME, f"Update check failed:\n\n{error}")
            return
        if not latest:
            self.update_status = "No published Gate Keepa release yet"
            self.refresh_status_window()
            if show_no_update:
                messagebox.showinfo(APP_NAME, "No published Gate Keepa release was found yet.")
            return
        latest_tuple, latest_version, release_url = latest
        if latest_tuple > version_tuple(APP_VERSION):
            self.update_status = f"{latest_version} available"
            self.refresh_status_window()
            if messagebox.askyesno(APP_NAME, f"Gate Keepa {latest_version} is available.\n\nOpen the release page?") and release_url:
                webbrowser.open(release_url)
        else:
            self.update_status = f"Up to date ({APP_VERSION})"
            self.refresh_status_window()
            if show_no_update:
                messagebox.showinfo(APP_NAME, f"Gate Keepa {APP_VERSION} is up to date.")

    def open_log(self) -> None:
        try:
            os.startfile(LOG_PATH)  # type: ignore[attr-defined]
        except Exception:
            webbrowser.open(LOG_PATH.as_uri())

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        if self.activation_event and os.name == "nt":
            try:
                kernel32 = _kernel32()
                kernel32.SetEvent(self.activation_event)
                kernel32.CloseHandle(self.activation_event)
            except Exception:
                pass
            self.activation_event = None
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()

    def run(self) -> int:
        self.root.mainloop()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--configure", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    args, _ = parser.parse_known_args()
    configure_logging()
    remove_legacy_bridge_secret()
    if args.smoke_test:
        logging.info("%s %s smoke test passed imports", APP_NAME, APP_VERSION)
        return 0
    instance = acquire_single_instance()
    if instance is None:
        signal_existing_instance()
        return 0
    logging.info("%s %s starting", APP_NAME, APP_VERSION)
    app = HelperApp(show_configure=args.configure)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
