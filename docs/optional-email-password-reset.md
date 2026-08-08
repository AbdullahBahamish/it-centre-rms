# Optional email password resets

The system uses administrator-approved password reset requests by default. This works without user email accounts or a paid service.

If the organisation later gives every user a working email address and has access to an SMTP server, it can switch to email reset links.

1. Obtain the SMTP host, port, username, password, sender address, and TLS requirement from the organisation's mail administrator.
2. In `.env`, uncomment and fill in the `DJANGO_EMAIL_*` values from `.env.example`.
3. Add `DJANGO_PASSWORD_RESET_METHOD=email` to `.env`.
4. Set `DJANGO_ALLOWED_HOSTS` to the public RMS hostname and enable HTTPS.
5. Restart the application and submit a password reset request using a test account.

Email reset links expire after one hour by default. Change this with `DJANGO_PASSWORD_RESET_TIMEOUT` only if required.

Do not use the console email backend in production: it prints reset links to the application logs rather than delivering them.

To return to the administrator-approved workflow, remove `DJANGO_PASSWORD_RESET_METHOD=email` or set it to `admin`, then restart the application.
