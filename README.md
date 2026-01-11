# reservation-voice-agent

Voice agent to call restaurants. Allows people to make reservations & check current wait time without any manual interaction.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for local Postgres & Redis)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Node.js 20+](https://nodejs.org/) (for dashboard)
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) (for local Twilio integration)

## Quick Start

### 1. Start Infrastructure

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

### 2. Run Voice Engine

```bash
cd apps/voice-engine
uv sync
uv run uvicorn main:app --reload --port 8000
```

### 3. Run Dashboard

```bash
cd apps/dashboard
npm install
npm run dev
```

### 4. Expose to Twilio

```bash
cloudflared tunnel --url http://localhost:8000
```

## Project Structure

```
├── apps/
│   ├── voice-engine/    # Python/FastAPI - AI voice processing
│   └── dashboard/       # Next.js - User control panel
├── libs/
│   ├── api-contracts/   # Shared Zod/Pydantic schemas
│   └── audio-utils/     # Audio transcoding utilities
└── infrastructure/
    ├── docker/          # Local dev containers
    └── terraform/       # Cloud deployment (placeholder)
```

See [CLAUDE.md](./CLAUDE.md) for detailed architecture and development guidelines.
