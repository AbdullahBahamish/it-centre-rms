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
