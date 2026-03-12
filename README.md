# EVA Automotive Template Catalog

Monorepo containing backend and frontend applications for managing automotive floor-mat templates.

## Structure

- `src/` — Backend API (Node.js + Express + TypeScript + PostgreSQL)
- `apps/web/` — Frontend catalog UI (React + TypeScript + Tailwind + React Query)
- `docs/` — Architecture documentation

## Backend quick start

```bash
cp .env.example .env
npm install
npm run migrate
npm run dev
```

## Frontend quick start

```bash
cd apps/web
npm install
npm run dev
```
