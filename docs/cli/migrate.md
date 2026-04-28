# observal migrate

PostgreSQL shallow-copy migration tools. Export, import, and validate registry data and telemetry between Observal instances.

## Subcommands

| Command | Description |
| --- | --- |
| [`migrate export`](#observal-migrate-export) | Export all PostgreSQL registry data to a portable archive |
| [`migrate import`](#observal-migrate-import) | Import a migration archive into the target database |
| [`migrate validate`](#observal-migrate-validate) | Validate archive integrity and optionally compare against a database |
| [`migrate export-telemetry`](#observal-migrate-export-telemetry) | Export ClickHouse telemetry data to Parquet files |
| [`migrate import-telemetry`](#observal-migrate-import-telemetry) | Import Parquet telemetry files into target ClickHouse |
| [`migrate validate-telemetry`](#observal-migrate-validate-telemetry) | Validate telemetry Parquet files and optionally check FK references |

---

## `observal migrate export`

Export all PostgreSQL registry data to a portable archive.

### Options

| Option | Required | Description |
| --- | --- | --- |
| `--db-url TEXT` | Yes | Source PostgreSQL connection string |
| `--output, -o TEXT` | No | Output archive path (default: auto-generated) |

### Example

```bash
observal migrate export --db-url "postgresql://user:pass@localhost:5432/observal" -o backup.tar.gz
```

---

## `observal migrate import`

Import a migration archive into the target database.

### Options

| Option | Required | Description |
| --- | --- | --- |
| `--db-url TEXT` | Yes | Target PostgreSQL connection string |
| `--archive, -a TEXT` | Yes | Path to `.tar.gz` archive |

### Example

```bash
observal migrate import --db-url "postgresql://user:pass@newhost:5432/observal" --archive backup.tar.gz
```

---

## `observal migrate validate`

Validate archive integrity and optionally compare against a database.

### Options

| Option | Required | Description |
| --- | --- | --- |
| `--archive, -a TEXT` | Yes | Path to `.tar.gz` archive |
| `--db-url TEXT` | No | Optional database for cross-validation |

### Example

```bash
observal migrate validate --archive backup.tar.gz
observal migrate validate --archive backup.tar.gz --db-url "postgresql://user:pass@localhost:5432/observal"
```

---

## `observal migrate export-telemetry`

Export ClickHouse telemetry data to Parquet files.

### Options

| Option | Required | Description |
| --- | --- | --- |
| `--clickhouse-url TEXT` | Yes | Source ClickHouse connection URL |
| `--manifest TEXT` | Yes | Path to write the export manifest |
| `--output-dir TEXT` | Yes | Directory to write Parquet files |

### Example

```bash
observal migrate export-telemetry \
  --clickhouse-url "http://localhost:8123" \
  --manifest manifest.json \
  --output-dir ./telemetry-export/
```

---

## `observal migrate import-telemetry`

Import Parquet telemetry files into target ClickHouse.

### Options

| Option | Required | Description |
| --- | --- | --- |
| `--clickhouse-url TEXT` | Yes | Target ClickHouse connection URL |
| `--input-dir TEXT` | Yes | Directory containing Parquet files |

### Example

```bash
observal migrate import-telemetry \
  --clickhouse-url "http://newhost:8123" \
  --input-dir ./telemetry-export/
```

---

## `observal migrate validate-telemetry`

Validate telemetry Parquet files and optionally check FK references.

### Options

| Option | Required | Description |
| --- | --- | --- |
| `--input-dir TEXT` | Yes | Directory containing Parquet files |
| `--clickhouse-url TEXT` | No | Target ClickHouse for row count comparison |
| `--target-db-url TEXT` | No | Target PostgreSQL for FK validation |

### Example

```bash
observal migrate validate-telemetry --input-dir ./telemetry-export/
observal migrate validate-telemetry --input-dir ./telemetry-export/ --clickhouse-url "http://localhost:8123"
```

## Related

* [Self-Hosting → Backup and restore](../self-hosting/backup-and-restore.md)
* [Self-Hosting → Upgrades](../self-hosting/upgrades.md)
