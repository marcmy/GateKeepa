# Amazon Information Incident Response Plan

**Organization:** ______________________________  
**Incident Management Point of Contact (IMPOC):** ______________________________  
**Effective date:** ______________________________  
**Last reviewed:** ______________________________  
**Next review due (no later than 6 months):** ______________________________

> This template becomes an organizational control only after the organization fills it out, adopts it, and follows it. Keeping an unused template in the Gate Keepa repository is not itself an incident-response program.

## 1. Purpose and scope

This plan covers suspected or confirmed security incidents involving Amazon Information, Amazon Selling Partner API credentials, the Amazon seller account, or systems used to access Gate Keepa/SP-API.

For this small organization, the IMPOC is the person responsible for coordinating detection, containment, Amazon notification, remediation, recovery, and documentation. If there is only one authorized operator, that person holds all incident-response roles listed below.

## 2. Roles and authority

The IMPOC is authorized to:

- stop use of Gate Keepa and affected devices;
- disconnect an affected device from the network;
- revoke or rotate Amazon LWA credentials and other affected credentials;
- change account passwords and require re-authentication;
- preserve logs and other evidence;
- contact Amazon and other service providers;
- restore service only after the immediate risk is addressed.

If another person is authorized to access Amazon Information, that person must immediately report suspected incidents to the IMPOC and follow the IMPOC's containment instructions.

## 3. What counts as an incident

Examples include:

- suspected compromise, loss, or disclosure of an Amazon refresh token, client secret, seller account password, or MFA factor;
- malware or unauthorized access on a computer used for Amazon Information;
- accidental publication of credentials or Amazon Information;
- unexpected SP-API activity or account access;
- loss or theft of a device containing or able to access Amazon Information;
- confirmed or suspected access by a person who is not authorized;
- a vulnerability or misconfiguration that has resulted in unauthorized access or disclosure.

## 4. Response procedure

### Detect and record

1. Record the time the incident was detected. This timestamp starts the Amazon 24-hour notification window when Amazon Information is involved.
2. Record what was observed, affected account/device/application, and who discovered it.
3. Preserve relevant Gate Keepa logs, Windows security information, Amazon notices, screenshots, and other available evidence. Do not copy credentials into the incident record.

### Contain

1. Stop Gate Keepa/SP-API activity if continued use could worsen the incident.
2. Disconnect compromised devices from networks when appropriate.
3. Revoke or rotate affected LWA client secrets, refresh tokens, passwords, API credentials, and MFA factors as appropriate.
4. Remove unauthorized access and disable affected accounts or sessions where possible.

### Notify Amazon within 24 hours

For a security incident involving Amazon Information, the IMPOC will report the incident to **security@amazon.com within 24 hours of detection**.

The report should include, to the extent known and safe to provide:

- organization/seller identity and contact information;
- detection time;
- concise description of the incident;
- Amazon Information or credentials potentially affected;
- known scope and impact;
- containment/remediation steps already taken;
- a contact for follow-up.

Do not email passwords, client secrets, refresh tokens, or other live credentials.

### Eradicate and recover

1. Remove malware, vulnerable software, exposed credentials, or other root causes.
2. Apply relevant OS/browser/application updates.
3. Confirm only authorized users retain access.
4. Verify newly rotated credentials work and old credentials are invalidated as applicable.
5. Resume Gate Keepa/SP-API use only after the IMPOC determines the affected environment is safe enough to return to service.

### Post-incident review

Within a reasonable period after containment:

1. Document what happened, why, and the actions taken.
2. Identify preventive changes.
3. Update this plan or related controls if needed.
4. Record the date the incident was closed.

## 5. Review schedule

This plan will be reviewed **at least once every six months**, and additionally after any material security incident or significant change to the SP-API environment.

Each review will confirm:

- the IMPOC/contact details are current;
- `security@amazon.com` and the 24-hour reporting requirement remain in the procedure;
- current systems, credentials, and authorized users are represented;
- any lessons from incidents or security changes have been incorporated.

## 6. Incident record

For each incident, keep a record containing at least:

- incident identifier;
- detection date/time;
- reporter;
- affected systems/accounts;
- summary and suspected cause;
- containment/remediation actions and timestamps;
- Amazon notification timestamp, if applicable;
- recovery/closure date;
- follow-up actions.

Do not store live secrets in the incident record.

## Adoption

I confirm that this plan describes the incident-response procedure this organization will actually follow.

**Name:** ______________________________  
**Signature/approval:** ______________________________  
**Date:** ______________________________
