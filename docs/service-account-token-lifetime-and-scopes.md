# Service account tokens: scopes and effective lifetime

Short guide applicable to all APIs in this project (ESV, OAuth clients, Journeys, SAML, etc.).

## Problem observed

- Token response shows `expires_in ≈ 899s` (~15 minutes)
- Some API calls start failing with 401/expired token around ~3 minutes

## Why this happens

- The service account wasn’t granted (or the request didn’t include) the required API scopes.
- Without the right scopes for the endpoints you call, tokens can behave as if they expire early even when `expires_in` is higher.

## Fix (applies globally)

- Include the exact scopes required by the APIs you are calling when requesting the token.
- Ensure the service account is permitted to request those scopes.
- Example: for ESV operations you typically need `fr:idc:esv:*` in the requested scopes.

Example (conceptual):

```
scope=fr:idc:esv:* <other-api-specific-scopes>
```

## Verify

1. Request a new token with the updated scopes
2. Confirm the response `expires_in` (e.g., 899)
3. Call your target APIs again after 3–5 minutes — they should still succeed up to the expected lifetime

## Best practices

- Request the minimal, correct scopes per API
- If behavior seems off, double‑check: requested scopes, allowed scopes for the client, and correct token endpoint/tenant

## Minimal scopes

- ESV (Environment Secrets & Variables)
  - Read-only: `fr:idc:esv:read`
  - Create/Update/Delete: `fr:idc:esv:update`
  - Restart service to inject changes: `fr:idc:esv:restart`
  - All ESV operations: `fr:idc:esv:*`
- AM APIs (`/am/*`): `fr:am:*`
- IDM APIs (`/openidm/*`): `fr:idm:*`
  - Note: docs state tokens with `fr:idm:*` also have ESV access, but this is deprecated. Don’t rely on it going forward.

## Official docs

- Service account scopes: https://docs.pingidentity.com/pingoneaic/latest/tenants/service-accounts.html#service-account-scopes
