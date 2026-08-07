# RMS API

The integration API is versioned under `/api/v1/` and uses Django REST Framework token authentication. Use HTTPS for every request and never send tokens over plain HTTP.

## Authentication

Obtain a token:

```http
POST /api/v1/auth/login/
Content-Type: application/json

{"username":"integration-user","password":"password"}
```

Use the returned token:

```http
Authorization: Token <token>
```

Available authentication endpoints:

- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/logout/`
- `GET /api/v1/auth/me/`

Tokens expire after `DJANGO_API_TOKEN_TTL_SECONDS` (one hour by default) and are revoked on logout or a new login for the same account. Store them in the consuming system’s secret store, not source code or browser storage.

## Resources

- `GET, POST /api/v1/records/`
- `GET, PUT, PATCH, DELETE /api/v1/records/{id}/`
- `POST /api/v1/records/{id}/attachments/`
- `GET, POST /api/v1/assets/`
- `GET, PATCH, DELETE /api/v1/assets/{id}/`
- `GET /api/v1/categories/`
- `GET /api/v1/record-types/`
- `GET /api/v1/users/` (administrators only)

Responses are JSON. Record and asset operations reuse RMS role and category authorization. Unauthorized objects return a safe `404` response where appropriate.

## Security requirements

- Use a dedicated integration account with the minimum RMS role required.
- Use separate tokens for each consuming system and rotate/revoke them regularly.
- Set `DJANGO_API_TOKEN_TTL_SECONDS` to match the organization’s integration policy; shorter lifetimes reduce exposure.
- Keep integration accounts non-administrative unless an endpoint explicitly requires administration.
- Configure Redis-backed throttling in production.
- Validate integration behavior against the UAT checklist before granting production access.
