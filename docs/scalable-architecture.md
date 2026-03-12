# EVA Template Catalog — Scalable Architecture Design

## 1) System Architecture

### High-level architecture

Use a **modular monolith** first (single deployable backend with clear module boundaries), designed so modules can be extracted into services later if needed.

```text
[React + TS + Tailwind SPA]
          |
          v
    [API Gateway Layer]
   (Auth, rate-limit, logging)
          |
          v
[Node.js Backend (Modular Monolith)]
  ├─ Car Platform Module (EVA)
  ├─ Template Modification Module (ART)
  ├─ Hanger Module
  ├─ Search/Filter Module
  ├─ Import Module (Google Sheets)
  ├─ Status/Workflow Module
  └─ Activity Log Module
          |
          v
      [PostgreSQL]
   + indexes + FTS + partition-ready
          |
          v
   [Redis] (cache, queue, sessions)
          |
          v
 [Background Workers]
  (import jobs, indexing, reconciliation)
```

### Why this architecture

- **Fast delivery**: one backend codebase is simpler for a small team.
- **Scalable boundaries**: each domain module can later become microservice if traffic or org complexity grows.
- **Operational simplicity**: one DB (PostgreSQL) reduces consistency issues and avoids premature distributed-system complexity.
- **Performance**: caching + async workers isolate heavy operations (imports, reindexing) from user-facing API latency.

---

## 2) Backend Architecture

### Runtime and style

- Node.js + TypeScript.
- REST API with OpenAPI spec.
- Layered structure per module:
  - `controller` (HTTP)
  - `service` (business rules)
  - `repository` (DB access)
  - `dto/validator` (schema validation)

### Domain modules

1. **EVA Car Platform Module**
   - CRUD for car platforms.
   - Owns fields: `eva_code`, `brand`, `model`, `generation`, etc.
2. **ART Modification Module**
   - CRUD for modifications linked to EVA.
   - Bulk operations for import.
3. **Hanger Module**
   - Hanger management and section mapping.
   - Validates location constraints.
4. **Search Module**
   - Multi-field search and faceted filtering.
   - Supports card list and expansion endpoints.
5. **Status Module**
   - Status states per EVA or ART (e.g., draft, verified, archived).
   - Transition rules.
6. **Activity Log Module**
   - Immutable audit trail for key events.
7. **Import Module**
   - Parses Google Sheets snapshots.
   - Validates, deduplicates, upserts.

### Cross-cutting concerns

- **AuthN/AuthZ**: JWT + role-based access (`admin`, `operator`, `viewer`).
- **Validation**: Zod or Joi at API boundaries.
- **Observability**: structured logs, metrics (latency, error rates), tracing hooks.
- **Idempotency** for import endpoints.
- **Pagination defaults** to prevent large payloads.

---

## 3) Database Schema (PostgreSQL)

### Core tables

#### `car_platforms` (EVA)
- `id` (uuid pk)
- `eva_code` (varchar unique, indexed)
- `brand` (varchar indexed)
- `model` (varchar indexed)
- `generation` (varchar)
- `body_type` (varchar indexed)
- `production_year_start` (smallint)
- `production_year_end` (smallint)
- `hanger_id` (fk -> hangers.id, indexed)
- `template_type` (enum: `2D`, `5D`, indexed)
- `status` (enum: `draft`, `active`, `archived`)
- `search_vector` (tsvector, indexed GIN)
- `created_at`, `updated_at`

#### `template_modifications` (ART)
- `id` (uuid pk)
- `car_platform_id` (fk -> car_platforms.id, indexed)
- `article_code` (varchar unique, indexed)
- `drive_type` (enum: `FWD`, `RWD`, `AWD`, indexed)
- `gearbox` (enum: `MANUAL`, `AUTOMATIC`, indexed)
- `fuel_type` (varchar indexed)
- `facelift_version` (varchar)
- `status` (enum)
- `created_at`, `updated_at`

#### `hangers`
- `id` (uuid pk)
- `hanger_number` (int unique, indexed)
- `brand` (varchar indexed)
- `warehouse_section` (varchar indexed)
- `notes` (text)
- `created_at`, `updated_at`

#### `activity_logs`
- `id` (bigserial pk)
- `entity_type` (enum: `car_platform`, `template_modification`, `hanger`, `import_job`)
- `entity_id` (uuid)
- `action` (varchar) — created/updated/status_changed/imported
- `before_data` (jsonb)
- `after_data` (jsonb)
- `actor_user_id` (uuid nullable)
- `source` (enum: `ui`, `import`, `system`)
- `created_at` (timestamptz indexed)

#### `import_jobs`
- `id` (uuid pk)
- `source` (enum: `google_sheets`)
- `status` (enum: `queued`, `running`, `completed`, `failed`, `partial`)
- `started_at`, `finished_at`
- `stats` (jsonb) — inserted/updated/failed counts
- `error_report` (jsonb)
- `created_by` (uuid nullable)

### Constraints and indexes

- Unique constraints:
  - `car_platforms.eva_code`
  - `template_modifications.article_code`
  - `hangers.hanger_number`
- Composite index for common filters:
  - `(brand, model, template_type)` on `car_platforms`
  - `(car_platform_id, drive_type, gearbox)` on `template_modifications`
- Full text:
  - GIN index on `search_vector` (brand/model/generation/eva_code).

---

## 4) API Structure (REST)

### Base
- `/api/v1`

### EVA endpoints
- `GET /cars` — paginated list + filters + search.
- `GET /cars/:id` — detail + optional modifications count.
- `POST /cars`
- `PATCH /cars/:id`
- `PATCH /cars/:id/status`
- `DELETE /cars/:id` (soft delete preferred)

### ART endpoints
- `GET /cars/:id/modifications`
- `POST /cars/:id/modifications`
- `PATCH /modifications/:id`
- `PATCH /modifications/:id/status`
- `DELETE /modifications/:id`

### Hanger endpoints
- `GET /hangers`
- `POST /hangers`
- `PATCH /hangers/:id`

### Search endpoints
- `GET /search?q=...&brand=...&templateType=...`
- `GET /filters/meta` (facets/counts for UI chips)

### Import endpoints
- `POST /imports/google-sheets` (start job)
- `GET /imports/:jobId` (status)
- `GET /imports/:jobId/errors` (row-level errors)

### Activity endpoints
- `GET /activity?entityType=car_platform&entityId=...`

### UI optimization endpoint (expandable cards)
- `GET /cards` — returns compact card data.
- `GET /cards/:carId/expand` — returns ART rows for expanded card.

This split minimizes payload on first render and keeps expansion fast.

---

## 5) Google Sheets Import Pipeline

### Flow

1. User triggers import (manual) or scheduler triggers nightly sync.
2. Backend creates `import_jobs` record with `queued`.
3. Worker fetches sheet via Google API.
4. Parser maps rows to canonical DTOs.
5. Validator checks required fields, enums, year ranges, duplicates.
6. Staging process loads normalized rows (in memory or temp table).
7. Upsert in transaction batches:
   - Upsert `hangers`
   - Upsert `car_platforms` by `eva_code`
   - Upsert `template_modifications` by `article_code`
8. Record row-level failures to `error_report`.
9. Emit activity log entries.
10. Mark job completed/partial/failed.

### Reliability decisions

- **Idempotency key** per import run to avoid duplicate writes.
- **Batch size** (e.g., 500 rows) for controlled memory and lock duration.
- **Dead-letter handling** for failed imports.
- **Dry-run mode** to validate without writing.

---

## 6) Performance Strategy for 5000+ Cars

5000 records is moderate for PostgreSQL, but optimize for smooth UX and future growth (50k+).

### Query strategy

- Server-side pagination (limit/offset or cursor).
- Only fetch card fields in list endpoint; lazy-load ART on expand.
- Use selective `SELECT` projections (no `SELECT *`).

### Indexing and search

- B-tree indexes for exact-match filters.
- GIN full-text index for global search.
- Optionally `pg_trgm` for fuzzy search on brand/model/eva/article.

### Caching

- Redis cache for frequent filter metadata and top searches.
- Short TTL (30–120s) with event-driven invalidation on writes.

### Background processing

- Imports and heavy recomputation in worker queue.
- Async activity log enrichment.

### Frontend performance

- Debounced search (200–300ms).
- Virtualized list rendering if card list gets large.
- Optimistic UI for small updates; SWR/React Query cache.

### DB operations

- Connection pooling.
- Analyze slow queries (`EXPLAIN ANALYZE`).
- Periodic vacuum/analyze and index maintenance.

---

## 7) Suggested Project Folder Structure

```text
evasite/
  apps/
    web/                         # React app
      src/
        components/
          cards/
          filters/
          tables/
        pages/
        hooks/
        services/                # API client
        store/
        styles/
    api/                         # Node.js backend
      src/
        modules/
          car-platform/
            car-platform.controller.ts
            car-platform.service.ts
            car-platform.repository.ts
            car-platform.routes.ts
            car-platform.validation.ts
          template-modification/
          hanger/
          search/
          status/
          activity-log/
          import/
        shared/
          db/
          cache/
          auth/
          logger/
          errors/
          utils/
        app.ts
        server.ts
      prisma/ or migrations/
  packages/
    types/                       # shared DTO/types
    eslint-config/
    tsconfig/
  infrastructure/
    docker/
    terraform/ (optional)
  docs/
    scalable-architecture.md
```

This supports monorepo scaling and shared typing between frontend and backend.

---

## Recommended rollout phases

1. **Phase 1 (MVP)**: core CRUD, search, expandable cards, import manual trigger.
2. **Phase 2**: status workflows, activity logs, role-based access.
3. **Phase 3**: caching, advanced search relevance, scheduled imports, observability dashboards.
4. **Phase 4**: service extraction only if needed (e.g., import service, search service).

This phased approach balances speed and long-term maintainability.
