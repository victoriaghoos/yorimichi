# 🌸 Yorimichi (寄り道)

> "The art of the scenic detour." | 「寄り道の美学をデジタル化する。」

**Yorimichi** is a routing engine that plans not just the *shortest* walking route between two points, but also a **scenic** alternative that favors paths near temples, shrines, parks, water, nature, and historic sites while avoiding busy roads. It currently covers Japan's Kansai and Kanto regions (~20.5M nodes / 44.4M edges, verified via `SELECT COUNT(*)` against the live PostGIS graph), and started as a single-district proof of concept in Higashiyama, Kyoto.

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square)](https://www.python.org/)
[![Architecture](https://img.shields.io/badge/architecture-Hexagonal-orange?style=flat-square)](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software))
[![Status](https://img.shields.io/badge/status-solo_side_project-yellow?style=flat-square)](#status--limitations)

---

## What it does

Given an origin and destination, the backend's `/route` endpoint returns two routes:
- a **baseline** route (plain shortest path via NetworkX)
- a **scenic** route computed with a custom A* variant ("S-A*")

Cost per edge:

$$\text{edgeCost}(u, v) = \text{distance}(u, v) \times \text{ScenicPenalty}(u, v) \times \text{RoadPenalty}(u, v)$$

- `ScenicPenalty` discounts edges near scenic OSM points of interest (nearest-POI lookup via a KD-tree), weighted by category: a temple/shrine pulls harder than a generic "attraction" tag.
- `RoadPenalty` penalizes busy `highway` tags (`primary`, `trunk`, `secondary`, ...).
- The A* heuristic scales straight-line distance by the *best-case* scenic discount, so it never overestimates the true remaining cost, keeping the search admissible.

Scenic categories (⛩️ shrines/temples, 🌸 parks, 🌊 water, 🏯 historic sites, 🌳 nature, 🌉 viewpoints) can each be boosted or weakened per request via query parameters, and toggled from the frontend.

---

## Architecture

Hexagonal (Ports & Adapters), with real dependency inversion rather than just folder naming:

- **Domain** (`domain/`): pure Python: entities (`Node`, `Edge`, `Route`), scoring, the S-A* math, and abstract ports (`IGraphRepository`, `IScenicDataProvider`). No OSMnx/NetworkX/PostGIS imports.
- **Application** (`application/`): `PlanScenicRouteUseCase` orchestrates domain logic purely through ports; it never leaks raw infrastructure objects (e.g. a NetworkX graph) to its callers.
- **Infrastructure** (`infrastructure/`): two interchangeable `IGraphRepository` adapters, in-memory OSMnx/NetworkX, and PostGIS (using a real spatial nearest-node query), plus a scenic-POI provider and the FastAPI entrypoint. The backend is selectable via a `YORIMICHI_GRAPH_BACKEND` env var, and an integration test asserts both backends return comparable-length routes for the same input (within a tolerance, since PostGIS is a periodically-imported snapshot while OSMnx queries live OSM data).

---

## Tech stack

| Layer | Technology |
| :--- | :--- |
| Backend | Python 3.12+, FastAPI, NetworkX/OSMnx, SQLAlchemy 2.0, PostgreSQL/PostGIS, scipy (KD-tree), Poetry, ruff + mypy |
| Frontend | React 19, TypeScript, Vite, react-leaflet |
| Data | OSM PBF extracts for Kansai and Kanto, imported into PostGIS via a custom batch importer (`backend/scripts/import_graph_to_postgis.py`) — 20.5M nodes / 44.4M edges currently loaded |

---

## Status & limitations

An actively-evolving **solo side project**, not a finished product:

- ✅ Core algorithm, hexagonal architecture, and both graph backends are implemented and covered by 83 automated tests (unit + integration).
- ✅ Working React/Leaflet frontend: click-to-set origin/destination, geolocation ("use my location"), per-category boost toggles, dual route rendering with a color-blind-safe palette.
- ✅ CI on every push/PR ([.github/workflows/ci.yml](.github/workflows/ci.yml)): backend `ruff` + `mypy` + unit tests, frontend ESLint + build. Integration tests (real network/DB calls) are excluded from CI and run manually.
- ⚠️ `backend/tests/e2e/` exists but is currently empty.
- ⚠️ Scenic scoring depends on OpenStreetMap tag quality, which is inherently inconsistent; the category-weight table is a manually curated approximation, not a solved problem.
- ❌ PWA/offline support and live GPS route-tracking while walking are not implemented (`vite-plugin-pwa` is listed as a dependency but not yet wired into `vite.config.ts`).
- 

## Repository structure

```
yorimichi/
├── backend/    Python/FastAPI routing engine (domain / application / infrastructure)
└── frontend/   React/Vite/TypeScript client
```

The backend is a self-contained, independently testable service; the frontend is one consumer of its `/route` API.

---

> "Yorimichi: because the shortest path isn't always the best one."
> 「寄り道：最短ルートが、最高のルートとは限らない。」