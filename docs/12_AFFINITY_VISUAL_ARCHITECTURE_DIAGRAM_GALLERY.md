# 12. System Architecture & Diagrams Gallery
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 3.0 · updated 2026-09-26 against `staging`  
**Status:** Verified & Operational  

---

## 📑 Diagrams Index
1. [Diagram 1: Multi-Tier System Topology](#diagram-1-multi-tier-system-topology)
2. [Diagram 2: LangGraph Pipeline State Machine](#diagram-2-langgraph-pipeline-state-machine)
3. [Diagram 3: End-to-End Request Sequence](#diagram-3-end-to-end-request-sequence)
4. [Diagram 4: Data Privacy & Ephemeral Caching Lifecycle](#diagram-4-data-privacy--ephemeral-caching-lifecycle)
5. [Diagram 5: Target Audience Segmentation Matrix](#diagram-5-target-audience-segmentation-matrix)
6. [Diagram 6: User Journey & Interactive State Flow](#diagram-6-user-journey--interactive-state-flow)
7. [Diagram 7: Local spaCy NER Competitor Pipeline](#diagram-7-local-spacy-ner-competitor-pipeline)
8. [Diagram 8: Multi-Stage LLM Output Repair Guard](#diagram-8-multi-stage-llm-output-repair-guard)
9. [Diagram 9: Accounts, Dashboards & Admin Access](#diagram-9-accounts-dashboards--admin-access)
10. [Diagram 10: Confidence Headline Recompute](#diagram-10-confidence-headline-recompute)
11. [Diagram 11: LLM Fallback Chain with Shape Validation](#diagram-11-llm-fallback-chain-with-shape-validation)

---

## Diagram 1: Multi-Tier System Topology

```mermaid
flowchart TD
    subgraph ClientLayer["1. Presentation Tier (React + Tailwind)"]
        UI["React SPA (App.jsx)"]
        Session["Browser sessionStorage"]
        UI <--> Session
    end

    subgraph GatewayLayer["2. Gateway Tier (FastAPI)"]
        Main["FastAPI Router (main.py)\nrate limiting + request tracing"]
        Cache["Database-backed Cache (30-min TTL)"]
        Main <--> Cache
    end

    subgraph PipelineLayer["3. Orchestration Tier (LangGraph)"]
        Graph["LangGraph State Machine (graph.py)"]
        ChatGraph["Chat Graph (chat_graph.py)"]
        SearchModule["agent/retrieval.py"]
        ConfidenceModule["confidence_indicator +\nconfidence_dashboard (in graph.py)"]
        MarketModule["agent/market_agent.py"]
        CompetitorModule["agent/competitor_agent.py"]
        WhiteSpaceModule["agent/white_space.py"]
        ScoreModule["agent/opportunity_score.py"]
        SwotModule["agent/swot_agent.py"]
        MvpModule["agent/mvp_agent.py"]
        GtmModule["agent/gtm_agent.py"]
        ReportModule["agent/report_assembler.py"]
        AuthModule["agent/auth.py\n(JWT, require_admin)"]
        AnalyticsModule["user_analytics.py +\nplatform_metrics.py"]
        EventsModule["agent/events.py\n(durable event log)"]

        Graph --> SearchModule
        Graph --> ConfidenceModule
        Graph --> MarketModule
        Graph --> CompetitorModule
        Graph --> WhiteSpaceModule
        Graph --> ScoreModule
        Graph --> SwotModule --> MvpModule --> GtmModule
        GtmModule --> ReportModule
    end

    subgraph PersistenceLayer["4. Persistence Tier"]
        DB[("Postgres (prod) /\nSQLite (local) - agent/db.py")]
    end

    subgraph ExternalLayer["5. Cloud API Tier"]
        Groq["Groq Cloud LLM API (qwen3.8-27b + fallbacks)"]
        Gemini["Gemini API (final fallback tiers)"]
        Tavily["Tavily Search API"]
        DDG["DuckDuckGo Search (Fallback)"]
        SendGrid["SendGrid Email API"]

        Groq -.fallback.-> Gemini
        MarketModule --> Groq
        SwotModule --> Groq
        MvpModule --> Groq
        GtmModule --> Groq
        SearchModule --> Tavily
        SearchModule -.Fallback.-> DDG
        ReportModule -.email.-> SendGrid
    end

    UI -->|POST /validate| Main
    Main --> Graph
    Main --> ChatGraph
    Main <--> DB
    Main --> AuthModule
    Main --> AnalyticsModule
    Graph --> EventsModule
    AuthModule <--> DB
    AnalyticsModule <--> DB
    EventsModule --> DB
```

---

## Diagram 2: LangGraph Pipeline State Machine

```mermaid
flowchart TD
    START(["Start Request"]) --> WebSearch["1. web_search_node\n(5 Search Angles)"]
    WebSearch --> Confidence["2. confidence_indicator\n(Source Agreement per Angle)"]
    Confidence --> Market["3. market_opportunity_node\n(Groq LLM Reasoning)"]
    Market --> Competitors["4. competitor_discovery_node\n(Local spaCy NER)"]
    Competitors --> Score["5. opportunity_score_node\n(0-100 Score Formulation)"]
    Score --> WhiteSpace["6. white_space_node\n(Gap Synthesis)"]
    WhiteSpace --> Swot["7. swot_node\n(Groq LLM, sourceIds per claim)"]
    Swot --> Viability["8. viability_score_node\n(demand, risk, velocity +\ncompetitionClarity, timing)"]
    Viability --> Mvp["9a. mvp_node\n(LLM Feature Prioritization)"]
    Viability --> Gtm["9b. gtm_node\n(LLM Positioning/Channels)"]
    Mvp --> Contra["10. contradiction_detector"]
    Gtm --> Contra
    Contra --> Exp["11. experiment_generator"]
    Exp --> Plan["12. action_plan"]
    Plan --> Assume["13. assumption_tracker (LLM)"]
    Assume --> Revenue["14. revenue_models (LLM)"]
    Revenue --> ConfDash["15. confidence_dashboard_node\n(recomputes headline over cited sources)"]
    ConfDash --> Verdict["16. compute_verdict\n(Pursue / Validate first / Rethink)"]
    Verdict --> END(["Return JSON Payload + sessionId"])
```

MVP and GTM run in parallel. Quick mode stops after market, competitor and white-space
analysis.

---

## Diagram 3: End-to-End Request Sequence

```mermaid
sequenceDiagram
    participant User as Founder (Browser)
    participant API as FastAPI Gateway
    participant Graph as LangGraph State Machine
    participant Search as Tavily / DDG API
    participant Groq as Groq LLM Cloud
    participant NER as spaCy NER (Local)

    User->>API: POST /validate (idea, customer, problem)
    API->>API: Check 30-min SHA-256 volatile cache
    alt Cache Hit
        API-->>User: 200 OK Cached JSON
    else Cache Miss
        API->>Graph: pipeline.invoke(state)
        Graph->>Search: collect(idea, customer, problem)
        Search-->>Graph: Array of 10+ web snippets
        Graph->>Graph: Evaluate confidence_indicator regex
        Graph->>Groq: Execute market_opportunity agent
        Groq-->>Graph: Formatted Market JSON
        Graph->>NER: Execute analyze_competitors(snippets)
        NER-->>Graph: Competitors list + 3x3 Grid
        Graph->>Graph: Synthesize white_space & opportunity_score
        Graph-->>API: Complete PipelineState
        API-->>User: 200 OK JSON Response
    end
```

---

## Diagram 4: Data Privacy & Ephemeral Caching Lifecycle

> The cache moved from an in-memory dict to the `validation_cache` database table in
> Milestone 4. Same 30-minute TTL and same rule: partial results are never cached.

```mermaid
sequenceDiagram
    participant Client as React Client
    participant Server as FastAPI Server
    participant Cache as validation_cache table (Postgres/SQLite)

    Client->>Server: POST /validate
    Server->>Server: Normalize fields & compute SHA-256 hash
    Server->>Cache: _get_cached(hash)
    alt Entry Exists & Age < 30 min
        Cache-->>Server: Return cached payload
        Server-->>Client: 200 OK (Instant)
    else Entry Expired / Missing
        Server->>Server: Execute Agent Pipeline
        alt Pipeline Executed Without Error
            Server->>Cache: _set_cached(hash, payload)
            Server-->>Client: 200 OK
        else Partial Failure Occurred
            Server-->>Client: 200 OK with errors payload (Not Cached)
        end
    end
```

---

## Diagram 5: Target Audience Segmentation Matrix

```mermaid
flowchart TD
    subgraph Matrix["Target Audience Matrix"]
        subgraph HighResearch["High Research Frequency"]
            P2["Student Entrepreneurs\n(Campus Pitch Competitions & Incubators)"]
            P1["Solo Bootstrappers\n(Side Projects & Indie Hackers)"]
        end
        subgraph LowResearch["Low Research Frequency"]
            P4["Angel Investors & VC Analysts\n(Deal Screening)"]
            P3["Product Managers\n(Feature Roadmaps & Expansion)"]
        end
        HighResearch --- LowResearch
    end
```

---

## Diagram 6: User Journey & Interactive State Flow

```mermaid
flowchart LR
    subgraph InputPhase["1. Submission"]
        direction TB
        A1["Founder inputs Idea"] --> A2["Optionally enters Customer & Problem"]
        A2 --> A3["Clicks Validate Idea"]
    end

    subgraph ExecutionPhase["2. Processing Engine"]
        direction TB
        B1["Multi-Angle Web Search"] --> B2["Cross-Source Agreement"]
        B2 --> B3["LLM Market Reasoning"]
        B3 --> B4["spaCy NER Competitor Parsing"]
        B4 --> B5["Score & White-Space Triangulation"]
    end

    subgraph DisplayPhase["3. Validation Dossier"]
        direction TB
        C1["Review 0-100 Score"] --> C2["Inspect Market Segments & Trends"]
        C2 --> C3["Analyze 3x3 Positioning Grid"]
        C3 --> C4["Evaluate White-Space Gaps & Sources"]
    end

    A3 --> B1
    B5 --> C1
```

---

## Diagram 7: Local spaCy NER Competitor Pipeline

```mermaid
flowchart LR
    Snippets["Retrieved Search Snippets"] --> Normalize["1. Join lines with '. ' (Sentence boundaries)"]
    Normalize --> NER["2. spaCy en_core_web_sm (Extract ORG)"]
    NER --> Filter["3. Filter platform terms & generic denylist"]
    Filter --> Context["4. _has_product_context() validation"]
    Context --> Heuristics["5. Local context pricing & breadth extraction"]
    Heuristics --> Grid["3x3 Grid Placement"]
```

---

## Diagram 8: Multi-Stage LLM Output Repair Guard

```mermaid
flowchart LR
    Raw["Raw Groq LLM Output"] --> Strip["1. strip_reasoning()<br/>(Remove <think> tags)"]
    Strip --> Find["2. _find_balanced_objects()<br/>(Brace-depth extraction)"]
    Find --> Repair["3. _repair_invalid_escapes()<br/>(Fix illegal backslashes)"]
    Repair --> Shape["4. _is_valid_shape()<br/>(Schema validation)"]
    Shape --> Output["Validated Structured JSON"]
```

---

## Diagram 9: Accounts, Dashboards & Admin Access

```mermaid
flowchart TD
    Visitor["Visitor"] -->|optional| SignIn["POST /auth/signup or /auth/login\n(bcrypt + 30-day JWT)"]
    Visitor -->|optional| Google["POST /auth/google\n(Google ID token, verified server-side)"]
    Google --> Me
    Visitor -->|anonymous| Validate["POST /validate"]
    SignIn --> Me["GET /auth/me\n{ id, email, isAdmin }"]
    Me --> Menu["AccountMenu dropdown"]
    Menu --> History["History\nGET /me/history"]
    Menu --> Compare["Compare ideas\nPOST /reports/compare"]
    Menu --> Dash["Dashboard\nGET /me/analytics"]
    Menu -->|isAdmin only| Health["Platform health\nGET /admin/platform-metrics"]
    Dash --> Tabs["Overview · Comparison matrix ·\nValidation history · Score trends"]
    Env["ADMIN_EMAILS env var"] -->|startup bootstrap +\nself-heal on each check| AdminFlag[("users.is_admin")]
    AdminFlag --> Health
    Events[("events table\n90-day TTL")] --> Health
```

---

## Diagram 10: Confidence Headline Recompute

```mermaid
flowchart LR
    Raw["Raw search pool\n(all angles, 30-50+ results)"] --> CI["confidence_indicator\n(early)"]
    CI -->|perAngle kept| Final["confidence object"]
    CI -.headline overwritten.-> Final
    Claims["Cited claims\n(SWOT, MVP, GTM, market\ntrends/segments/TAM-SAM-SOM)"] --> CD["confidence_dashboard\n(last)"]
    Raw -->|relevance lookup| CD
    CD -->|headline: cited sources with relevance >= 0.5| Final
    CD -->|coverage, agreement, direct evidence,\navg relevance, recency| Final
```

See [confidence-and-evidence-scoring-methodology.md](confidence-and-evidence-scoring-methodology.md).

---

## Diagram 11: LLM Fallback Chain with Shape Validation

```mermaid
flowchart TD
    Call["Agent calls kickoff_with_fallback(build_crew, validate)"] --> M1["groq/qwen/qwen3.8-27b"]
    M1 -->|rate limit / provider error /\nfails validate| M2["groq/openai/gpt-oss-20b"]
    M2 -->|same| M3["groq/openai/gpt-oss-120b"]
    M3 -->|same| M4["gemini/gemini-3.6-flash"]
    M4 -->|same| M5["gemini/gemini-3.8-flash"]
    M1 & M2 & M3 & M4 & M5 -->|passes validate| OK(["Use response"])
    M5 -->|all failed| Q{"allow_local and\nOllama reachable?"}
    Q -->|yes| Local["Local Ollama model"]
    Q -->|no| Retry["Cooldown, then one more\npass over M1..M5"]
    Local -->|fails| Retry
    Local -->|passes| OK
    Retry -->|passes| OK
    Retry -->|fails| End{"allow_local?"}
    End -->|no| Ask["NeedsDeepAnalysisError\n(/validate asks for email;\nonly possible where Ollama exists)"]
    End -->|yes| Degraded["Deterministic fallback\n(degraded: true)"]
```
