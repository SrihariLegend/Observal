# observal auth

Authentication and account management.

## Subcommands

| Command | Description |
| --- | --- |
| [`auth login`](#observal-auth-login) | Log in to an Observal server (auto-creates admin on fresh server) |
| [`auth logout`](#observal-auth-logout) | Clear saved credentials |
| [`auth whoami`](#observal-auth-whoami) | Show the authenticated user |
| [`auth status`](#observal-auth-status) | Check server connectivity, health, and local telemetry buffer |
| [`auth change-password`](#observal-auth-change-password) | Change the password for the current user |
| [`auth set-username`](#observal-auth-set-username) | Change the display name for the current user |

---

## `observal auth login`

Log in to an Observal server. On a fresh server with no users, bootstraps an admin account with your email and password.

### Synopsis

```bash
observal auth login [--server URL] [--key KEY] [--email EMAIL] [--password PASSWORD] [--name NAME]
```

### Options

| Option | Description |
| --- | --- |
| `--server URL` | Override the server URL for this login |
| `--key KEY` | Log in with an API key instead of email/password |
| `--email EMAIL` | Skip the email prompt |
| `--password PASSWORD` | Skip the password prompt (pass via env var in CI) |
| `--name NAME` | Display name used when bootstrapping |

### Example

```bash
observal auth login
# Server URL [http://localhost:8000]: <Enter>
# Method: [E]mail / [K]ey: E
# Email: admin@demo.example
# Password: **************
# Logged in as admin@demo.example (super_admin)
```

Credentials are saved to `~/.observal/config.json` (mode `0600`).

---

## `observal auth logout`

Clears credentials from `~/.observal/config.json`. Does not delete aliases or the telemetry buffer.

```bash
observal auth logout
```

---

## `observal auth whoami`

Print the currently authenticated user.

```bash
observal auth whoami
# alice@example.com (user) — https://observal.your-company.internal
```

Exits non-zero if you're not logged in.

---

## `observal auth status`

Check server connectivity, health, and the local telemetry buffer.

```bash
observal auth status
# Server:   https://observal.your-company.internal — OK (200)
# Auth:     alice@example.com (user)
# Buffer:   0 pending events
# Health:   API ok, Postgres ok, ClickHouse ok, Redis ok
```

Useful as the first step when things aren't working.

---

## `observal auth change-password`

Change the password for the currently authenticated user. Prompts for the current password, then a new password.

### Synopsis

```bash
observal auth change-password
```

### Example

```bash
observal auth change-password
# Current password: **************
# New password: **************
# Password changed.
```

---

## `observal auth set-username`

Change the display name for the currently authenticated user.

### Synopsis

```bash
observal auth set-username <name>
```

### Example

```bash
observal auth set-username "Alice Smith"
# Display name updated to: Alice Smith
```

---

## Environment variables

| Variable | Purpose |
| --- | --- |
| `OBSERVAL_SERVER_URL` | Default server URL for login |
| `OBSERVAL_ACCESS_TOKEN` / `OBSERVAL_API_KEY` | Pre-authenticate without calling `login` (for CI) |
| `OBSERVAL_TIMEOUT` | Request timeout in seconds |

Full list: [Environment variables](../reference/environment-variables.md).

## Related

* [`observal config`](config.md) — where credentials live
* [Self-Hosting → Authentication and SSO](../self-hosting/authentication.md) — server-side auth setup
