# Gate Keepa

A local-first **Firefox** sourcing companion for Amazon + Keepa.

Gate Keepa is a clean-room implementation. It does not copy SourceLens code, assets, guides, or proprietary scoring logic. Seller-specific eligibility is obtained through Amazon's official Selling Partner API (SP-API).

Current development version: **0.2.3**.

## Scope

Gate Keepa focuses on seller-specific sourcing restrictions:

- Keepa row ASIN discovery with inline eligibility badges
- live SP-API Listings Restrictions checks
- sellable / approval-required / restricted states
- approval links when Amazon supplies them
- eligibility cache with manual clear and configurable TTL
- local brand/category gating observations
- bookmarks / Watch Later
- per-ASIN notes
- sourcing history + CSV export
- local cost CSV import/export
- transparent local deal-score heuristic
- locally observed seller-count trend
- heuristic meltable/hazmat warnings
- similar-product / rabbit-trail helpers
- Amazon product-page eligibility panel
- US / Canada / UK marketplace-aware links
- Pomodoro sourcing timer

Gate Keepa deliberately **does not estimate Amazon selling fees or profitability**. It does not call Product Fees and does not require the Pricing role.

## Amazon role

The private SP-API app needs only the **Product Listing** role for seller-specific Listings Restrictions checks.

## Normal Windows / Firefox setup

The packaged build is designed so the end user does **not** need Python, PowerShell, Node, a terminal, JSON editing, or `about:debugging`.

1. Run `GateKeepa-Setup-0.2.3.exe`.
2. Leave **Start Gate Keepa automatically when I sign in** enabled.
3. In the setup window, enter the four values from the seller's private Amazon SP-API app:
   - Client ID
   - Client secret
   - Refresh token
   - Seller ID
4. Click **Save & connect**.
5. Accept installation of the bundled Mozilla-signed Firefox add-on when prompted.
6. Open Keepa and use it normally.

There is **no browser-pairing step and no localhost HTTP server** in 0.2.3. The installer registers a Firefox Native Messaging host automatically. Firefox communicates with the installed Gate Keepa native host through OS-managed stdio IPC.

For a private SP-API app, Amazon still requires the seller to perform Amazon's own self-authorization flow. Gate Keepa does not automate or bypass that process.

## Security changes in 0.2.3

The 0.2.3 architecture was tightened specifically around Amazon Information handling:

- removed the packaged localhost HTTP bridge and pairing-token mechanism;
- removed localhost extension permissions and dead pairing code;
- added Firefox Native Messaging restricted to Gate Keepa's existing add-on ID;
- added defense-in-depth verification of the initiating add-on ID in the native host;
- enforce HTTPS-only Amazon requests with a TLS 1.2 minimum;
- refuse redirects from HTTPS to non-TLS URLs;
- keep the LWA client secret and refresh token in Windows Credential Manager;
- stop returning/caching Amazon's raw Listings Restrictions payload;
- removed optional GitHub Gist sync and its browser-stored GitHub token;
- delete the obsolete 0.2.2 localhost bridge token when the helper starts;
- add an advisory 180-day LWA client-secret rotation countdown/warning.

See [`SECURITY.md`](SECURITY.md) for the technical data path and control boundaries.

## Security questionnaire support

The `compliance/` directory contains small-business templates and guidance:

- `INCIDENT_RESPONSE_PLAN.md` — defined incident role, 24-hour Amazon reporting procedure, and six-month review schedule
- `ACCESS_CONTROL_POLICY.md` — least-privilege and authorized-user policy
- `SECURITY_QUESTIONNAIRE_GUIDE.md` — maps Amazon questions to Gate Keepa controls versus controls the seller must actually operate

A template is **not** a security control merely because it exists in the repository. The seller must fill it out, adopt it, and actually follow it before representing that control as implemented.

## LWA secret rotation

Gate Keepa records the local date when the client secret is first saved or changed. The Status window shows an advisory countdown based on 180 days and warns at 30 days or fewer.

Amazon's own developer console/notifications remain authoritative for the real rotation deadline.

## Helper support features

The Windows notification-area app provides:

- **Status** — version, Amazon setup state, Native Messaging registration, marketplace, masked seller ID, LWA rotation reminder, update status
- **Test Amazon connection** — verifies Login with Amazon authorization
- **Install Firefox extension** — opens the bundled signed XPI in Firefox
- **Create diagnostics bundle** — sanitized local diagnostics and logs
- **Check for updates** — checks `gate-keepa-vX.Y.Z` GitHub releases
- **Open log**

Diagnostics do not include the Amazon client secret or refresh token.

## Firefox signing

Normal Firefox installation requires Mozilla signing. Release builds use the configured AMO credentials to obtain an unlisted Mozilla signature before creating the end-user installer. The existing add-on ID is retained so upgrades continue through the same Firefox identity.

## Windows signing

The Windows installer/helper are not currently Authenticode-signed. Windows SmartScreen may therefore display an unknown-publisher warning. Removing that warning cleanly requires a Windows code-signing certificate and signing step.

## Developer layout

- `extension/` — Firefox Manifest V3 extension source
- `spapi.py` — TLS-only SP-API client and restriction classification
- `native_host.py` — Firefox Native Messaging host
- `helper.py` — Windows GUI/tray credential/status helper
- `GateKeepa.spec` — helper PyInstaller build
- `GateKeepaNativeHost.spec` — native host PyInstaller build
- `native-messaging/` — Firefox native-host manifest
- `installer/` — Inno Setup installer and native-host registration
- `compliance/` — optional policy templates/guidance

## Build and artifacts

`.github/workflows/gate-keepa-build.yml` validates version consistency, Python/JavaScript syntax, native-message framing and restriction-classification tests, the restriction-only API scope, the no-localhost/TLS security model, frozen helper/native-host builds, Firefox packaging/signing, and the Inno Setup installer.

A signed end-user artifact contains only:

- `GateKeepa-Setup-X.Y.Z.exe`
- `SHA256.txt`

Developer artifacts additionally contain the frozen helper, native host, native manifest, installer, and Firefox build products.

## Known limits

Final acceptance still needs a live Keepa page and the seller's authorized Amazon account. CI can verify packaging and application logic but cannot prove current third-party DOM/account behavior without those services.

Gate Keepa intentionally does not fake proprietary or undocumented SourceLens features such as its exact scoring model, guides, regional Buy Box sweeps, or exact Keepa chart overlays.

## Upgrade compatibility

Gate Keepa retains the existing Firefox add-on ID, Windows installer AppId, Windows Credential Manager service name, and `%LOCALAPPDATA%\SourcingCockpit` data directory so earlier 0.2.x installations can upgrade without creating a second credential/application identity. The obsolete localhost pairing identity is intentionally retired in 0.2.3.
