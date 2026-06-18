# Security policy

## Secrets

- Never commit `.env`, `token_cache.json`, account numbers, app keys, app secrets, or bearer tokens.
- Use a separate key pair issued for KIS mock trading.
- If a key was pasted into chat, an issue, a commit, or a log, revoke and rotate it immediately.
- GitHub Codespaces users should store `GH_ACCOUNT`, `GH_APPKEY`, and `GH_APPSECRET` in Codespaces user secrets and grant access only to this repository.

## Mock-only boundary

The base URL is fixed to `https://openapivts.koreainvestment.com:29443`. The client rejects transaction IDs that are not mock IDs (`V...`) or the shared public price ID (`FHKST...`). Do not remove these guards.

## Records

`records/*.jsonl` is designed for assignment evidence and excludes credentials. Always review a generated record before pushing it. Detailed `logs/*.log` files remain untracked.
