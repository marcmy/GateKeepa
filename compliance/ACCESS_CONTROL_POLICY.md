# Amazon Information Access Control Policy

**Organization:** ______________________________  
**Owner:** ______________________________  
**Effective date:** ______________________________  
**Last reviewed:** ______________________________  
**Next quarterly review due:** ______________________________

> This template is evidence of a control only after the organization adopts and follows it.

## Scope

This policy covers access to Amazon Information, the Amazon seller account, SP-API application credentials, Gate Keepa configuration, and computers/accounts used to operate Gate Keepa.

## Least privilege

- Access is limited to people whose business duties require it.
- If the organization has one operator, that operator is the only authorized user unless this document is updated.
- Gate Keepa's Amazon application is limited to the **Product Listing** role needed for Listings Restrictions checks.
- Pricing/Product Fees access is not required by Gate Keepa and should not be granted for Gate Keepa.
- New access must be explicitly approved by the owner before it is provided.
- Access must be removed promptly when it is no longer required, and within Amazon's required timeframe when a user leaves the organization.

## Account use

- Authorized users use their own individual account/identity where the service supports it.
- Seller Central, email, Windows, and other security-sensitive accounts are not intentionally shared between unrelated users.
- MFA is enabled on the Amazon seller account and other applicable security-sensitive accounts where the organization can configure it.
- Passwords and authentication factors are not sent through chat, email, public repositories, or source code.

## SP-API credentials

- The LWA client secret and refresh token are entered directly into the installed Gate Keepa helper.
- Gate Keepa stores them through Windows Credential Manager.
- Live credentials are not committed to Git, hard-coded in source, or included in support diagnostics.
- LWA credentials are rotated according to Amazon's required schedule. Gate Keepa's local 180-day reminder is advisory; Amazon's own deadline is authoritative.

## Device access

- Devices used to access Amazon Information must use a login controlled by an authorized operator.
- The authorized operator is responsible for keeping the OS, browser, Gate Keepa, and anti-malware protections current.
- Other household, guest, or unrelated users are not intentionally given access to the operator's authenticated seller/Gate Keepa session.

## Quarterly review

Access will be reviewed **at least quarterly** and whenever there is a material staffing/account change. The review confirms:

- who is authorized;
- whether each person's access is still necessary;
- whether former/unneeded access has been removed;
- whether service/application access still follows least privilege;
- whether Gate Keepa still uses only the minimum Amazon role required;
- whether credentials are due for rotation.

The owner records the review date and next review due date at the top of this document or in an equivalent access-review record.

## Current authorized users

| Person | Business function requiring access | Systems/accounts | Approved by | Date |
|---|---|---|---|---|
| __________________ | __________________ | __________________ | __________________ | __________________ |

## Adoption

I confirm that this policy describes the access-control practices this organization will actually follow.

**Name:** ______________________________  
**Signature/approval:** ______________________________  
**Date:** ______________________________
