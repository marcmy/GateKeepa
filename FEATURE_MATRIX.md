# Feature matrix

This is a clean-room workflow recreation based on public product descriptions and official APIs.
It does not contain SourceLens code, assets, or proprietary scoring logic.

| SourceLens-advertised area | Gate Keepa status | Notes |
|---|---|---|
| Keepa row eligibility | Implemented | Official SP-API Listings Restrictions via Firefox Native Messaging host |
| Green/yellow/red gating | Implemented | Seller-specific; approval URL shown when available |
| Eligibility cache / clear | Implemented | Configurable TTL; reduced UI fields only |
| Brand/category gating DB | Implemented | Learns from rows observed locally |
| Bookmarks / Watch Later | Implemented | Local browser storage |
| Product notes | Implemented | Amazon page panel, local storage |
| Sourcing history / CSV | Implemented | Up to 2,000 latest observations |
| Bulk cost file | Implemented | CSV import/export, per-ASIN cost storage |
| Deal Score | Partial | Transparent local heuristic; not SourceLens' proprietary score |
| Competition trend | Partial | Local observed seller-count trend, not Keepa historical-series decoding |
| Meltable / hazmat flags | Partial | Keyword warnings only; deliberately labeled heuristic |
| Similar Product finder | Implemented | Keepa title-keyword search helper |
| Rabbit Trail finder | Implemented | Amazon narrow search helper |
| Amazon product page tools | Implemented | Eligibility, bookmark, note, Keepa jump |
| Product fee estimate | Out of scope | Deliberately omitted; Gate Keepa does not use Product Fees or require Pricing |
| Pomodoro timer | Implemented | 25-minute in-page timer |
| Team/Gist sync | Removed | Removed in 0.2.3 to minimize external data movement and stored credentials |
| Regional Buy Box map / 8-region sweep | Not implemented | Would require reliable location-specific offer capture; not faked |
| Exact Keepa chart break-even line | Not implemented | Chart internals need targeted DOM/chart adapter |
| Competitor storefront -> Product Finder | Scaffold candidate | Exact Product Finder mapping should be verified against live Keepa |
| AI supplier research | Not implemented | Requires an external service/API and supplier-research design |
| Proprietary sourcing guides | Not implemented | SourceLens documentation content is proprietary |

## Security/transport status

- Firefox-to-local-app transport: Native Messaging, no packaged localhost HTTP listener.
- Amazon transport: HTTPS only; TLS 1.2 minimum; non-TLS redirects refused.
- Amazon secrets: Windows Credential Manager, not browser storage/source/diagnostics.
- SP-API scope: Listings Restrictions / Product Listing role only.
- Raw Amazon restrictions response: not returned to Firefox or cached.

## Next high-value targets

1. Verify Keepa's live DOM selectors with the seller's normal workflow.
2. Verify the installed Native Messaging registry/host handoff on a clean Windows/Firefox machine.
3. Complete real seller-account acceptance against Listings Restrictions.
4. Add only workflow features that do not broaden SP-API/data-security scope without an explicit need.
