# DialecticAI — Runtime V2

**Status: archive.** Frozen after the owner's algorithm made v2's approach (a judge model
checking every move) obsolete; kept, unmodified, only because the numbers in
`../ENGINE_V2_LESSONS.md` and `../RESEARCH_HISTORY_AND_PROGRAM.md` are computed from this
code and its logs (see [archive/run_logs/INDEX.md](archive/run_logs/INDEX.md)). For the
active engine see [../dialectic_world/](../dialectic_world/) (v3). `archive/docs/` holds
superseded planning documents kept for the same reason.

An experimental agent runtime with an enforced dialectical **world-roadmap**.
First the model derives a simplest process, its development, an independently developing
opposite, their contradiction and a proposed leap. Only an accepted complete roadmap
permits tool execution. Practice can require revising the roadmap.

Read [RUNTIME_CONTRACT.md](RUNTIME_CONTRACT.md) for the authoritative current contract,
validation boundary and distinction between a planned and realized leap.

## Install (Python 3.10+)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,dashboard]"
```

On Linux/macOS activate with `source .venv/bin/activate`.
Copy `.env.example` to `.env` and configure only the provider you use. Never commit keys.

## Verify without network calls

```powershell
python -m pytest -q
python -m tests.local_runner
```

The local runner is an explicit simulation, not a real answer to a task.

## Run a real agent

```json
{"name":"Calculator","goal":"Compute accurately and verify using Python.","llm":"groq","tools":["python_executor"],"max_iterations":30}
```

Save as `calculator.json`, configure `GROQ_API_KEY` and `GROQ_MODEL` for a model available to your account, then:

```powershell
python -m dialectic_ai run calculator.json
```

Example input: `Calculate 17 * 23 and verify the result with Python.` Each run first
constructs its roadmap, then acts. This spends inference quota and can reject proposals
or stop without completion. PythonExecutor is for trusted local use only.

**Verified working combination (2026-09-19):** actor `gigachat` with `GIGACHAT_MODEL=GigaChat-2-Max`
(the free base `GigaChat` model is noticeably less reliable at the strict JSON contract over a
long run). The semantic judge is auto-selected to a *different* provider than the actor — Groq
is excluded from judging (a point-test caught it false-rejecting a valid proposal), so configure
at least one of Gemini/Cerebras/OpenAI alongside your actor for real semantic validation instead
of a same-provider self-judgment fallback. See `.env.example`.

Opt-in end-to-end real-provider check (up to 25 iterations, 480 seconds):

```powershell
$env:DIALECTIC_RUN_CANARY="1"
$env:DIALECTIC_CANARY_PROVIDER="gigachat"
python -m pytest tests/test_canary_real_provider.py -v
```

## Dashboard

Moved to `archive/dashboard/` along with the rest of this archive (unused in the current
pipeline). To run it anyway:

```powershell
python -m dialectic_ai.api.server
```

In another terminal:

```powershell
cd archive/dashboard
npm ci
npm run dev
```

Open the Vite address printed in the terminal. Backend defaults to `127.0.0.1:8123`.
`VITE_API_BASE` overrides the frontend API URL. Choose Mock for simulation; real-provider
runs expose `fetch_url`, which fetches supplied URLs and is not a search engine.

## Evidence and limitations

`trace.jsonl` records roadmap versions, decisions and observations.
`python -m dialectic_ai eval --trace trace.jsonl` checks the latest run's trace structure.
Live dashboard state is in memory. Automatic resume, multi-user authentication and
conversational memory are not implemented. Semantic validation is enabled for real
models, but is still an LLM judgment. No superiority or benchmark accuracy is claimed.
Historical documents may describe removed code; use RUNTIME_CONTRACT.md for current behavior.
