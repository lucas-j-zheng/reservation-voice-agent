# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Voice agent application that enables users to make restaurant reservations and check current wait times via phone calls, eliminating the need for manual interaction.

---

## MVP Definition

**Goal:** A single-user system that can place one outbound call, identify as AI, negotiate a 2-turn reservation, and save the result to a database.

**Success Metric:** A record in the reservations table with a `confirmation_code`.

**Constraint:** Use Gemini 2.5 Flash Native Audio via the Live API (GA 2026) for sub-800ms response times.

---

## Monorepo Structure

Polyglot Monorepo layout. Do not deviate from this directory structure even for the MVP.

```
/sam-monorepo
├── apps/
│   ├── voice-engine/        # [PYTHON/FastAPI] The core AI/Audio relay
│   │   ├── src/
│   │   │   ├── brain/       # Gemini Live API & Prompting
│   │   │   ├── stream/      # Twilio WebSocket & Audio Transcoding
│   │   │   └── tools/       # Function Calling (MVP: save_booking)
│   │   └── main.py          # Entry point
│   └── dashboard/           # [TS/Next.js] The user control panel
│       ├── src/app/         # Next.js 15 App Router
│       └── src/components/  # Live call monitors (MVP: placeholder)
├── libs/
│   ├── api-contracts/       # [SHARED] Zod/Pydantic schemas for data safety
│   └── audio-utils/         # [PYTHON] Low-level PCM/mulaw math
├── infrastructure/          # [DEVOPS]
│   ├── docker/              # Local Redis/Postgres containers
│   └── terraform/           # (Placeholder for future GCP/Railway deploy)
├── .env.example
└── README.md
```

---

## Tech Stack

| Component     | Technology                              |
|---------------|----------------------------------------|
| Orchestration | Python 3.12+ (FastAPI)                 |
| AI            | gemini-2.5-flash-native-audio (Live API) |
| Telephony     | Twilio Voice (WebSockets / Media Streams) |
| Database      | Supabase (PostgreSQL)                  |
| Real-time     | Redis (Required for low-latency barge-in handling) |

---

## Live Data Flow (MVP Logic)

1. **Ingress:** Twilio forks 8kHz μ-law audio to `apps/voice-engine`
2. **Transcode:** `libs/audio-utils` converts to 16kHz LPCM16 (Gemini's native format)
3. **Brain:** `apps/voice-engine/src/brain` streams audio to Gemini
4. **Barge-in:** If Twilio sends a start event while the AI is speaking, the voice-engine clears the outbound audio buffer instantly
5. **Completion:** Upon hearing a confirmation, Gemini triggers `tools/save_booking.py`

---

## Database Schema

Keep the data model simple but compliant with the `api-contracts` lib.

```sql
-- Table: Calls (Audit Log)
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twilio_sid TEXT UNIQUE,
    status TEXT, -- 'ongoing', 'completed', 'failed'
    transcript_summary TEXT
);

-- Table: Reservations (The Result)
CREATE TABLE reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    restaurant_name TEXT,
    party_size INT,
    confirmed_time TIMESTAMPTZ,
    confirmation_code TEXT
);
```

---

## MVP Implementation Constraints (Strict)

- **Native Audio Only:** Do not use `google-cloud-text-to-speech`. Use the Gemini Live API's `response_modality: AUDIO` to ensure the voice sounds human and responsive.

- **AI Disclosure:** The agent must start with: *"Hello, I'm Sam, an AI assistant calling to book a table for [User]."*

- **Local Dev:** Use a Cloudflare Tunnel to bridge Twilio to your local machine.

- **No Auth (Yet):** Hardcode a single `USER_ID` in the `.env` for the MVP.

---

## Development Commands

### Infrastructure (Local)

```bash
# Start local Postgres and Redis
docker compose -f infrastructure/docker/docker-compose.yml up -d

# Stop local infrastructure
docker compose -f infrastructure/docker/docker-compose.yml down
```

### Voice Engine (Python)

```bash
cd apps/voice-engine

# Install dependencies (creates .venv automatically)
uv sync

# Run the server
uv run python main.py
# or with uvicorn for hot reload:
uv run uvicorn main:app --reload --port 8000
```

### Dashboard (Next.js)

```bash
cd apps/dashboard

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### Local Tunnel (for Twilio)

```bash
# Expose voice-engine to Twilio via Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```
