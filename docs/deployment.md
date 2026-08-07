# University Local-Server Deployment

This guide deploys IT Centre RMS as an internal HTTPS service. Use a dedicated service account and keep the application, database, and backup storage under IT Centre control.

## Prerequisites

- Internal DNS name, for example `rms.university.local`, and an HTTPS certificate trusted by organization devices.
- PostgreSQL 16+ and Redis 7+ on the server or on managed internal hosts.
- Python 3.13, `pg_dump`, and a reverse proxy: Nginx on Linux or IIS on Windows.
- A service account with read/write access only to the application `media/` directory and backup destination.

## Application setup

1. Copy the repository to `/srv/it-centre-rms/app` (Linux) or `C:\it-centre-rms\app` (Windows). Do not copy development virtual environments, `.env`, SQLite databases, backups, or uploaded media into a new production installation.
2. Create a virtual environment and install requirements:

   ```bash
   python3.13 -m venv /srv/it-centre-rms/venv
   /srv/it-centre-rms/venv/bin/pip install -r requirements.txt
   ```

3. Create the PostgreSQL database and least-privilege application account:

   ```sql
   CREATE USER it_centre_rms WITH PASSWORD 'use-a-unique-secret';
   CREATE DATABASE it_centre_rms OWNER it_centre_rms;
   ```

4. Copy `.env.example` to a protected environment file, replace every placeholder, and restrict it to the service account. Linux uses `/etc/it-centre-rms/rms.env`; on Windows define the same values as system environment variables or protect `C:\it-centre-rms\app\.env`.
5. Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to the approved internal DNS name. Do not use public wildcard hosts.
6. Run deployment commands:

   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   python manage.py system_check_ready
   python manage.py check --deploy --fail-level WARNING
   ```

The first migration automatically creates the required roles and permissions. Create the first administrator through `createsuperuser`, then assign its RMS role through the application administration interface.

## Linux service

1. Place `deploy/systemd/it-centre-rms.service` at `/etc/systemd/system/it-centre-rms.service`.
2. Place `deploy/nginx/it-centre-rms.conf` in the Nginx site configuration, replace the sample DNS name and certificate paths, then validate with `nginx -t`.
3. Enable services:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now it-centre-rms nginx
   ```

Nginx serves collected static files. Record files remain protected and are downloaded through the application’s authorization checks; do not expose `media/` as a public directory.

## Windows Server service

1. Install the project and PostgreSQL/Redis service accounts under `C:\it-centre-rms`.
2. Use the command in `deploy/windows/start-waitress.ps1` to run Waitress on `127.0.0.1:8000`, managed by the university’s approved Windows service manager.
3. Configure IIS as the HTTPS endpoint with a binding for the internal DNS name, proxy application requests to `http://127.0.0.1:8000`, and map `/static/` to `C:\it-centre-rms\app\staticfiles`.
4. Do not create a public IIS virtual directory for `media/`; downloads must continue through Django authorization views.

## Backups, restore, and maintenance

- Schedule `scripts/backup-postgres.sh BACKUP_ROOT` on Linux or `scripts/backup-postgres.ps1 -BackupRoot BACKUP_ROOT` on Windows daily. Provide database variables through the scheduled job’s protected environment.
- Retain backups according to the university retention policy and copy encrypted backups to a separate internal storage location.
- Test restore quarterly in a non-production environment:

  ```bash
  pg_restore --clean --if-exists --dbname=it_centre_rms /path/to/database.dump
  tar -xzf /path/to/media.tar.gz -C /srv/it-centre-rms/app
  ```

- Run `python manage.py cleanup_orphan_files` only after a verified backup. It deletes unreferenced files from `MEDIA_ROOT`.

## Go-live checklist

1. CI is green and `check --deploy --fail-level WARNING` passes with production environment values.
2. HTTPS, SMTP password reset, backup, and restore have been verified.
3. Complete [user acceptance testing](user-acceptance-testing.md) with IT Centre representatives.
4. Document the named owners for application administration, database backups, restores, certificate renewal, and incident response.
