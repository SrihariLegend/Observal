# Quickstart

Go from zero to "my first trace in the Observal dashboard" in about five minutes. This assumes you have Docker running.

By the end of this guide you will have:

* The Observal CLI installed
* An Observal server running locally
* The CLI logged in as an admin
* An agent created, published, and pulled into your IDE
* A live trace visible in the web UI

## 1. Install the CLI

```bash
curl -fsSL https://raw.githubusercontent.com/BlazeUp-AI/Observal/main/install.sh | bash
```

No Python required. For alternative install methods, see [Installation](installation.md).

> [!NOTE]
> You need Docker Engine ≥ 24.0 with Compose v2 (`docker compose`, not `docker-compose`). Homebrew's Docker formula is outdated — install [Docker Desktop](https://docs.docker.com/get-docker/) or use your distro's upstream packages. Verify with `docker version` and `docker compose version`.

## 2. Start the server

```bash
git clone https://github.com/BlazeUp-AI/Observal.git
cd Observal
cp .env.example .env

docker compose -f docker/docker-compose.yml up --build -d
```

That's it. The `.env.example` ships with working defaults. Ten services come up:

| Service | URL |
| --- | --- |
| Init (migrations) | exits after setup |
| API (FastAPI + OTLP ingestion) | `http://localhost:8000` |
| Web UI (Next.js) | `http://localhost:3000` |
| Postgres | `localhost:5432` |
| ClickHouse | `localhost:8123` |
| Redis | `localhost:6379` |
| Worker (arq) | internal |
| Load Balancer (nginx) | internal |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3001` |

The API waits for Postgres, ClickHouse, and Redis to pass health checks before starting — expect 15–30 seconds. Confirm it is up:

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

Hitting a port conflict? See [Self-Hosting → Ports and volumes](../self-hosting/ports-and-volumes.md).

## 3. Log in

```bash
observal auth login
```

Prompts:

1. **Server URL** — press Enter for `http://localhost:8000`
2. **Login method** — pick `[E]mail`
3. **Email / password** — use one of the seeded demo accounts:

| Role | Email | Password |
| --- | --- | --- |
| Super Admin | `super@demo.example` | `super-changeme` |
| Admin | `admin@demo.example` | `admin-changeme` |
| Reviewer | `reviewer@demo.example` | `reviewer-changeme` |
| User | `user@demo.example` | `user-changeme` |

Log in as super admin for the fewest restrictions while exploring. Credentials land in `~/.observal/config.json` (mode `0600`).

Check it worked:

```bash
observal auth whoami
# → super@demo.example (super_admin)
```

## 4. Create and publish an agent

Create an agent using the interactive wizard:

```bash
observal agent create
```

The wizard prompts for a name, description, and which MCP servers / skills / hooks to bundle. Give it a name like `my-first-agent` and include at least one MCP server.

Alternatively, use the YAML workflow:

```bash
observal agent init                        # scaffold observal-agent.yaml
observal agent add mcp <mcp-name>          # add a component
observal agent build                       # validate against the server
observal agent publish                     # submit to the registry
```

Verify it appears in the registry:

```bash
observal agent list
```

## 5. Pull the agent into your IDE

Install the agent you just published:

```bash
observal pull my-first-agent --ide claude-code
```

This drops agent files, skills, hooks, and MCP configs into the right places for your IDE and wires up telemetry automatically.

If you have other MCP servers already configured that are not part of an agent, instrument them too:

```bash
observal doctor patch --all --all-ides
```

Preview what will change first (no files modified):

```bash
observal doctor patch --all --all-ides --dry-run
```

Expected output:

```
Patching Claude Code...
  ✓ filesystem        wrapped  (was: npx @modelcontextprotocol/server-filesystem)
  ✓ github            wrapped  (was: npx @modelcontextprotocol/server-github)
  ✓ Telemetry hooks installed

Patching Kiro...
  ✓ mcp-obsidian      wrapped
  ✓ Telemetry hooks installed

Backups saved:
  ~/.claude/settings.json.20260421_143055.bak
  .kiro/settings/mcp.json.20260421_143055.bak

3 server(s) instrumented, hooks installed across 2 IDE(s).
```

Verify the instrumentation is healthy:

```bash
observal doctor --ide claude-code
```

Restart your IDE to pick up the new config.

## 6. See your first trace

Trigger anything in your IDE that uses an MCP tool (ask Claude to list files, read a GitHub issue, whatever). Open `http://localhost:3000/traces` in your browser and refresh -- you will see the trace appear.

Or use the CLI:

```bash
observal ops traces --limit 5
```

Drill into a trace:

```bash
observal ops spans <trace-id>
```

## What you just built

```
Your IDE  <-->  observal-shim  <-->  MCP server
                      │
                      ▼  (fire-and-forget)
               Observal API  ──►  ClickHouse  ──►  Web UI, eval engine
```

Every MCP request/response is now a span. Spans group into traces. Traces form sessions. The eval engine can score any session.

## Where to next

| You want to... | Go to |
| --- | --- |
| Understand the data model | [Core Concepts](core-concepts.md) |
| Learn what to do with traces | [Use Cases](../use-cases/README.md) |
| Configure the server for production | [Self-Hosting](../self-hosting/README.md) |
| Deep-dive on a CLI command | [CLI Reference](../cli/README.md) |
