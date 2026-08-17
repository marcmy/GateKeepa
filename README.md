# Gate Keepa

A local-first Firefox/Chrome/Edge sourcing companion for Amazon + Keepa.

This project deliberately does **not** copy SourceLens code, assets, guides, or proprietary scoring logic. It recreates useful workflow pieces using public page integration, local storage, and Amazon's official Selling Partner API (SP-API).

## Implemented

- Keepa row ASIN discovery with inline eligibility badges
- Live seller-specific eligibility via SP-API Listings Restrictions
- Approval-required links when Amazon supplies them
- Eligibility cache with manual clear and configurable TTL
- Local gating database generated from observed products
- Bookmarks / Watch Later
- Per-ASIN notes
- Sourcing history + CSV export
- Bulk ASIN cost CSV import/export
- Local deal score heuristic
- Competition trend from locally observed seller-count changes
- Heuristic meltable / hazmat flags
- Similar-product / rabbit-trail search helpers
- Amazon product-page panel
- US / Canada / UK marketplace-aware Amazon and Keepa links
- Pomodoro sourcing timer
- Optional team sync through a GitHub Gist
- Firefox + Chromium Manifest V3 background support
- One-click browser-to-helper pairing with a random localhost bridge token
- Helper status screen, diagnostics bundle creation, and update checks

Gate Keepa intentionally does **not** estimate Amazon selling fees or profitability. That functionality is outside this project's scope.

## Normal Windows setup — intended for Doug

The packaged build is designed so the user does **not** need Python, PowerShell, Node, a terminal, JSON editing, or `about:debugging`.

1. Run `GateKeepa-Setup-0.2.2.exe`.
2. Leave **Start Gate Keepa automatically when I sign in** enabled.
3. The setup window opens. Paste the four values from the seller's private Amazon SP-API app:
   - Client ID
   - Client secret
   - Refresh token
   - Seller ID
4. Click **Save & connect**. The helper verifies Login with Amazon authorization and then stays in the Windows notification area.
5. Install the bundled Mozilla-signed Firefox add-on when prompted.
6. In the helper choose **Pair browser**. Gate Keepa prefers Firefox explicitly for the pairing page; if Firefox cannot be located it falls back to the Windows default browser. The one-time pairing window expires after two minutes.
7. Open Keepa and use it normally.

After first setup the helper starts automatically with Windows and runs the Amazon bridge on localhost. Launching Gate Keepa again brings the existing instance's settings window forward rather than starting a duplicate helper.

### The one unavoidable Amazon step

For a private SP-API application Amazon requires self-authorization. The helper deliberately does not attempt to automate or bypass Amazon's developer authorization process. Once Amazon has issued the values above, they are entered once through the GUI.

Gate Keepa needs only the **Product Listing** role for seller-specific Listings Restrictions checks. It does **not** call Amazon's Product Fees API and does **not** require the **Pricing** role.

### Firefox signing

Release/Beta Firefox requires Mozilla signing for normally installed extensions. The repository has AMO signing credentials configured, and release builds can obtain an unlisted Mozilla signature before creating the end-user installer.

The signing job allows up to 60 minutes for Mozilla approval so a normal validation queue does not cause a false CI failure.

### Windows signing

The current Windows installer/helper are not Authenticode-signed. Windows SmartScreen may therefore display an unknown-publisher warning on a fresh download. That is a packaging/reputation issue rather than an application dependency; removing the warning cleanly requires a Windows code-signing certificate and signing step.

## Helper support features

The notification-area menu exposes:

- **Status** — version, helper/bridge state, marketplace, masked seller ID, browser-pairing state and update status
- **Test Amazon connection** — verifies the stored Login with Amazon authorization
- **Pair browser extension** — opens a two-minute, one-time localhost pairing flow
- **Create diagnostics bundle** — writes a ZIP under `%LOCALAPPDATA%\SourcingCockpit` containing a sanitized diagnostics JSON and helper log
- **Check for updates** — looks for GitHub releases tagged `gate-keepa-vX.Y.Z`
- **Open log** — opens the local helper log

Diagnostics deliberately contain only masked IDs and booleans indicating whether credentials exist. They do **not** include the Amazon client secret, refresh token, or localhost bridge token.

## Security model

- The Amazon client secret and refresh token are stored through Windows Credential Manager using `keyring`.
- A random localhost bridge token is also stored in Windows Credential Manager.
- The browser extension receives that bridge token only through a short-lived one-time pairing flow and stores it in extension-local storage.
- The eligibility POST endpoint requires the paired bridge token in addition to the existing extension-origin checks.
- Non-secret Amazon settings live under `%LOCALAPPDATA%\SourcingCockpit`.
- The helper binds the SP-API bridge to `127.0.0.1` only.
- The bridge rejects ordinary website origins and browser CORS preflights so random web pages cannot spend the seller's Amazon API quota through localhost.
- POST endpoints require JSON request bodies and do not return raw Amazon error payloads.
- Amazon secrets are never stored in the browser extension or committed to git.
- Gist synchronization is optional and disabled by default. Firefox requests its additional data-collection permissions only if the user enables the feature, and Gist traffic is refused if that consent is later removed.
- Eligibility/storage writes are serialized so concurrent Keepa scans do not silently overwrite one another's cache/history/gating updates.

## Developer layout

- `extension/` — cross-browser Manifest V3 extension
- `bridge/` — localhost SP-API implementation
- `helper.py` — Windows GUI/tray wrapper around the bridge
- `GateKeepa.spec` — one-file PyInstaller build
- `installer/` — Inno Setup installer

For direct bridge development, copy `bridge/config.example.json` to `bridge/config.json` and run:

```powershell
py -3.12 .\bridge\server.py --config .\bridge\config.json
```

Direct developer mode remains backwards-compatible without helper-managed bridge authentication unless `SOURCING_COCKPIT_BRIDGE_TOKEN` is set. End users should use the packaged helper.

## Build and artifacts

`.github/workflows/gate-keepa-build.yml` validates the Python and JavaScript, runs bridge unit tests, verifies that Product Fees functionality has not been reintroduced, builds `GateKeepa.exe`, smoke-tests the frozen executable, stages/lints/packages the Firefox extension, optionally obtains an unlisted Mozilla signature for release builds, builds the per-user Windows installer, and uploads developer/release artifacts as appropriate.

A signed end-user artifact contains only:

- `GateKeepa-Setup-X.Y.Z.exe`
- `SHA256.txt`

Raw helper/Firefox build products are kept in a separate developer artifact so the normal download is not cluttered with unsigned ZIPs and duplicate XPI names.

## Known limits

SourceLens also advertises features that depend on proprietary logic, undocumented page integrations, or data we cannot faithfully derive from the public page alone — notably regional Buy Box sweeps and its exact Keepa chart break-even overlay. Those are intentionally not faked here.

DOM extraction is defensive rather than coupled to one Keepa build, but Keepa can still change its markup. Final acceptance still needs a live Keepa page and the seller's authorized Amazon account; CI can verify packaging and application logic but cannot prove third-party DOM/account integration without those real services.

## Rename compatibility

Gate Keepa intentionally preserves the original Firefox add-on ID, Windows installer AppId, Credential Manager service name, localhost authentication header, and `%LOCALAPPDATA%\SourcingCockpit` data directory. Those internal identifiers are retained so existing Sourcing Cockpit installations, credentials, pairing data, and Mozilla signing identity can upgrade in place.
