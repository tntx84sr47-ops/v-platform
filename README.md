# V Platform — Phase 1

**Personal & Family Life Operating System** · Miami Beach · 2026

A multi-agent system built on **LangGraph** with a central **V Orchestrator** (CEO agent)
that delegates work to specialist departments.

```
┌──────────────────────── V Orchestrator (LangGraph) ────────────────────────┐
│                                                                            │
│   analyze → decompose → execute → aggregate → evaluate ─┬─► synthesize ─►  │
│                ▲                                        │                  │
│                └───────────────── refine ◄──────────────┘                  │
│                                                                            │
└──────────┬─────────────┬─────────────┬─────────────┬───────────────────────┘
           │             │             │             │
           ▼             ▼             ▼             ▼
       📣 Marketing   🥐 Bakery     ✉️ Comms      🏠 MLO Coach
```

## Quick start

```bash
# 1. Clone / copy these files into your project root
# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
cp .env.example .env
# Then edit .env and set ANTHROPIC_API_KEY (or OPENAI_API_KEY)

# 4. Run
streamlit run streamlit_app.py
```

## Folder layout

```
v_platform/
├── streamlit_app.py              ← UI entrypoint
├── requirements.txt
├── .env.example
│
├── crews/
│   ├── orchestrator/             ← V Orchestrator (CEO, LangGraph)
│   │   ├── graph.py              ← Graph wiring
│   │   ├── nodes.py              ← Node implementations
│   │   ├── state.py              ← Typed state object
│   │   ├── prompts.py            ← All LLM prompts
│   │   └── departments.py        ← Department registry
│   │
│   ├── marketing/crew.py         ← V Marketing
│   ├── bakery/crew.py            ← V Bakery
│   ├── comms/crew.py             ← V Comms
│   └── mlo_coach/crew.py         ← V MLO Coach
│
├── shared/
│   └── llm.py                    ← LLM factory (Anthropic / OpenAI)
│
└── ui/
    ├── orchestrator_view.py      ← Live-streaming orchestrator UI
    └── department_views.py       ← Direct-access department tabs
```

## Adding a new department

1. Create `crews/<name>/crew.py` with a `run(subtask: str, context: str = "") -> str` function.
2. Register it in `crews/orchestrator/departments.py` (`DEPARTMENTS` and `DEPARTMENT_LABELS`).
3. Add the literal name to `DepartmentName` in `crews/orchestrator/state.py`.
4. Update the department list in `crews/orchestrator/prompts.py` (`ORCHESTRATOR_IDENTITY`
   and `DECOMPOSITION_PROMPT`).

That's it — no graph changes needed.

## How the orchestrator runs

1. **analyze** — strategic analysis of the user task
2. **decompose** — produces a JSON plan of subtasks, each owned by one department
3. **execute** — runs subtasks sequentially, passing earlier results as context
4. **aggregate** — concatenates department outputs
5. **evaluate** — LLM scores the result (0.0–1.0) on completeness / quality / coherence
6. **refine** *(conditional)* — if score < threshold and iterations remain, generate
   a targeted patch plan and loop back through `execute`
7. **synthesize** — writes the final, polished answer for the user

Configurable in `.env`:
- `V_ORCHESTRATOR_MAX_ITERATIONS` (default `2`)
- `V_ORCHESTRATOR_QUALITY_THRESHOLD` (default `0.8`)
