# VORAK — Security Notes

**Status: Guidance for an in-progress project.** This document describes security requirements to implement and verify; it is not a certification or claim that every control is already present.

## Secrets and repository hygiene

- Keep API keys, access tokens, passwords, cookies, private keys and personal data out of source control.
- Use environment variables or an appropriate secret manager. Commit only placeholder variable names in `.env.example`.
- Ensure local secret files are covered by `.gitignore`.
- Before publishing, inspect the current files and the complete Git history for secrets. Rotate any credential that has ever been exposed.

## Tool execution

- Treat model-generated plans and arguments as untrusted.
- Route every action-capable tool through a policy/permission check.
- Prefer narrow allowlisted operations over unrestricted shell, filesystem or browser access.
- Require explicit approval for destructive, external, financial, account-changing or otherwise consequential actions.
- Enforce timeouts, cancellation, argument validation and safe retry rules.

## Screen, files and privacy

- Request screen or file access only when required for the current task.
- Explain what data is accessed and for what purpose.
- Minimize retention; redact secrets and sensitive content from logs.
- Do not capture or transmit screen content continuously without a clear user-controlled reason and consent.

## Prompt injection and untrusted content

Web pages, documents, code comments, terminal output and screen content may contain malicious instructions. Treat them as data, not authority. They must not override system policy, reveal secrets or grant additional tool permissions.

## Before a public release

- [ ] Scan tracked files for credentials and private data.
- [ ] Review commit history for previously committed secrets.
- [ ] Rotate exposed credentials; history rewriting alone is not sufficient.
- [ ] Confirm `.gitignore` excludes local environment files and generated sensitive data.
- [ ] Verify tool permissions and approval requirements.
- [ ] Add tests for permission bypass, prompt injection and unsafe retries.
- [ ] Document known limitations and supported security controls honestly.

These notes are a starting checklist, not a substitute for a security review.