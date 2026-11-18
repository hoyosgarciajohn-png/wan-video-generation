# Studio email login — prepared November 18, 2026

John approved replacing the token screen with email/password access and password recovery, including deployment. No further release approval is needed for this change. Activation is blocked by missing mail credentials, not by a permission requirement.

## User experience

Both Director and classic Studio use email + password, show-password control, first-password setup, forgot-password and reset-password screens. Anonymous first visits do not show a misleading expired-session alert in Director. Password links use a URL fragment that is removed immediately, so credentials do not reach HTTP access logs. A password is never placed in browser local storage.

An operator-provisioned email maps to an existing owner ID. Public registration cannot claim an existing workspace. Existing project rows and media are not rewritten. Once an account password is set, the old token can no longer sign into that owner. Setting/resetting a password invalidates existing browser sessions for that owner.

## Implementation

- stdlib scrypt N=131072, r=8, p=1, random salt; 12–128-character passwords.
- HTTP-only Secure SameSite cookies, existing same-origin/JSON checks.
- Recovery credentials are random, stored hashed, valid 30 minutes and single-use. Issuing a new link revokes prior links. Restore removes recovery credentials.
- Login rate limit: existing 10 failures/minute/peer. Recovery/reset: 10 requests/hour/peer. Limits and sessions are process-local; account hashes are durable SQLite records.
- TLS SMTP on port 587 (STARTTLS) or 465; delivery exceptions do not expose provider diagnostics or secret values.
- The email config endpoint reports configuration only; successful SMTP submission and inbox delivery still require live verification.
- No change to rendering, API keys, GPUs or historical grants.

Security references: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html and https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html.

## Observed blocker

Read-only host probe run 44343693588 confirmed no mail-related controller environment variables and no sendmail. No project-specific Supabase Auth project exists in the connected primary account; unrelated applications were not changed. Connected Resend has verified sending domains for Open Tomorrow, SIMIES and Transformational Resonance, but no WAN/Studio-specific domain. No API key was created and no emails were sent.

Choose a sender/relay and provision its credentials privately. Never put credentials, personal email mappings or reset links in GitHub, build logs or chat. The verified owner email was identified through the connected account profile; it must be mapped privately to `john-hoyos`, not to a new workspace ID.

Required server environment (values are not included here):

- `WAN_SMTP_HOST`, `WAN_SMTP_PORT` (587 or 465), `WAN_SMTP_USER`, `WAN_SMTP_PASSWORD`, `WAN_MAIL_FROM`.
- `WAN_STUDIO_ACCOUNT_FILE`: readable only by root/service group, JSON mapping verified account email to existing owner ID.

After mail configuration and delivery verification, build the frontend and use `deployment/auth_release.py` with `WAN_AUTH_RELEASE_SHA` pinned to the exact reviewed main commit and the existing runner-only `WAN_HOST_SSH_KEY`. It calls `auth_install.py`, which checks predecessor hashes, mail/account configuration, inactive rendering, private backup, unchanged historical project rows and service health. This installer is not automatically triggered by this PR. Do not replay the old Director installer.

After deployment: use **First time? Set your password**. The owner sets a private password and verifies that the existing projects appear. Then verify one recovery link and download/access permissions in the owner's live session. No fictional account should be added to production.

## Current evidence

Automated checks use fictional accounts only. Backend tests cover ownership, durable credentials, wrong passwords, CSRF, rate limiting, token expiry/reuse, session revocation, mail errors and recovery removal on restore. UI tests cover existing edit/re-auth flows, disabled unavailable mail, reset confirmation and invalid credentials. Production login/recovery and final visual acceptance remain pending until mail is connected and the release is installed.

Validation completed: 254 Python tests (253 passed, one existing skip), 18 frontend model/API tests, 22 UI tests, shared-contract validation, TypeScript/Vite production build and diff whitespace check. The five account tests were rerun after adding legacy-token rejection coverage. No real-user password or email was used in these tests.
