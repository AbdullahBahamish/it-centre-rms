# User Acceptance Testing

Complete this checklist with IT Centre representatives before production launch. Record the tester, date, result, and any issue reference for every item.

## Accounts and authority

- An administrator can create, activate, deactivate, and assign only lower-ranked users.
- A manager, staff member, and viewer see only actions allowed by their assigned role.
- A user cannot assign themselves a privileged role or modify an equal/higher-ranked account.
- Password-reset email is delivered through the university SMTP service and expires as configured.

## Records and files

- Authorized users can create, update, archive, search, and download records.
- Restricted categories are invisible or inaccessible to unauthorized users.
- Attachment upload rejects invalid file types, forged content, and oversize files.
- Generated PDFs include the expected record data and remain downloadable only by authorized users.

## Operations and recovery

- The application is reachable through the approved internal DNS name over HTTPS.
- Scheduled backups include PostgreSQL data and the `media/` directory.
- A restore is performed into a non-production environment and verified with a sample record and attachment.
- IT Centre management signs off on retention policy, backup owner, restore owner, and administrator ownership.
