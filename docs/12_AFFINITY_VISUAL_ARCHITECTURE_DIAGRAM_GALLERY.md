# 12. System Architecture & Diagrams Gallery
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
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
        Tavily["Tavily Search API"]
        DDG["DuckDuckGo Search (Fallback)"]
        Resend["Resend Email API"]

        MarketModule --> Groq
        SwotModule --> Groq
        MvpModule --> Groq
        GtmModule --> Groq
        SearchModule --> Tavily
        SearchModule -.Fallback.-> DDG
        ReportModule -.email.-> Resend
    end

    UI -->|POST /validate| Main
    Main --> Graph
    Main --> ChatGraph
    Main <--> DB
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
    Swot --> Mvp["8. mvp_node\n(Groq LLM Feature Prioritization)"]
    Mvp --> Gtm["9. gtm_node\n(Groq LLM Positioning/Channels)"]
    Gtm --> ConfDash["10. confidence_dashboard_node\n(Source Coverage, Recency, Agreement)"]
    ConfDash --> END(["Return JSON Payload + sessionId"])
```

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

```mermaid
sequenceDiagram
    participant Client as React Client
    participant Server as FastAPI Server Memory
    participant Cache as Volatile Cache Dict

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
