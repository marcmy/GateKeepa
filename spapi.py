from __future__ import annotations

import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_VERSION = "0.2.3"
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
REGION_ENDPOINTS = {
    "NA": "https://sellingpartnerapi-na.amazon.com",
    "EU": "https://sellingpartnerapi-eu.amazon.com",
    "FE": "https://sellingpartnerapi-fe.amazon.com",
}
MARKETPLACE_INFO = {
    "ATVPDKIKX0DER": {"region": "NA", "currency": "USD"},
    "A2EUQ1WTGCTBG2": {"region": "NA", "currency": "CAD"},
    "A1F83G8C2ARO7P": {"region": "EU", "currency": "GBP"},
}

_TLS_CONTEXT = ssl.create_default_context()
_TLS_CONTEXT.minimum_version = ssl.TLSVersion.TLSv1_2


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if urllib.parse.urlparse(newurl).scheme.lower() != "https":
            raise urllib.error.URLError("Refusing redirect to a non-TLS URL")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(
    _HttpsOnlyRedirectHandler(),
    urllib.request.HTTPSHandler(context=_TLS_CONTEXT),
)


def endpoint_for_marketplaces(marketplace_ids: list[str]) -> str:
    if not marketplace_ids:
        raise ValueError("At least one marketplace ID is required")
    regions: set[str] = set()
    for marketplace_id in marketplace_ids:
        info = MARKETPLACE_INFO.get(marketplace_id)
        if not info:
            raise ValueError(f"Unsupported marketplace: {marketplace_id}")
        regions.add(str(info["region"]))
    if len(regions) != 1:
        raise ValueError("A single SP-API request cannot mix marketplaces from different regions")
    return REGION_ENDPOINTS[regions.pop()]


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Config:
    client_id: str
    client_secret: str
    refresh_token: str
    seller_id: str
    marketplace_id: str
    region: str = "NA"
    user_agent: str = f"GateKeepa/{APP_VERSION} (Language=Python/3.12)"

    @property
    def endpoint(self) -> str:
        try:
            return REGION_ENDPOINTS[self.region.upper()]
        except KeyError as exc:
            raise ValueError(f"Unsupported region {self.region!r}; expected NA, EU, or FE") from exc

    @classmethod
    def load(cls, path: Path) -> "Config":
        data = json.loads(path.read_text(encoding="utf-8"))
        required = ["client_id", "client_secret", "refresh_token", "seller_id", "marketplace_id"]
        missing = [key for key in required if not str(data.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Missing required config keys: {', '.join(missing)}")
        return cls(
            client_id=str(data["client_id"]).strip(),
            client_secret=str(data["client_secret"]).strip(),
            refresh_token=str(data["refresh_token"]).strip(),
            seller_id=str(data["seller_id"]).strip(),
            marketplace_id=str(data["marketplace_id"]).strip(),
            region=str(data.get("region", "NA")).strip().upper() or "NA",
            user_agent=str(data.get("user_agent") or cls.user_agent),
        )


class RateGate:
    def __init__(self, min_interval_seconds: float):
        self._min_interval = min_interval_seconds
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
            self._next = time.monotonic() + self._min_interval


class SpApiClient:
    def __init__(self, config: Config):
        self.config = config
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()
        self._restrictions_gate = RateGate(0.21)

    def _json_request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        form: dict[str, str] | None = None,
        timeout: float = 25.0,
    ) -> tuple[Any, dict[str, str]]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("Gate Keepa refuses non-TLS Amazon API requests")

        req_headers = dict(headers or {})
        data: bytes | None = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            req_headers["Content-Type"] = "application/x-www-form-urlencoded"

        request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with _OPENER.open(request, timeout=timeout) as response:
                raw = response.read()
                if not raw:
                    payload: Any = {}
                else:
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise ApiError("Amazon returned an invalid JSON response") from exc
                return payload, dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                payload = {}
            message = _amazon_error_message(payload) or f"HTTP {exc.code}"
            raise ApiError(message, exc.code) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Network error: {exc.reason}") from exc

    def access_token(self) -> str:
        with self._token_lock:
            if self._token and time.time() < self._token_expires_at - 60:
                return self._token
            payload, _ = self._json_request(
                LWA_TOKEN_URL,
                method="POST",
                form={
                    "grant_type": "refresh_token",
                    "refresh_token": self.config.refresh_token,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                },
            )
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not token:
                raise ApiError("LWA response did not contain access_token")
            expires_in = int(payload.get("expires_in", 3600))
            self._token = str(token)
            self._token_expires_at = time.time() + expires_in
            return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "x-amz-access-token": self.access_token(),
            "user-agent": self.config.user_agent,
            "accept": "application/json",
        }

    def get_restrictions(
        self,
        asin: str,
        marketplace_ids: list[str] | None = None,
        condition_type: str | None = None,
    ) -> dict[str, Any]:
        self._restrictions_gate.wait()
        marketplaces = marketplace_ids or [self.config.marketplace_id]
        endpoint = endpoint_for_marketplaces(marketplaces)
        params: list[tuple[str, str]] = [
            ("asin", asin),
            ("sellerId", self.config.seller_id),
            ("marketplaceIds", ",".join(marketplaces)),
        ]
        if condition_type:
            params.append(("conditionType", condition_type))
        url = f"{endpoint}/listings/2021-08-01/restrictions?{urllib.parse.urlencode(params)}"
        payload, _headers = self._json_request(url, headers=self._headers())
        if not isinstance(payload, dict):
            raise ApiError("Amazon returned an unexpected restrictions response")
        return classify_restrictions(payload)


def _amazon_error_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                return first.get("message") or first.get("code")
        return payload.get("error_description") or payload.get("message")
    return None


def classify_restrictions(payload: dict[str, Any]) -> dict[str, Any]:
    restrictions = payload.get("restrictions") or []
    reasons: list[dict[str, Any]] = []
    for restriction in restrictions:
        if isinstance(restriction, dict):
            reasons.extend(x for x in (restriction.get("reasons") or []) if isinstance(x, dict))

    reason_codes = sorted({
        str(reason.get("reasonCode"))
        for reason in reasons
        if reason.get("reasonCode")
    })
    messages = [str(reason.get("message")) for reason in reasons if reason.get("message")]

    approval_url = None
    for reason in reasons:
        for link in reason.get("links") or []:
            if not isinstance(link, dict):
                continue
            resource = link.get("resource")
            if resource and str(resource).startswith("https://"):
                approval_url = str(resource)
                if reason.get("reasonCode") == "APPROVAL_REQUIRED":
                    break
        if approval_url and reason.get("reasonCode") == "APPROVAL_REQUIRED":
            break

    if not restrictions:
        status = "SELLABLE"
    elif "NOT_ELIGIBLE" in reason_codes:
        status = "RESTRICTED"
    elif "APPROVAL_REQUIRED" in reason_codes:
        status = "APPROVAL_REQUIRED"
    elif "ASIN_NOT_FOUND" in reason_codes:
        status = "UNKNOWN"
    else:
        status = "RESTRICTED"

    # Return only the fields needed by the UI. Avoid caching the raw Amazon response.
    return {
        "status": status,
        "reasonCodes": reason_codes,
        "message": " | ".join(dict.fromkeys(messages)),
        "approvalUrl": approval_url,
    }
