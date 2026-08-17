# Gate Keepa security architecture

Gate Keepa 0.2.3 is designed around a narrow Amazon SP-API scope: seller-specific **Listings Restrictions** checks using the **Product Listing** role. It does not request the Pricing role or call Product Fees APIs.

## Data path

1. The Firefox extension extracts the ASIN and related product context from Keepa/Amazon pages.
2. The extension sends an eligibility request to the installed Gate Keepa native host using **Firefox Native Messaging** (local OS-managed stdio IPC).
3. The native host reads the seller's SP-API credentials locally and calls Amazon over **HTTPS only**, with TLS 1.2 as the enforced minimum.
4. The native host returns only the UI fields needed by Gate Keepa: eligibility status, reason codes, message, and an HTTPS approval URL when Amazon supplies one.

Gate Keepa does **not** open a localhost HTTP listener in the packaged application. The previous localhost bridge and pairing token were removed, including their dead code and extension host permissions.

## Credential handling

- Amazon client secrets and refresh tokens are stored through Windows Credential Manager using Python `keyring`.
- They are not placed in the Firefox extension, committed to Git, hard-coded into the application, or included in diagnostics bundles.
- Legacy localhost bridge tokens from 0.2.2 are deleted when the 0.2.3 helper starts.
- The Firefox native host manifest allow-lists only the Gate Keepa Firefox add-on ID: `sourcing-cockpit@marcmy.github.io`.
- The native host also checks the initiating Firefox add-on ID at process start as defense in depth.

## Transport controls

- Amazon LWA and SP-API endpoints are hard-coded as `https://` endpoints.
- The SP-API client refuses non-HTTPS request URLs before network access.
- Its TLS context enforces TLS 1.2 or newer.
- Redirects to a non-HTTPS URL are refused.
- Firefox-to-native-host communication uses Native Messaging on the same Windows host and does not create a TCP/IP network service.

## Data minimization

- Raw Listings Restrictions responses are not returned to Firefox or cached by Gate Keepa.
- The extension caches only the reduced eligibility fields required for its UI plus local sourcing metadata.
- Optional GitHub Gist synchronization was removed from 0.2.3, along with its GitHub host permission and token setting, reducing external data movement and credential surface.

## LWA client-secret rotation

Amazon requires LWA client-secret rotation on its schedule. Gate Keepa records the local time when a client secret is first saved or changed and displays an advisory countdown based on 180 days. It warns when 30 days or fewer remain.

This local timestamp is only a convenience reminder; Amazon's own developer console and notices are authoritative for the actual rotation deadline.

## Diagnostics

The diagnostics ZIP may include:

- application/runtime version information;
- masked client and seller IDs;
- marketplace and region;
- whether credentials are present;
- native-host registration status;
- the local LWA-rotation reminder state;
- helper/native-host logs.

It does not contain the Amazon client secret or refresh token.

## Scope boundary

Application controls cannot by themselves establish an organization's firewall, IDS/IPS, network segmentation, account-password policy, security training, access review, or incident-response practices. Those controls must actually exist in the seller's environment before they are represented to Amazon as implemented.
