# SUSE PagerDuty SRE Agent Demo - Log Generator

A Python-based log generator that creates realistic SUSE RMT (Repository Mirroring Tool) logs and sends them to an existing Loki instance. Designed to trigger FATAL and HTTP 500 error alerts in Grafana for PagerDuty SRE Agent testing.

## Overview

This tool generates structured logs for multiple RMT services across different cloud providers (GCP, AWS, Azure) and sends them to Loki via HTTP API. The logs trigger Grafana alerts when error thresholds are exceeded (>= 5 errors in 10 minutes).

## Architecture

```
┌─────────────────────┐
│  This Machine       │
│  log_generator.py   │ → Generates FATAL/500 error logs
└──────────┬──────────┘
           │
           ↓ (HTTP POST to Loki API)
┌─────────────────────┐
│  Grafana/Loki       │ ← Stores logs, triggers alerts
└──────────┬──────────┘
           │
           ↓ (sends alert via routing key)
┌─────────────────────┐
│  PagerDuty          │ ← Receives alert, SRE Agent queries back
└─────────────────────┘
```

## Prerequisites

### Required
- Python 3.8+
- Network access to Loki instance
- Loki URL (e.g., `http://localhost:3100`)

### Optional (for local testing)
- Docker & Docker Compose (to run your own Loki instance)

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/suse-pagerduty-demo.git
cd suse-pagerduty-demo
```

### 2. Install Dependencies (Optional)

**Check if already installed:**
```bash
python3 -c "import requests, yaml; print('✅ Dependencies already installed')"
```

**If needed:**
```bash
pip install -r requirements.txt
```

### 3. Configure Loki URL

**Option A: Using .env file (recommended)**
```bash
cp .env.example .env
# Edit .env and set your Loki URL
```

**Option B: Using environment variable**
```bash
export LOKI_URL=http://your-loki-instance:3100
```

**Option C: Edit config file directly**
Edit `config/services.yaml` and change the Loki URL.

### 4. Test Connection

```bash
curl http://your-loki-instance:3100/ready
```

### 5. Generate Logs

```bash
# Generate normal traffic for 10 minutes
python log_generator.py --duration 10 --verbose

# Trigger FATAL alert (6 errors)
python log_generator.py --burst-errors 6 --error-type FATAL

# Trigger HTTP 500 alert
python log_generator.py --burst-errors 6 --error-type ERROR

# Run continuously
python log_generator.py --verbose
```

## Usage

### Command Line Options

```bash
python log_generator.py [OPTIONS]
```

| Option | Description | Example |
|--------|-------------|---------|
| `--config PATH` | Path to config file | `--config config/services.yaml` |
| `--duration MINUTES` | Run for specified minutes | `--duration 30` |
| `--burst-errors COUNT` | Generate burst of errors | `--burst-errors 6` |
| `--error-type TYPE` | Error type (FATAL or ERROR) | `--error-type FATAL` |
| `--verbose` or `-v` | Show each log | `--verbose` |

### Examples

```bash
# Normal traffic for 30 minutes
python log_generator.py --duration 30 --verbose

# Trigger FATAL alert
python log_generator.py --burst-errors 6 --error-type FATAL

# Trigger HTTP 500 alert
python log_generator.py --burst-errors 6 --error-type ERROR

# Continuous generation
python log_generator.py --verbose
```

## Configuration

### Service Configuration (`config/services.yaml`)

Customize RMT services, instances, and log patterns:

```yaml
loki:
  url: "${LOKI_URL:-http://localhost:3100}"

services:
  rmt-registration:
    enabled: true
    rate_per_minute: 20
    instances:
      - "rmt-gce-1-us-east4-b"
      - "rmt-ec2-1-me-central-1c"
    log_patterns:
      - level: "FATAL"
        weight: 5
        templates:
          - "Database connection pool exhausted"
```

### Configuration Options

- **enabled:** Enable/disable service
- **rate_per_minute:** Logs per minute
- **instances:** Instance names
- **log_patterns:**
  - **level:** FATAL, ERROR, WARN, INFO
  - **weight:** Relative frequency
  - **templates:** Log message templates
  - **attributes:** Dynamic values

## Included Services

### rmt-registration
- Customer registration service
- Instances: GCP, AWS, Azure
- Rate: 20 logs/minute

### rmt-api
- API endpoints
- Instances: GCP, AWS, Azure
- Rate: 30 logs/minute

### rmt-sync
- Repository synchronization
- Instances: GCP, AWS
- Rate: 15 logs/minute

### rmt-auth
- Authentication service
- Instances: GCP, Azure
- Rate: 25 logs/minute

## Log Format

Logs are sent to Loki with labels:
- `job`: "rmt-servers"
- `level`: FATAL, ERROR, WARN, INFO
- `service`: Service name
- `instance`: Instance name

### Example Loki Queries

```logql
# All FATAL errors
{level="FATAL"}

# HTTP 500 errors
{level="ERROR"} |= "HTTP 500"

# Count FATAL errors in 10 minutes (for alerts)
count_over_time({level="FATAL"}[10m])

# Count HTTP 500 errors in 10 minutes (for alerts)
count_over_time({level="ERROR"} |= "HTTP 500" [10m])
```

## Grafana Alert Configuration

### FATAL Error Alert
- **Query:** `count_over_time({level="FATAL"}[10m])`
- **Condition:** `>= 5`
- **Evaluate every:** `1m`

### HTTP 500 Error Alert
- **Query:** `count_over_time({level="ERROR"} |= "HTTP 500" [10m])`
- **Condition:** `>= 5`
- **Evaluate every:** `1m`

## Troubleshooting

### Logs not appearing

```bash
# Check Loki is reachable
curl http://your-loki:3100/ready

# Query recent logs
curl -G -s "http://your-loki:3100/loki/api/v1/query" \
  --data-urlencode 'query={job="rmt-servers"}' | jq

# Verify LOKI_URL
echo $LOKI_URL
```

### Connection errors

- Verify Loki is running
- Check firewall rules (port 3100)
- Test network: `ping your-loki-host`

### Dependencies missing

```bash
pip install requests pyyaml python-dotenv
```

## Optional: Local Loki Instance

To test locally:

```bash
# Start Loki
docker-compose up -d

# Verify
curl http://localhost:3100/ready

# Configure
export LOKI_URL=http://localhost:3100

# Stop
docker-compose down
```

## Customization

### Add New Service

Edit `config/services.yaml`:

```yaml
services:
  my-service:
    enabled: true
    rate_per_minute: 15
    instances:
      - "my-service-1"
    log_patterns:
      - level: "ERROR"
        weight: 10
        templates:
          - "Custom error: {code}"
        attributes:
          code: [500, 502, 503]
```

### Adjust Error Rates

Change `weight` values (higher = more frequent).

### Add Instances

Add to `instances` list for any service.

## Project Structure

```
suse-pagerduty-demo/
├── README.md
├── log_generator.py
├── config/
│   └── services.yaml
├── requirements.txt          # Optional
├── .env.example             # Optional
├── .gitignore
└── docker-compose.yml       # Optional
```

## License

MIT

## Support

nicolas.briceno@pagerduty.com
