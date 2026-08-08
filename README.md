# IT Centre Record Management System

The IT Centre Record Management System (RMS) provides structured control over institutional records, contributor assignments, attachments, and administrative access.

## Overview

This application supports disciplined record administration for internal IT Centre operations. Records are classified, access-controlled, and traceable, with supporting files and contributor assignments managed within the same operational workflow.

## Core Capabilities

* **Record Classification**
  Records are organised by category and record type to support consistent retrieval and governance.

* **Contributor Assignment**
  Contributors are associated with records through controlled selection rules that preserve accountability.

* **Attachment Management**
  Supporting files are linked directly to their parent record to maintain operational context.

* **Administrative Access Control**
  Role-based permissions govern record actions, user administration, and role assignments.

## Design Principles

* Consistent terminology across records, roles, and administrative actions
* Explicit relationships between records, contributors, and attachments
* Controlled workflows instead of ad hoc data handling
* Clear operational boundaries for access and responsibility

## Operational Context

The system is intended for internal IT Centre use where records must be maintained with clear ownership, controlled access, and predictable administrative processes.

## Local Setup

1. Create a virtual environment and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set `DJANGO_SECRET_KEY`.

3. Apply migrations and run the development server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## Testing

Run the complete automated test suite with:

```bash
python manage.py test
```

The suite covers account security, role-based access controls, record workflows,
attachment validation and storage, system policy middleware, and core utilities.

## Deployment

For a university local-server installation with PostgreSQL, Redis, HTTPS, SMTP,
backups, and service configuration, follow [the deployment guide](docs/deployment.md).
Complete [user acceptance testing](docs/user-acceptance-testing.md) before go-live.
For administrator setup, follow [the admin setup guide](docs/admin-setup.md).
For a first administrator on Render Free, follow [the Render Free admin guide](docs/render-free-admin-setup.md).
For system integrations, see [the API guide](docs/api.md).
