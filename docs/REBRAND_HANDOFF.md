# Smart Ward Hub — Rebrand Handoff

## Principle

Branding is presentation metadata, not a trust, authorization, audit or clinical-safety control. A brand change must not alter API semantics, security scopes, patient-data boundaries, evidence claims, database schema or migration behavior.

## Current abstraction

Product name, short name and description are read from `SW_PRODUCT_NAME`, `SW_PRODUCT_SHORT_NAME` and `SW_PRODUCT_DESCRIPTION`. The FastAPI title/description and `/health` system label use these settings. Defaults preserve the current product identity until the brand decision is approved.

## Rebrand steps

1. Approve the new name, product descriptor, domain and trademark review.
2. Update the three environment values in the deployment template and approved runtime configuration.
3. Update UI/static assets and user-facing documentation through a separate commit.
4. Search for old product names in source, docs, OpenAPI snapshots, runbooks, examples and screenshots.
5. Confirm package/import/repository identifiers remain unchanged unless a migration plan exists.
6. Run security, privacy, functional, freeze and redaction tests.
7. Regenerate release notes and evidence manifest only after the final text/assets are approved.
8. Publish a versioned migration/release note explaining the identity change.

## Acceptance criteria

The new brand appears consistently in approved user-facing surfaces; no old or unapproved name remains in customer-facing artifacts; no secrets or patient identifiers are introduced; API routes, scopes, audit schemas and evidence claim boundaries are unchanged; and the full regression suite passes.

## Not allowed during rebrand

Do not rename security scopes, opaque identifiers, database tables, evidence IDs or API routes merely to match a new brand. Do not claim that a brand change represents new clinical validation, regulatory approval, security certification or product capability.
