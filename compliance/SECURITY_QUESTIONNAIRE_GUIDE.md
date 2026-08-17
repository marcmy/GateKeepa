# Amazon security questionnaire guide

This document maps common Amazon SP-API security questions to Gate Keepa's technical controls and to controls that must exist in the seller's real environment.

**Do not answer `Yes` merely because this repository contains a policy template or because Gate Keepa implements one part of a multi-part question.** Answer based on controls that are actually implemented and followed by the organization.

| Question area | Gate Keepa 0.2.3 contribution | What the organization must verify before answering Yes |
|---|---|---|
| Firewalls, IDS/IPS, anti-virus/anti-malware, and network segmentation | Gate Keepa minimizes its own network surface and does not open a localhost HTTP listener. | The environment actually has **all** controls named by Amazon. A normal endpoint firewall/anti-malware installation alone does not establish IDS/IPS plus network segmentation. |
| Restrict access based on job duties/business functions | Gate Keepa credentials stay in Windows Credential Manager and the SP-API app needs only Product Listing. See `ACCESS_CONTROL_POLICY.md`. | Only authorized people have access, access corresponds to a real business need, shared/unnecessary access is prevented, and the policy is actually adopted/followed. |
| Encrypt Amazon Information in transit | Amazon-bound requests are HTTPS-only with TLS 1.2 minimum. Firefox-to-host traffic uses same-device Firefox Native Messaging rather than a network listener. Non-TLS Amazon requests/redirects are refused. | There are no other organizational workflows that send Amazon Information across a network without the required encryption. |
| Incident-response plan with defined roles, six-month reviews, and 24-hour procedures | `INCIDENT_RESPONSE_PLAN.md` contains a small-business plan covering these points. | Fill in the organization/IMPOC/dates, formally adopt it, maintain the review schedule, and actually follow it. An untouched template is not a Yes. |
| Report incidents involving Amazon Information to security@amazon.com within 24 hours | The incident-response template explicitly contains this procedure. | Adopt the plan and ensure the responsible person knows and follows the procedure. |
| Password/MFA/expiration/rotation controls | Gate Keepa does not store seller-account passwords and does not weaken Amazon MFA. | Verify the exact password/MFA requirements Amazon asks about are actually enforced for the applicable accounts/systems. Do not infer Yes from Amazon MFA alone if the question is conjunctive. |
| Credentials stored securely/not hard-coded/public | Client secret and refresh token are stored in Windows Credential Manager. They are absent from browser settings, source, public Git, and diagnostics. | Operators must also avoid copying those credentials into email/chat/public repos or otherwise sharing them insecurely. |

## Technical changes in 0.2.3 relevant to the questionnaire

- Removed the packaged localhost HTTP bridge and its pairing/token mechanism.
- Removed localhost extension permissions and pairing page/script.
- Added Firefox Native Messaging with a native manifest restricted to the Gate Keepa add-on ID.
- Added a second native-host check of the invoking add-on ID.
- Enforced HTTPS and TLS 1.2+ for Amazon requests and rejected non-TLS redirects.
- Stopped returning/caching Amazon's raw Listings Restrictions payload; only UI-relevant reduced fields are retained.
- Removed optional GitHub Gist synchronization and its stored GitHub token to reduce external data movement.
- Added an advisory LWA client-secret rotation countdown based on the date a secret is saved/changed locally.
- Preserved Windows Credential Manager for the LWA client secret and refresh token.

## Items Gate Keepa cannot make true by itself

Gate Keepa cannot create an organizational IDS/IPS, segment the seller's home/business network, enforce every password policy across unrelated systems, conduct security training, perform external penetration tests, or make a policy real merely by storing a Markdown document. Those are environment/organizational controls and should be answered based on reality.

When a question contains several controls joined by “and,” treat the answer as Yes only if every required component is actually satisfied.
