# SatQuery X

> **Interactive Vision-Language Assistant for Multimodal Remote Sensing Image Analysis through Text Queries**
>
> Smart India Hackathon 2026 · Problem Statement **SIH26167** · Team EXOR

SatQuery X is a remote-sensing intelligence workspace that lets an analyst interact with satellite imagery using natural-language queries. Instead of requiring the user to manually choose a model for every task, the system is designed around an agentic orchestration layer that validates inputs, interprets the query, routes work to specialised analysis capabilities, and returns an evidence-oriented result with confidence and execution traceability.

## What it supports

- **Single-image VQA and scene understanding** — ask questions about an uploaded satellite image.
- **Captioning / scene description** — generate a structured description of a scene.
- **Spatial / ROI analysis** — focus an analysis on a selected region of interest.
- **Bi-temporal change analysis** — compare baseline (**T0**) and current (**T1**) observations.
- **Optical + SAR workflows** — combine complementary information from cross-sensor imagery.
- **Evidence & traceability** — expose processing stages and supporting information rather than treating the final answer as a black box.
- **Audit trail** — keep an execution-oriented record of analysis activity.
- **3D Earth Explorer** — provide geographic and temporal context around satellite observations.
- **Provider-backed AI integrations** — the backend can use configured multimodal/text AI providers through environment variables.

## Architecture

```text
                       NATURAL-LANGUAGE QUERY
                                  │
                                  ▼
                         INPUT VALIDATION
                    (format / modality / pairing)
                                  │
                                  ▼
                         AGENTIC CONTROLLER
                      (intent + workflow routing)
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
         SINGLE IMAGE          TEMPORAL             OPTICAL + SAR
        VQA / CAPTIONING     CHANGE ANALYSIS          ANALYSIS
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  ▼
                      EVIDENCE / CONFIDENCE
                                  │
                                  ▼
                         EXPLAINABLE RESULT
                                  │
                                  ▼
                            AUDIT TRAIL
```

The frontend is the analyst-facing command centre. The FastAPI backend provides the API and specialist routing surface. AI provider adapters are kept behind the backend so credentials remain server-side.

## Repository layout

```text
SatQueryX-Workspace/
├── frontend/                 # React + Vite analyst interface
│   ├── src/
│   │   ├── api/              # Backend client and API integration
│   │   └── components/       # UI components
│   └── index.html             # CesiumJS / web entry point
├── backend/                  # FastAPI application and routes
│   ├── routes/               # Upload, query, change, fusion, audit, etc.
│   ├── services/             # Backend services such as keep-alive / change logic
│   └── main.py                # Application entry point
├── ai/                       # Vision / VQA / provider adapters
├── .github/workflows/        # CI checks
├── render.yaml               # Render deployment configuration
├── requirements.txt          # Python dependencies
└── .env.example              # Backend environment template
```

## Tech stack

### Frontend
- React 19
- TypeScript
- Vite
- CesiumJS for the 3D Earth Explorer

### Backend
- Python
- FastAPI
- Uvicorn
- Pillow / NumPy
- Pydantic
- HTTPX
- python-dotenv
- python-multipart

### AI / orchestration
- Provider adapters for Gemini and OpenAI-compatible / OpenRouter-style vision endpoints
- Optional text providers such as Groq / OpenAI-compatible services
- Remote-sensing VLM / specialist-model integration points
- Evidence-oriented response and audit layers

The frontend currently uses React 19, TypeScript and Vite, while the backend dependency set is defined in `requirements.txt`. fileciteturn707file0 fileciteturn708file0

## API surface

The backend exposes `/api` endpoints for the major workflows, including:

| Capability | Endpoint |
|---|---|
| Image upload | `POST /api/upload` |
| Natural-language query | `POST /api/query` |
| Captioning | `POST /api/caption` |
| Temporal / change analysis | `POST /api/analyze/change` |
| Optical + SAR fusion | `POST /api/fuse` |
| Audit log retrieval | `GET /api/audit` |
| Copilot / chat | `POST /api/chat` |
| Region analysis | `POST /api/analyze/region` |
| High-precision escalation | `POST /api/analyze/escalate` |
| Pair validation | `POST /api/validate/pair` |
| Earth / catalog helpers | `POST /api/tee/*` |
| Health | `GET /api/health` |

The frontend client is wired to these workflows and uses `VITE_API_URL` when explicitly configured. In production it defaults to the deployed Render backend; locally it defaults to `http://localhost:8000`. fileciteturn709file0

The FastAPI application registers image, query, audit, caption, comparison, change, fusion, chat, specialist, region, escalation, Earth-explorer, pair-validation, and benchmark routes, plus `/api/health`. fileciteturn710file0

## Running locally

### 1. Clone

```bash
git clone https://github.com/Aryanrai-007/SatQueryX-Workspace.git
cd SatQueryX-Workspace
```

### 2. Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Frontend

```bash
cd frontend
npm ci
npm run dev
```

Then open the Vite URL shown in the terminal (normally `http://localhost:5173`).

For local development, set:

```env
VITE_API_URL=http://localhost:8000
```

The frontend API client otherwise falls back to the deployed backend in production and localhost during local development. fileciteturn709file0

## Environment configuration

Copy the backend template:

```bash
cp .env.example .env
```

Configure only the providers you intend to use. Typical variables include:

```env
GEMINI_API_KEY=
GEMINI_MODEL=

OPENROUTER_API_KEY=
OPENROUTER_MODEL=
OPENROUTER_VISION_MODEL=
OPENROUTER_SITE_URL=

GROQ_API_KEY=
GROQ_MODEL=

OPENAI_API_KEY=
OPENAI_MODEL=

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:latest
```

**Never commit real API keys to Git.** Keep secrets in the deployment provider or local environment.

## Deployment

The project is structured for separate frontend/backend deployment.

- **Frontend:** Vite build output can be deployed to Vercel or another static hosting platform.
- **Backend:** FastAPI can be deployed to Render or another Python service.
- **Environment variables:** configure API credentials on the server side.

The repository includes a `render.yaml` service configuration, and the frontend API client is already prepared to talk to the deployed Render backend unless `VITE_API_URL` overrides it. fileciteturn709file0

## Product workflow

A typical analysis session looks like:

1. **Provide imagery** — upload a supported image or image pair.
2. **Define the question** — ask what you want to know in natural language.
3. **Validate context** — verify that the image count, modality and pairing are appropriate for the requested workflow.
4. **Route the task** — select or invoke the appropriate specialist analysis path.
5. **Inspect the result** — review the answer alongside visual/contextual evidence.
6. **Audit the execution** — inspect traceability information where available.

## Supported image formats

The current upload interface is intended for common raster image inputs such as:

- PNG
- JPEG / JPG
- TIFF / TIF

For benchmark and production workflows, dataset-specific constraints still apply. The application should not assume that arbitrary images are equivalent to georeferenced remote-sensing data.

## Remote-sensing model adaptation

SatQuery X is designed to combine general multimodal language capabilities with remote-sensing-specific components. The broader SIH architecture includes adaptation / fine-tuning of a vision-language component using remote-sensing training data such as BigEarthNet.txt or other open-source datasets.

During development, a PaliGemma-based adaptation pipeline has been used as an engineering path for remote-sensing VQA experimentation. Foundation-model training from scratch is intentionally avoided in favour of modular adaptation and specialist components.

## Evidence-first design

A central design principle is that the language model should not be treated as the scientific source of truth.

The intended separation is:

```text
LLM / router  → interprets intent and coordinates work
Specialists   → perform task-specific image analysis
Evidence      → supports the observed result
Synthesis     → converts evidence into an analyst-readable answer
```

When sufficient evidence is unavailable, the system should prefer a conservative response over fabricating unsupported observations.

## Current prototype status

This repository contains the working application architecture and product interface for the SatQuery X concept. Some capabilities are stronger than others depending on the configured model/provider and available compute.

The project should therefore distinguish clearly between:

- **Implemented application workflows** — UI, API routing, upload/query flows, validation surfaces, audit/evidence presentation and provider integration.
- **Model-dependent functionality** — specialist VQA, grounding, change detection and multimodal inference quality depends on the configured models and runtime.
- **Research / benchmark work** — final model quality and hidden-dataset performance require dedicated evaluation and should not be inferred from the prototype UI alone.

## SIH 2026 context

SatQuery X is being developed for Smart India Hackathon 2026, Problem Statement **SIH26167**: an interactive vision-language assistant for multimodal remote-sensing image analysis through text queries.

The target architecture is intended to cover:

- single-image VQA,
- an additional single-image capability such as captioning or grounding,
- bi-temporal change reasoning,
- optical + SAR multimodal analysis,
- agentic validation and specialist routing,
- evidence, confidence and auditable execution traces.

## Research foundations

The architecture is informed by research and benchmark directions including:

- **BigEarthNet / BigEarthNet v2.0** — remote-sensing image understanding and land-cover representation.
- **RSVQA** — visual question answering for remote-sensing data.
- **VRSBench** — remote-sensing vision-language grounding, captioning and VQA.
- **CDVQA** — bi-temporal change reasoning and change-based visual question answering.

## Contributing

For development work:

```bash
git checkout -b feature/<name>
# make changes
npm run build
# run backend checks / tests as applicable
git commit -m "feat: ..."
git push origin feature/<name>
```

Please keep API credentials, generated datasets and large model artefacts out of Git history.

## Disclaimer

SatQuery X is a research and hackathon prototype. Remote-sensing outputs can be sensitive to sensor characteristics, spatial alignment, image quality, temporal variation, cloud cover and model limitations. Results should be validated by qualified analysts before operational or safety-critical use.

## Team

**Team EXOR**  
Smart India Hackathon 2026  
Problem Statement: **SIH26167**
