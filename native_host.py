from __future__ import annotations

import json
import logging
import os
import struct
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import keyring

from spapi import APP_VERSION, Config, MARKETPLACE_INFO, SpApiClient, endpoint_for_marketplaces


APP_NAME = "Gate Keepa"
SERVICE_NAME = "SourcingCockpit"
NATIVE_HOST_NAME = "com.marcmy.gatekeepa"
ALLOWED_EXTENSION_ID = "sourcing-cockpit@marcmy.github.io"
MAX_MESSAGE_BYTES = 1_000_000


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    path = root / "SourcingCockpit"
    path.mkdir(parents=True, exist_ok=True)
    return path


APP_DIR = app_data_dir()
SETTINGS_PATH = APP_DIR / "settings.json"
LOG_PATH = APP_DIR / "native-host.log"


def configure_logging() -> None:
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def load_settings() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "client_id": "",
        "seller_id": "",
        "marketplace_id": "ATVPDKIKX0DER",
        "region": "NA",
    }
    if not SETTINGS_PATH.exists():
        return defaults
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            defaults.update(payload)
    except Exception:
        logging.exception("Could not read Gate Keepa settings")
    return defaults


def get_secret(name: str) -> str:
    return keyring.get_password(SERVICE_NAME, name) or ""


def make_config(settings: dict[str, Any] | None = None) -> Config:
    settings = settings or load_settings()
    client_secret = get_secret("client_secret")
    refresh_token = get_secret("refresh_token")
    values = {
        "client_id": str(settings.get("client_id", "")).strip(),
        "client_secret": client_secret.strip(),
        "refresh_token": refresh_token.strip(),
        "seller_id": str(settings.get("seller_id", "")).strip(),
        "marketplace_id": str(settings.get("marketplace_id", "")).strip(),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError("Gate Keepa Amazon setup is incomplete: " + ", ".join(missing))
    region = str(settings.get("region", "NA")).strip().upper() or "NA"
    return Config(
        client_id=values["client_id"],
        client_secret=values["client_secret"],
        refresh_token=values["refresh_token"],
        seller_id=values["seller_id"],
        marketplace_id=values["marketplace_id"],
        region=region,
        user_agent=f"GateKeepa/{APP_VERSION} (Language=Python/3.12; Platform=Windows; Transport=NativeMessaging)",
    )


def mask_value(value: str, head: int = 3, tail: int = 3) -> str:
    value = str(value or "")
    if not value:
        return "Not configured"
    if len(value) <= head + tail + 1:
        return "•" * len(value)
    return f"{value[:head]}…{value[-tail:]}"


_client_lock = threading.Lock()
_client: SpApiClient | None = None
_client_fingerprint: tuple[str, ...] | None = None


def get_client() -> SpApiClient:
    global _client, _client_fingerprint
    settings = load_settings()
    config = make_config(settings)
    fingerprint = (
        config.client_id,
        config.client_secret,
        config.refresh_token,
        config.seller_id,
        config.marketplace_id,
        config.region,
    )
    with _client_lock:
        if _client is None or _client_fingerprint != fingerprint:
            _client = SpApiClient(config)
            _client_fingerprint = fingerprint
        return _client


def validate_eligibility_request(body: dict[str, Any]) -> tuple[list[str], list[str], str | None]:
    raw_asins = body.get("asins")
    if not isinstance(raw_asins, list) or not raw_asins:
        raise ValueError("asins must be a non-empty array")

    asins: list[str] = []
    seen: set[str] = set()
    for value in raw_asins[:100]:
        asin = str(value).strip().upper()
        if not (len(asin) == 10 and asin.isalnum()):
            raise ValueError(f"Invalid ASIN: {value!r}")
        if asin not in seen:
            seen.add(asin)
            asins.append(asin)

    settings = load_settings()
    marketplace_ids = body.get("marketplaceIds")
    if marketplace_ids is None:
        marketplace_ids = [str(settings.get("marketplace_id") or "ATVPDKIKX0DER")]
    if (
        not isinstance(marketplace_ids, list)
        or not marketplace_ids
        or len(marketplace_ids) > 10
        or not all(isinstance(x, str) and x in MARKETPLACE_INFO for x in marketplace_ids)
    ):
        raise ValueError("marketplaceIds must contain supported marketplace IDs")
    endpoint_for_marketplaces(marketplace_ids)

    condition = body.get("conditionType") or None
    if condition is not None and (not isinstance(condition, str) or len(condition) > 64):
        raise ValueError("Invalid conditionType")
    return asins, marketplace_ids, condition


def handle_request(body: dict[str, Any]) -> dict[str, Any]:
    request_type = str(body.get("type") or "").strip()
    if request_type == "ping":
        settings = load_settings()
        return {
            "ok": True,
            "service": "GateKeepaNativeHost",
            "version": APP_VERSION,
            "transport": "native-messaging",
            "marketplaceId": str(settings.get("marketplace_id") or ""),
            "sellerIdMasked": mask_value(str(settings.get("seller_id") or "")),
            "configured": bool(
                str(settings.get("client_id") or "").strip()
                and str(settings.get("seller_id") or "").strip()
                and get_secret("client_secret")
                and get_secret("refresh_token")
            ),
        }

    if request_type != "eligibility":
        raise ValueError(f"Unknown native request type: {request_type or '<missing>'}")

    asins, marketplace_ids, condition = validate_eligibility_request(body)
    client = get_client()
    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(asins))) as pool:
        futures = {
            pool.submit(client.get_restrictions, asin, marketplace_ids, condition): asin
            for asin in asins
        }
        for future in as_completed(futures):
            asin = futures[future]
            try:
                results[asin] = future.result()
            except Exception as exc:
                logging.exception("Eligibility lookup failed for %s", asin)
                results[asin] = {
                    "status": "UNKNOWN",
                    "reasonCodes": [],
                    "message": str(exc),
                    "approvalUrl": None,
                    "error": True,
                }
    return {"ok": True, "results": results}


def read_message(stream) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("Truncated native-message header")
    length = struct.unpack("<I", header)[0]
    if length <= 0 or length > MAX_MESSAGE_BYTES:
        raise ValueError("Invalid native-message size")
    raw = stream.read(length)
    if len(raw) != length:
        raise ValueError("Truncated native-message body")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Native message must be a JSON object")
    return payload


def write_message(stream, payload: dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(raw) > MAX_MESSAGE_BYTES:
        raw = json.dumps({"ok": False, "error": "Native response exceeded size limit"}).encode("utf-8")
    stream.write(struct.pack("<I", len(raw)))
    stream.write(raw)
    stream.flush()


def verify_firefox_invoker(argv: list[str]) -> None:
    # Firefox passes the native manifest path and the initiating extension ID.
    # The manifest itself also restricts allowed_extensions; this is defense in depth.
    if len(argv) < 3:
        raise PermissionError("Native host may only be started by the installed Firefox extension")
    extension_id = str(argv[2]).strip()
    if extension_id != ALLOWED_EXTENSION_ID:
        raise PermissionError("Unapproved extension attempted to start Gate Keepa native host")


def run_native_loop() -> int:
    configure_logging()
    try:
        verify_firefox_invoker(sys.argv)
    except Exception:
        logging.exception("Native host invocation rejected")
        return 2

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        try:
            envelope = read_message(stdin)
            if envelope is None:
                return 0
            request_id = envelope.get("id")
            request = envelope.get("request")
            if not isinstance(request, dict):
                raise ValueError("Missing native request object")
            response = handle_request(request)
            write_message(stdout, {"id": request_id, "response": response})
        except Exception as exc:
            logging.exception("Native message failed")
            try:
                request_id = locals().get("envelope", {}).get("id") if isinstance(locals().get("envelope"), dict) else None
                write_message(stdout, {"id": request_id, "response": {"ok": False, "error": str(exc)}})
            except Exception:
                return 3


def main() -> int:
    if "--smoke-test" in sys.argv:
        configure_logging()
        test = handle_request({"type": "ping"})
        if test.get("service") != "GateKeepaNativeHost":
            return 1
        return 0
    return run_native_loop()


if __name__ == "__main__":
    raise SystemExit(main())
