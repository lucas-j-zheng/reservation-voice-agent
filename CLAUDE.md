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

```
Phone → Twilio (8kHz μ-law) → transcode → Gemini (16kHz PCM)
                                              ↓
Phone ← Twilio (8kHz μ-law) ← transcode ← Gemini (24kHz PCM)
```

1. **Ingress:** Twilio forks 8kHz μ-law audio to `apps/voice-engine`
2. **Transcode In:** `libs/audio-utils` converts 8kHz μ-law → 16kHz LPCM16 (Gemini input format)
3. **Brain:** `apps/voice-engine/src/brain` streams audio to Gemini Live API
4. **Transcode Out:** Gemini responds with 24kHz LPCM16 → converted to 8kHz μ-law for Twilio
5. **Barge-in:** If user speaks while AI is talking, voice-engine clears outbound queue and interrupts Gemini
6. **Completion:** Upon hearing a confirmation, Gemini triggers `tools/save_booking.py`

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

# Run tests
uv run pytest tests/ -v
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

---

## Environment Variables

```bash
# Required - AI
GEMINI_API_KEY=              # Google AI API key for Gemini Live API

# Required - Telephony
TWILIO_ACCOUNT_SID=          # Twilio account identifier
TWILIO_AUTH_TOKEN=           # Twilio auth token
TWILIO_PHONE_NUMBER=         # Twilio phone number for outbound calls

# Required - Database
SUPABASE_URL=                # Supabase project URL
SUPABASE_SERVICE_KEY=        # Supabase service role key (server-side only)

# Optional
DATABASE_URL=                # Direct PostgreSQL connection (overrides Supabase)
REDIS_URL=                   # Redis connection (defaults to redis://localhost:6379)
```

---

## Error Handling

- Always include `call_id` in logs for traceability
- Wrap DB operations in try/except; on failure update call status to `failed`
- Never leave calls in `ongoing` status after handler exits
- Handle malformed JSON and unknown Twilio events gracefully (log and skip)

---

## Implementation Notes

### Gemini Model Version
Uses `gemini-2.5-flash-native-audio-preview-09-2025` (NOT the latest -12-2025 version) due to a policy violation bug causing WebSocket error 1008. See: https://discuss.ai.google.dev/t/114644

### Barge-in Handling
Gemini's automatic voice activity detection handles barge-in. The handler clears the outbound audio queue when user speaks - no explicit ActivityStart signal needed.

### Session Lifecycle
- `receive_audio()` is a continuous async generator - each `session.receive()` returns one turn
- After `turn_complete`, must call `receive()` again for next turn
- Session stored in `_session_context` for proper cleanup via `__aexit__`
