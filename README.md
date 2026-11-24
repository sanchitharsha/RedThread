# Redthread

**Product safety recall investigation engine** — a hackathon prototype that takes an official recall notice, uses a browser agent to find potentially affected product listings on a shop website, and presents the findings through a live agent view, evidence graph, and exposure report.

> [!IMPORTANT]
> This is a **mini prototype** built for a hackathon. It is scoped to a **sandbox shop** and **US CPSC data only**.

> [!WARNING]
> **Redthread never says a product is safe.** The absence of a match means "No match found in checked sources" — it is not a safety determination. Always follow the official notice and remedy.

## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Copy .env.example to .env and fill in your keys
cp .env.example .env

# 3. Run with stubs (no real LLM or browser needed)
USE_STUBS=1 make demo

# Or just the backend:
USE_STUBS=1 python -m uvicorn backend.main:app --port 8000 --reload
```

## Architecture

```
┌────────────┐    ┌──────────────┐    ┌──────────────┐
│  Frontend   │◄──│   Backend    │───►│   Browser    │
│  (React)    │SSE│  (FastAPI)   │    │   Agent (M1) │
│  Port 5173  │   │  Port 8000   │    └──────┬───────┘
└────────────┘    └──────┬───────┘           │
                         │              ┌────▼────────┐
                    ┌────▼────────┐     │  Sandbox    │
                    │  Matching   │     │  Shop (M4)  │
                    │  Engine(M2) │     │  Port 8001  │
                    └─────────────┘     └─────────────┘
```

| Role | Owner | Packages |
|------|-------|----------|
| M1 — Browser Agent | Agent Lead | `agent/` |
| M2 — Matching | Matching Lead | `matching/` |
| M3 — Backend & Integration | Integration Lead | `contracts/`, `common/`, `backend/`, `scripts/` |
| M4 — Frontend & Sandbox | Frontend Lead | `frontend/`, `sandbox/` |

## Verdict Tiers

| Tier | Meaning |
|------|---------|
| CONFIRMED | Product identifiers match the recall, scope verified |
| LIKELY | Identifiers match but scope cannot be verified |
| RELATED | Partial match (brand only, name only, sibling model) |
| CONFLICT | Contradictory signals across sources |
| NO_MATCH | No match found in checked sources |
| UNRESOLVED | Could not be determined (blocked, extraction failed) |

There is **no "safe" tier**. "No match" is not a statement about product safety.

## Sponsor Prize Integrations

### 🎙️ ElevenLabs — Voice Narration Briefing
Redthread generates an executive audio briefing of every exposure report using **ElevenLabs Text-to-Speech**.
- **Endpoint**: `POST /api/investigations/{id}/narrate`
- **Frontend**: One-click "🎙️ Voice Briefing" button in the Exposure Report toolbar with real-time playback.
- **Graceful fallback**: When offline or if an API key is not configured, generates a structured briefing script preview.

### ☁️ AWS S3 — Investigation Evidence Archival
Completed investigation runs (events stream, knowledge graph, exposure report, verbatim quotes, and page captures) are packaged and securely archived into **Amazon S3**.
- **Endpoint**: `POST /api/investigations/{id}/archive`
- **Frontend**: "☁️ Archive to AWS" button displays archival manifests and S3 object keys.
- **Graceful fallback**: Generates a reproducible offline archival manifest if AWS credentials are not set.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `gemini` or `openai` | `gemini` |
| `LLM_MODEL` | Model name | `gemini-2.0-flash` |
| `GEMINI_API_KEY` | Gemini API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `USE_STUBS` | `1` to use stub data | `0` |
| `OFFLINE` | `1` to skip network calls | `0` |
| `SHOP_URL` | Sandbox shop URL | `http://localhost:8001` |
| `ALLOW_DOMAINS` | Comma-separated domain allowlist | `localhost` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key for voice narration | — |
| `ELEVENLABS_VOICE_ID` | Voice ID (defaults to Rachel) | `21m00Tcm4TlvDq8ikWAM` |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key for S3 archival | — |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key | — |
| `AWS_REGION` | AWS region | `us-east-1` |
| `S3_BUCKET` | AWS S3 bucket for artifact archival | — |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/investigations` | Start investigation |
| GET | `/api/investigations/{id}/events` | SSE event stream |
| GET | `/api/investigations/{id}/graph` | Evidence graph |
| GET | `/api/investigations/{id}/report` | Exposure report |
| GET | `/api/evidence/{id}` | Single evidence object |
| GET | `/api/investigations/{id}/export.json` | Full export |
| GET | `/api/replays` | List recorded runs |
| GET | `/api/health` | Health check |
| GET | `/api/sponsors/status` | Sponsor integrations status (ElevenLabs & AWS) |
| POST | `/api/investigations/{id}/narrate` | ElevenLabs report audio briefing |
| POST | `/api/investigations/{id}/archive` | AWS S3 investigation artifact archival |

## Make Targets

```bash
make install    # Install dependencies
make test       # Run pytest
make backend    # Start backend (port 8000)
make sandbox    # Start sandbox shop (port 8001)
make frontend   # Start frontend (port 5173)
make demo       # Start all three with USE_STUBS=1
make smoke      # Run smoke test
```

## Data Sources & Licences

- **CPSC Recall Data**: US Consumer Product Safety Commission — public domain. Data accessed via the CPSC public API.
- **LLM Processing**: Note that page text from visited sites is sent to the configured LLM provider (Gemini or OpenAI) for field extraction. No data is stored by the LLM provider beyond the API call.

## Disclaimer

Redthread reports what was matched in the sources it checked. "No match found in checked sources" is not a statement about product safety. Always follow the official notice and remedy.

## Honest Limits

- **Sandbox shop only**: The prototype runs against a fixed local shop with known listings. It is not designed for production use against arbitrary websites.
- **US CPSC data only**: Only US Consumer Product Safety Commission recalls are supported.
- **Mini prototype**: Built in a hackathon. Not production-hardened.
- **LLM-dependent extraction**: Field extraction quality depends on the LLM. The rule engine makes all verdict decisions — the LLM never assigns tiers.
