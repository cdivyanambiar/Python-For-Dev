# Switch Copilot: local prototype

A small, **fictional, read-only** observability demo. Ask about switch inventory
and alerts in SQLite, switch runbooks, or both. Nothing connects to real HPE
systems. The sample data is a static snapshot, not live telemetry.

## What goes where

```text
Co-pilot/
  all-MiniLM-L6-v2/  copied Hugging Face embedding model
  app/
    main.py           FastAPI: submit and poll a background job
    workflow.py       LangGraph: route -> documents and/or SQL -> answer
    retrieval.py      section chunks + MiniLM embeddings + cosine similarity
    database.py       sample SQLite data + read-only SQL guard
    model.py          local Ollama HTTP client
    config.py         paths and model name
  docs/               fictional switch runbook
  data/               SQLite database created on first startup
  tests/              focused tests with a fake language model
```

The routing step is a model call, not a LangChain agent. LangGraph runs source
steps sequentially, including for mixed questions. The prototype does not have
sessions, authentication, PostgreSQL, Redis, a durable queue, token budgets,
reranking or model-provider routing. Jobs live in one server process and are
lost on restart. Run one worker only.

## Models

Your copied **all-MiniLM-L6-v2** is the embedding model: it converts the question
and runbook sections into vectors for semantic retrieval. It cannot generate SQL
or answers. No embedding-model download is needed if the copied files are intact.

For generation, install [Ollama](https://ollama.com/download) and pull
[`qwen2.5:1.5b`](https://ollama.com/library/qwen2.5:1.5b) (about 986 MB;
Apache 2.0). It is small but can produce incorrect routes, SQL, and answers. A
larger alternative is [`qwen2.5:3b`](https://ollama.com/library/qwen2.5:3b)
(about 1.9 GB; different Qwen license). Download size is not total RAM required;
memory use depends on context and hardware. Evaluate accuracy and licensing
before using any model in a real service.

## Run on Windows PowerShell

From this directory, with Python 3.10+ and Ollama installed:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
ollama pull qwen2.5:1.5b
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If `.venv` is already present, skip creating it and installing dependencies.
Make sure the Ollama service is running. To use the 3B model, pull it and set
`$env:OLLAMA_MODEL = "qwen2.5:3b"` in the same terminal before starting Uvicorn.
Keep the model folder as `all-MiniLM-L6-v2` in this directory.

Open `http://127.0.0.1:8000/docs` for the interactive API. Or, in another
PowerShell window:

```powershell
$body = @{ question = "Which switches are offline and how do I troubleshoot them?" } | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/questions -ContentType "application/json" -Body $body
Invoke-RestMethod -Uri "http://127.0.0.1:8000/questions/$($job.job_id)" | ConvertTo-Json -Depth 10
```

Poll the GET endpoint until status is `completed` or `failed`. Try:

- `Which switches are offline?`
- `How should I investigate high CPU on a switch?`
- `Which switches have open alerts and how should I troubleshoot high CPU?`

Completed responses include the route, answer, and applicable document snippets,
generated SQL, and SQL result. Inspect the evidence; citations and correctness
are not guaranteed by the model. A failed job is reported as `failed` and
details are logged on the server. No relevant RAG results produces an explicit
insufficient-evidence answer.

Run tests with `.\.venv\Scripts\python -m unittest discover -s tests -v`.

## Safety and limitations

The SQL model can make mistakes. SQLite opens the database read-only, authorizes
reads only from the two demo tables and an allowlist of functions, limits query
execution time, and returns at most 50 rows. This is a demo guard, not a
multi-tenant security boundary. Sample docs and data are untrusted model context;
prompt injection and hallucinations remain possible. Do not expose this service
or use it with real customer data without authentication, tenant isolation,
stronger query controls, observability, durable jobs, and evaluation.
