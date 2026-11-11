# Chatter — Architecture Walkthrough (Interview Brief)

> Enterprise GenAI chatbot for HPE GreenLake. Natural-language querying over many
> data sources (OpenSearch, SQL, external HPE APIs) with intent-based routing.
>
> Stack: **FastAPI** (API) · **LangChain `create_agent`** (reasoning agent) ·
> **LangGraph `StateGraph`** (data-source workflow) · **AWS Bedrock** (Claude,
> Llama, Rerank) · **PostgreSQL** (data + agent memory) · **Redis** (status/response cache).

Open [chatter-architecture.drawio](chatter-architecture.drawio) in VS Code (Draw.io
Integration extension) or at <https://app.diagrams.net> alongside this document.

---

## Talking-track in one line

Request comes in over HTTP → FastAPI accepts it and returns `201` immediately →
a background task runs the **LangChain agent** → the agent decides whether to
greet, clarify, or call its `search_data_sources` tool → that tool runs a
**LangGraph workflow** that classifies intent (RAG + rerank), fans out to the
right data-source nodes, consolidates, then summarizes → the final answer is
written to **Redis**, and the client **polls** for it.

---

## 1 · The request

**Entry point:** `POST /ui-doorway/ui/chats` — `chatter/web/routers/chats.py` →
`create_chat()`.

**Inputs**
- **Body:** `ChatQuery { query, sessionId }`.
- **Headers:** `rugby-cid` (workspace/tenant id), `rugby-user-email`,
  `Rugby-JWT` (auth, held as `SecretStr`), `Time-Zone` (validated against IANA zones).

**Why async from the very first hop.** LLM pipelines are slow (multiple model
calls). We do **not** block the HTTP connection. `create_chat()`:
1. Calls `ChatService.validate_and_create_chat(...)` → budget + session checks,
   creates a DB row, returns a `201 Created` with the entry `id` and `sessionId`.
2. Fires `asyncio.create_task(process_and_store_chat_with_timeout(...))` — the
   heavy work (the `# noqa: RUF006` fire-and-forget task) — and returns.

So the client gets an id instantly and then **polls** `GET /chats/{id}` for the
final answer (see §4).

**Security at the boundary**
- Prompt-injection screening on the raw query (`_validate_user_query`) before it
  ever reaches an LLM → `UsageViolationError` on a hit.
- Budget enforcement per `rugby-cid` (`BudgetService.is_workspace_over_budget`).
- JWT kept as `SecretStr`, never logged.

---

## 2 · How the request is processed

### 2a. Application layer (`chatter/application_services/`)
`ChatService.process_and_store_chat` orchestrates the business flow:
budget check → prompt-injection guard → session validation → call the
orchestrator → persist results to Postgres + write-through Redis cache.

It delegates the actual reasoning to
`Orchestrator.process_query()` (`chatter/core/orchestrator.py`).

### 2b. The LangChain agent (reasoning / decision layer)
`Orchestrator._invoke_query` opens a **Postgres checkpointer** and invokes
`ChatAgent` (`chatter/core/agents/chat_agent.py`). `ChatAgent` builds a LangChain
agent with `create_agent(...)`:

```python
chat_agent = create_agent(
    model=model,                               # Bedrock / relay / on-prem (routed)
    tools=[search_data_sources_tool,           # ← runs the LangGraph workflow
           greetings_tool,
           clarification_tool],
    system_prompt=cached_prompt,               # Bedrock prompt-caching applied
    middleware=middleware_list,                # delete_messages, scope validation, followup ctx
    checkpointer=checkpointer,                 # ← conversation memory (see §3)
    response_format=ToolStrategy(ChatAgentResponse),  # structured output
    context_schema=ChatAgentContext,
)
```

This is a **ReAct-style agent**: the LLM reads the system prompt + conversation
history and chooses one of three paths:
- **greeting** → `greetings_tool` (fast path, no data retrieval),
- **ambiguous** → `intent_clarification_tool` (ask the user to disambiguate),
- **real question** → `search_data_sources_tool`, which hands off to the
  LangGraph workflow below.

### 2c. The LangGraph workflow (data-source execution layer)
`search_data_sources` runs `Orchestrator.get_chat_workflow()` — a
`StateGraph(ChatState)`. Shape (condensed from the real graph):

```
START
  → parallel_dispatch_intent_node        # QueryDispatcher ‖ IntentClassification (RAG + rerank), run concurrently
  → route_after_parallel_dispatch        # conditional edge
      ├─ TASK      → source_tracker → source_processor_node (fan-out per source)
      ├─ DOCUMENT  → document_node  (RAG answer) → END
      └─ OUTOFSCOPE→ outofscope_handler_node → END
  → source nodes: servers | server_inventory | groups | metrics | alerts |
                  activities | insights | firmware | firmware_baselines | ahs
  → consolidate_source_results_node      # merge multi-source results
  → persist_query_results_node           # store raw results
  → summarization_and_followup_node      # summarize + generate follow-ups (parallel)
  → END
```

Key design points to mention:
- **Intent classification is itself RAG:** the user query is matched against
  data-source description documents via vector retrieval, then **reranked**
  (Bedrock Titan Rerank) to pick the right source(s) —
  `IntentClassificationTool`.
- **Parallelism:** dispatcher + intent run concurrently in one node; multi-source
  questions fan out; summarization and follow-up generation run in parallel.
- **`ChatState` is the shared blackboard** (`chatter/core/utils/chat_state.py`):
  a `TypedDict` carrying `query`, `chat_history`, `identified_sources`,
  `source_to_results`, `token_summary`, `output`, `followup_questions`, etc.
  Every node reads/writes this typed state.
- **Model routing per call:** each tool/agent gets an `OnPremModelRouter` /
  `FeatureFlagModelRouter` keyed by a `route_key`, so any call can be flagged to
  Bedrock Claude/Llama, AI Relay, or an on-prem OpenAI-compatible endpoint.

---

## 3 · What LangChain does — and how it holds memory

### What LangChain gives us
- **`create_agent`** — the ReAct loop: prompt construction, tool binding, the
  model↔tool call cycle, and parsing the model's tool calls. We don't hand-write
  the agent loop.
- **`ToolStrategy(ChatAgentResponse)`** — **structured output**: the final answer
  is coerced into a typed Pydantic schema instead of free text.
- **Tools as plain callables** — `search_data_sources`, `greetings`,
  `clarification` are exposed to the LLM; the LLM decides which to call.
- **Middleware hooks** — `delete_messages` (prune history), scope-validation
  (reject out-of-scope asks early), `include_previous_followup_context`.
- **LangGraph `StateGraph`** — the deterministic, inspectable workflow graph for
  the data-source stage (nodes, conditional edges, parallel branches).
- **Model abstractions** — `langchain_core` message types (`HumanMessage`,
  `AIMessage`, `ToolMessage`) and the `Runnable` interface every tool implements
  (`ainvoke`; `invoke` raises `NotImplementedError` — fully async service).

### How memory works (the important interview point)
Memory is **not** an in-process Python dict — it's a **LangGraph checkpointer**
keyed by `thread_id = session_id`.

```python
async with get_postgres_saver() as checkpointer:      # AsyncPostgresSaver
    agent_result = await self.chat_agent.ainvoke(
        state={... "session_id": session_id ...},
        checkpointer=checkpointer,
    )
...
agent_result = await chat_agent.ainvoke(
    {"messages": [HumanMessage(content=user_query)]},
    context=state,
    config={"configurable": {"thread_id": session_id}},   # ← memory key
)
```

- **Persistence:** `AsyncPostgresSaver`
  (`chatter/infrastructure/data/postgres_saver.py`) serializes the full message
  list + state to **PostgreSQL** after each step, using a `JsonPlusSerializer`
  with an allow-list of types (`ChatAgentResponse`, `TokenSummary`,
  `DataSourceEnum`, …) for safe msgpack round-tripping.
- **Recall:** on the next turn in the same session, LangGraph loads the prior
  messages for that `thread_id`, so the agent sees the whole conversation and can
  answer follow-ups ("…and which of *those* are critical?") without re-querying.
- **Scoping:** memory is isolated per `session_id`; a new session → fresh
  `thread_id` → clean history.
- **Cost control vs. memory:** because the checkpointer replays *all* historical
  messages, token accounting deliberately counts **only the current turn**
  (`_get_current_turn_messages`) so billing/budget isn't inflated by history.
- **In-memory variant:** `invoke_from_node` / report paths use
  `InMemorySaver()` (ephemeral) when persistence isn't needed — e.g. starting the
  graph mid-way for tests/reports.

> One-liner: *"LangChain runs the agent loop and structured output; memory is a
> Postgres-backed LangGraph checkpointer keyed by the session id, so the whole
> conversation is durable and survives restarts."*

---

## 4 · How the response is handled

### Building the response
The summarization node produces `output` (the natural-language summary) plus
`followup_questions`, `server_filter`, `actions`, `data_source(s)`. `ChatService`
wraps these into a `ChatResponse`:

```
ChatResponse {
  summary, data, followupQuestions, questionType,
  serverFilter, serverFilterTruncated, serverFilterTotal,
  actions, answered, errorReason, dataSource, dataSources
}
```

### Delivery (async + cache)
1. The background task writes the completed `ChatResponse` to **Redis**
   (write-through) and persists chat data + token usage to **PostgreSQL**
   (`ChatDataService.update_chat_data`).
2. Status moves `PROCESSING → COMPLETED` (`ChatStatusReporter`).
3. The client **polls `GET /chats/{id}`**, which reads the cached entry and
   returns the final answer. Until then it sees `PROCESSING` + a default summary.

### Guardrails & error handling on the way out
- **Bedrock Guardrails** / scope violations → response replaced with
  `GUARDRAILS_BLOCKED_TEXT`, `data`/`followups` cleared.
- **`answered` flag** is computed by checking the summary against known
  "can't-answer" responses, so the UI knows whether the question was satisfied.
- **Token accounting** per call via `TokenManager`, aggregated into
  `TokenSummary`, fed back into `BudgetService` for usage control.
- **Timeout:** `process_and_store_chat_with_timeout` cancels runaway processing;
  abandoned cleanup tasks are tracked so they aren't GC'd mid-flight.

---

## Quick-reference: file map (for follow-up questions)

| Concern | File |
| --- | --- |
| HTTP entry / async pattern | [chatter/web/routers/chats.py](../../chatter/web/routers/chats.py) |
| Business orchestration | [chatter/application_services/chat_service.py](../../chatter/application_services/chat_service.py) |
| Agent + LangGraph wiring | [chatter/core/orchestrator.py](../../chatter/core/orchestrator.py) |
| LangChain agent + memory | [chatter/core/agents/chat_agent.py](../../chatter/core/agents/chat_agent.py) |
| Postgres checkpointer (memory) | [chatter/infrastructure/data/postgres_saver.py](../../chatter/infrastructure/data/postgres_saver.py) |
| Shared workflow state | [chatter/core/utils/chat_state.py](../../chatter/core/utils/chat_state.py) |
| Intent = RAG + rerank | [chatter/core/tools/intent_classification_tool.py](../../chatter/core/tools/intent_classification_tool.py) |
| RAG retriever (OpenSearch) | [chatter/core/utils/document_retriever.py](../../chatter/core/utils/document_retriever.py) |
| Model routing (Bedrock/relay/on-prem) | [chatter/core/models/](../../chatter/core/models/) |

## Likely follow-up questions — have an answer ready
- **Why LangGraph *and* a LangChain agent?** Agent = flexible LLM-driven routing
  (greet/clarify/search); Graph = deterministic, inspectable, parallelizable
  data-source execution. Best of both.
- **How do you keep LLM cost down?** Prompt caching (Bedrock cache points),
  current-turn-only token counting, per-workspace budgets, Haiku vs Sonnet per
  route, rerank to narrow retrieval.
- **How is multi-source handled?** Intent classification can identify several
  sources; `source_tracker`/`source_processor` fan out, then
  `consolidate_source_results_node` merges before summarization.
- **How do you evaluate quality?** Functional tests with `llm_trace`, regression
  suites (`tests/regression/`), summary/doc evaluation tools.
- **Governance / responsible AI?** Guardrails, scope-validation middleware,
  prompt-injection screening, feature-flag gating of every new data source,
  structured + budget-bounded outputs.