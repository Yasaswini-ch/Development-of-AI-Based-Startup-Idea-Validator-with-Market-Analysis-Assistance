# 19. Milestone 3: PostgreSQL Data Persistence & JWT Authentication Architecture

**Document Version:** 3.0 (Milestone 3 Architecture Specification)  
**Status:** Implemented & Verified  
**Target Audience:** Database Engineers, Backend Architects, Security Engineers  

---

## 📑 Executive Summary & Milestone 3 Scope

Milestone 3 expands Affinity from a stateless validation engine into an enterprise-ready SaaS application featuring **persistent user accounts**, **encrypted dossier storage**, **historical validation tracking**, and **role-based access control (RBAC)**.

While the core validation pipeline (`POST /validate`) retains its optional anonymous mode for privacy-conscious founders, authenticated users gain the ability to save validation dossiers, track market score changes over time, organize startup ideas into team workspaces, and export branded PDF reports.

```mermaid
flowchart TD
    subgraph AnonymousMode["Anonymous Execution Mode"]
        AnonReq["POST /validate (No Token)"] --> MemoryCache["SHA-256 Volatile Memory Cache (30-min TTL)"]
        MemoryCache --> StatelessResp["Stateless Validation Dossier"]
    end
    
    subgraph AuthenticatedMode["Authenticated User Engine (Milestone 3)"]
        AuthReq["POST /validate (Bearer JWT Token)"] --> AuthCheck["JWT Validation Middleware"]
        AuthCheck --> DBStore["PostgreSQL Storage Engine"]
        DBStore --> HistoryDB["User Workspace & Saved Validation History"]
        DBStore --> ExportEngine["PDF Export & Sharing Service"]
    end
```

---

## 1. Database Schema Design & ER Diagram

The persistent data layer is implemented using PostgreSQL with SQLAlchemy ORM (and Alembic migration management).

```mermaid
erDiagram
    USERS ||--o{ WORKSPACES : owns
    USERS ||--o{ VALIDATIONS : creates
    WORKSPACES ||--o{ WORKSPACE_MEMBERS : contains
    WORKSPACES ||--o{ VALIDATIONS : houses
    VALIDATIONS ||--o{ COMPETITOR_ENTITIES : contains
    VALIDATIONS ||--o{ SEARCH_SOURCES : cites

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        string avatar_url
        string role
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    WORKSPACES {
        uuid id PK
        uuid owner_id FK
        string name
        string slug UK
        timestamp created_at
    }

    WORKSPACE_MEMBERS {
        uuid workspace_id PK, FK
        uuid user_id PK, FK
        string role
        timestamp joined_at
    }

    VALIDATIONS {
        uuid id PK
        uuid user_id FK
        uuid workspace_id FK
        string idea_title
        text target_customer
        text problem_statement
        int opportunity_score
        jsonb market_opportunity_json
        jsonb white_space_json
        jsonb confidence_json
        boolean is_archived
        timestamp created_at
    }

    COMPETITOR_ENTITIES {
        uuid id PK
        uuid validation_id FK
        string name
        string price_bucket
        string feature_breadth
        text local_context
        timestamp created_at
    }

    SEARCH_SOURCES {
        uuid id PK
        uuid validation_id FK
        string title
        string url
        string domain
        float relevance_score
        timestamp created_at
    }
```

---

## 2. JWT Authentication Lifecycle & Security Specifications

### Token Issuance & Refresh Pattern
*   **Access Tokens:** Short-lived JWTs (15-minute expiration) signed using `RS256` or `HS256` (`HMAC-SHA256`).
*   **Refresh Tokens:** Long-lived tokens (7-day expiration) stored in `HttpOnly`, `Secure`, `SameSite=Strict` cookies.
*   **Password Hashing:** Argon2id / bcrypt with work factor 12.

```mermaid
sequenceDiagram
    participant User as Client App (React)
    participant Auth as FastAPI Auth Route (/auth/login)
    participant DB as PostgreSQL Database
    participant JWT as JWT Signer / Verifier

    User->>Auth: POST /auth/login {email, password}
    Auth->>DB: Query user by email
    DB-->>Auth: User record (password_hash)
    Auth->>Auth: Verify password hash (bcrypt)
    alt Password Match
        Auth->>JWT: Issue access_token (15m) & refresh_token (7d)
        JWT-->>Auth: Token Pair
        Auth-->>User: 200 OK + Set-Cookie (refresh_token) + JSON {access_token}
    else Invalid Credentials
        Auth-->>User: 401 Unauthorized {error: "Invalid credentials"}
    end
```

---

## 3. Milestone 3 API Endpoints & Contracts

### 1. `POST /auth/register` — Create User Account
*   **Request:** `{"email": "founder@startup.io", "password": "SecurePassword123!", "full_name": "Alex Rivner"}`
*   **Response (HTTP 201 Created):** `{"id": "usr_94821a", "email": "founder@startup.io", "message": "Account created successfully"}`

### 2. `GET /api/v1/validations/history` — Fetch Saved Validations
*   **Headers:** `Authorization: Bearer <access_token>`
*   **Query Params:** `?page=1&limit=10&workspace_id=ws_123`
*   **Response (HTTP 200 OK):**
```json
{
  "total": 14,
  "page": 1,
  "validations": [
    {
      "id": "val_88319a",
      "ideaTitle": "AI Specialty Coffee Discovery App",
      "opportunityScore": 79,
      "competitorCount": 4,
      "createdAt": "2026-09-15T14:30:00Z"
    }
  ]
}
```

---

## 4. Zero-Trust Security & Data Isolation
1.  **Row-Level Isolation:** All database queries enforce `workspace_id` and `user_id` scoping to prevent cross-tenant data leakage.
2.  **Volatile Fallback:** Unauthenticated requests bypass PostgreSQL entirely, ensuring zero DB load during public traffic spikes.
