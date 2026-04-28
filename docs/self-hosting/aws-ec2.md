# AWS EC2 Deployment

Deploy Observal on a single EC2 instance using Docker Compose. This guide covers instance sizing, security groups, storage, and optional HTTPS.

## Instance sizing

| Workload | Instance type | vCPUs | RAM | Notes |
| --- | --- | --- | --- | --- |
| Development / small team (< 10 users) | `t3.medium` | 2 | 4 GB | Minimum viable. ClickHouse may swap under heavy trace load. |
| Production (10-50 users) | `t3.large` | 2 | 8 GB | Recommended. Comfortable headroom for all ten services. |
| Production (50+ users, high trace volume) | `m6i.xlarge` | 4 | 16 GB | If you run the eval engine frequently or ingest > 100k spans/day. |

Use **Amazon Linux 2023** or **Ubuntu 22.04 LTS** as the AMI. Both have straightforward Docker install paths.

## Security groups

Create a security group with these inbound rules:

| Port | Protocol | Source | Purpose |
| --- | --- | --- | --- |
| 22 | TCP | Your IP / VPN CIDR | SSH access |
| 8000 | TCP | Your IP / VPN CIDR | Observal API (FastAPI + OTLP ingestion) |
| 3000 | TCP | Your IP / VPN CIDR | Observal web dashboard (Next.js) |
| 443 | TCP | 0.0.0.0/0 | HTTPS (optional, if using ALB or Let's Encrypt) |

Do **not** expose ports 5432 (Postgres), 8123 (ClickHouse), or 6379 (Redis) to the internet. They listen on the Docker bridge network and are not needed externally.

## EBS volume

ClickHouse stores all trace and span data on disk. Size the root or data volume accordingly:

| Workload | Volume type | Size | IOPS |
| --- | --- | --- | --- |
| Development | gp3 | 50 GB | 3,000 (default) |
| Production | gp3 | 100 GB+ | 3,000-6,000 |

gp3 is cheaper per GB than gp2 and lets you provision IOPS independently. If you expect sustained high write throughput (> 200k spans/day), bump IOPS to 6,000.

Mount the volume at `/data` or use the default root volume. Docker named volumes (`chdata`, `pgdata`, etc.) will live under `/var/lib/docker/volumes/` by default. To use a dedicated mount point, configure Docker's `data-root` or use bind mounts in `docker-compose.yml`.

## Step-by-step deployment

### 1. Launch the instance

Launch an EC2 instance with the sizing and security group above. Attach an SSH key pair.

### 2. SSH in

```bash
ssh -i /path/to/key.pem ec2-user@<public-ip>    # Amazon Linux
ssh -i /path/to/key.pem ubuntu@<public-ip>       # Ubuntu
```

### 3. Install Docker and Docker Compose

**Amazon Linux 2023:**

```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER

# Docker Compose plugin
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Re-login for group membership
exit
```

SSH back in, then verify:

```bash
docker version
docker compose version
```

**Ubuntu 22.04:**

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
exit
```

SSH back in, then verify with `docker version` and `docker compose version`.

### 4. Clone the repo

```bash
git clone https://github.com/BlazeUp-AI/Observal.git
cd Observal
```

### 5. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and change at minimum:

| Variable | What to set |
| --- | --- |
| `SECRET_KEY` | Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `POSTGRES_PASSWORD` | A strong random password |
| `CLICKHOUSE_PASSWORD` | A strong random password |
| `CORS_ALLOWED_ORIGINS` | `http://<public-ip>:3000` (or your domain) |
| `NEXT_PUBLIC_API_URL` | `http://<public-ip>:8000` |

Remove the `DEMO_*` variables if you do not want seeded demo accounts.

See [Configuration](configuration.md) and [Environment variables](../reference/environment-variables.md) for the full list.

### 6. Start Observal

```bash
docker compose -f docker/docker-compose.yml up -d
```

Wait 30-60 seconds for health checks. Confirm all services are running:

```bash
docker compose -f docker/docker-compose.yml ps
curl http://localhost:8000/health
# {"status": "ok"}
```

### 7. Access the dashboard

Open `http://<public-ip>:3000` in your browser.

If you kept the demo accounts, log in with `super@demo.example` / `super-changeme`. Otherwise, the first `observal auth login` from the CLI bootstraps an admin account.

### 8. Install the CLI locally and connect

On your local machine:

```bash
curl -fsSL https://raw.githubusercontent.com/BlazeUp-AI/Observal/main/install.sh | bash
observal auth login --server http://<public-ip>:8000
```

Then instrument your IDEs:

```bash
observal doctor patch --all --all-ides
```

## IAM roles (optional)

If you build custom Docker images and push them to Amazon ECR, attach an IAM instance profile with `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, and `ecr:GetDownloadUrlForLayer` permissions. The default deployment pulls public images from Docker Hub and GitHub Container Registry, so no IAM role is required for a standard install.

## HTTPS (optional)

Two common approaches:

### Option A: Application Load Balancer

1. Create an ALB in the same VPC.
2. Request an ACM certificate for your domain.
3. Create two target groups: one for port 3000 (dashboard), one for port 8000 (API).
4. Add HTTPS:443 listeners with rules routing by hostname or path to the target groups.
5. Update your security group to allow traffic from the ALB's security group on ports 3000 and 8000.
6. Update `CORS_ALLOWED_ORIGINS` and `NEXT_PUBLIC_API_URL` to use `https://`.

### Option B: Let's Encrypt with Caddy

Install Caddy as a reverse proxy on the instance:

```bash
sudo dnf install -y caddy   # Amazon Linux
# or: sudo apt-get install -y caddy   # Ubuntu
```

Create `/etc/caddy/Caddyfile`:

```
observal.example.com {
    handle /api/* {
        reverse_proxy localhost:8000
    }
    handle {
        reverse_proxy localhost:3000
    }
}
```

```bash
sudo systemctl enable caddy && sudo systemctl start caddy
```

Caddy auto-provisions and renews Let's Encrypt certificates. Point your DNS A record at the instance's public IP and ensure port 443 is open in the security group.

Update `.env`:

| Variable | Value |
| --- | --- |
| `CORS_ALLOWED_ORIGINS` | `https://observal.example.com` |
| `NEXT_PUBLIC_API_URL` | `https://observal.example.com` |

## Maintenance

### Upgrades

```bash
cd Observal
git pull
docker compose -f docker/docker-compose.yml up -d --build
```

See [Upgrades](upgrades.md) for migration steps between versions.

### Backups

Back up Postgres and ClickHouse volumes regularly. See [Backup and restore](backup-and-restore.md).

### Monitoring

`docker compose -f docker/docker-compose.yml logs -f` streams all container logs. Grafana is available at `http://<public-ip>:3001` for ClickHouse dashboards.

## Related

* [Docker Compose setup](docker-compose.md)
* [Configuration](configuration.md)
* [Requirements](requirements.md)
* [Troubleshooting](troubleshooting.md)