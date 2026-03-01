# blackroad-fleet-tracker

> **Production-grade vehicle & device fleet management** — GPS tracking, geofencing, idle detection, and trip analytics.

[![CI](https://github.com/BlackRoad-Hardware/blackroad-fleet-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/BlackRoad-Hardware/blackroad-fleet-tracker/actions)
[![PyPI](https://img.shields.io/pypi/v/blackroad-fleet-tracker.svg)](https://pypi.org/project/blackroad-fleet-tracker/)
[![npm](https://img.shields.io/npm/v/@blackroad/fleet-tracker.svg)](https://www.npmjs.com/package/@blackroad/fleet-tracker)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](./LICENSE)

Part of the [BlackRoad-Hardware](https://github.com/BlackRoad-Hardware) IoT & hardware intelligence platform.

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Features](#2-features)
3. [Installation](#3-installation)
   - [Python (pip)](#python-pip)
   - [JavaScript / TypeScript (npm)](#javascript--typescript-npm)
4. [Quick Start](#4-quick-start)
5. [API Reference](#5-api-reference)
   - [FleetTracker](#fleettracker)
   - [Asset](#asset)
   - [Geofence](#geofence)
   - [Helper Functions](#helper-functions)
6. [Architecture](#6-architecture)
7. [Configuration](#7-configuration)
8. [Stripe Billing Integration](#8-stripe-billing-integration)
9. [Testing](#9-testing)
   - [Unit Tests](#unit-tests)
   - [End-to-End Tests](#end-to-end-tests)
10. [Contributing](#10-contributing)
11. [BlackRoad Platform Repositories](#11-blackroad-platform-repositories)
12. [License](#12-license)

---

## 1. Platform Overview

`blackroad-fleet-tracker` is the fleet management module of the BlackRoad OS IoT platform. It provides real-time asset tracking with persistent SQLite storage, Haversine-accurate distance calculations, circular geofencing with enter/exit event emission, and idle-detection analytics.

It is designed to be embedded directly in backend services, deployed as a standalone microservice, or consumed via the official npm wrapper (`@blackroad/fleet-tracker`) from a Node.js or TypeScript front-end.

---

## 2. Features

| Capability | Details |
|---|---|
| **Asset CRUD** | Register, update, and query vehicles, drones, containers, sensor nodes, and robots |
| **GPS tracking** | Record timestamped location points with speed, heading, accuracy, and source |
| **Haversine distance** | Sub-metre accurate great-circle distance and bearing calculations |
| **Geofencing** | Circular geofences with automatic enter / exit event logging |
| **Idle detection** | Configurable movement-threshold idle detection over a rolling time window |
| **Trip analytics** | Cumulative trip distance over arbitrary look-back periods |
| **Nearest-asset search** | Sorted proximity search across the entire fleet |
| **Fleet dashboard** | Aggregate status snapshot grouped by asset state |
| **Thread-safe persistence** | SQLite WAL mode with per-write locking — safe for concurrent workers |

---

## 3. Installation

### Python (pip)

**Requirements:** Python ≥ 3.9

```bash
pip install -r requirements.txt
```

For production deployments, pin the dependency in your own `requirements.txt`:

```
blackroad-fleet-tracker==<version>
pytest>=7.0.0
```

### JavaScript / TypeScript (npm)

The official npm wrapper exposes the same API over a local socket or HTTP transport.

**Requirements:** Node.js ≥ 18

```bash
npm install @blackroad/fleet-tracker
```

```ts
import { FleetTrackerClient } from '@blackroad/fleet-tracker';

const client = new FleetTrackerClient({ baseUrl: 'http://localhost:8080' });
const asset = await client.getAsset('t1');
```

> See the [npm package README](https://www.npmjs.com/package/@blackroad/fleet-tracker) for the full TypeScript API.

---

## 4. Quick Start

```python
from fleet_tracker import FleetTracker, Asset, Geofence

# Initialise tracker (creates fleet_tracker.db on first run)
tracker = FleetTracker()

# Register an asset
truck = Asset("t1", "Truck Alpha", "vehicle", lat=40.7128, lon=-74.0060)
tracker.register_asset(truck)

# Add a geofence
depot = Geofence("gf-depot", "Main Depot", center_lat=40.7128,
                 center_lon=-74.0060, radius_km=1.0)
tracker.add_geofence(depot)

# Update location (triggers geofence evaluation automatically)
tracker.update_location("t1", lat=40.7200, lon=-74.0100, speed_kmh=55.0)

# Query proximity
nearby = tracker.get_assets_near(lat=40.7128, lon=-74.0060, radius_km=5.0)

# Check idle status
idle_status = tracker.detect_idle("t1", threshold_minutes=30)

# Fleet dashboard
print(tracker.get_fleet_status())
```

Run the bundled demo:

```bash
python fleet_tracker.py
```

---

## 5. API Reference

### FleetTracker

```python
FleetTracker(db_path: str = "fleet_tracker.db")
```

The primary interface. All methods are thread-safe.

| Method | Signature | Returns | Description |
|---|---|---|---|
| `register_asset` | `(asset: Asset) -> Asset` | `Asset` | Upsert an asset record |
| `get_asset` | `(asset_id: str) -> Optional[Asset]` | `Asset \| None` | Fetch a single asset by ID |
| `list_assets` | `(status=None, asset_type=None) -> List[Asset]` | `List[Asset]` | List assets with optional filters |
| `update_location` | `(asset_id, lat, lon, speed_kmh, heading_deg, accuracy_m, source) -> LocationPoint` | `LocationPoint` | Record a new GPS fix; auto-evaluates all active geofences |
| `get_assets_near` | `(lat, lon, radius_km) -> List[Dict]` | `List[Dict]` | Assets within radius, sorted by distance |
| `add_geofence` | `(geofence: Geofence) -> Geofence` | `Geofence` | Upsert a geofence |
| `check_geofence` | `(asset_id, geofence_id) -> Dict` | `Dict` | Point-in-circle test for an asset/geofence pair |
| `get_geofence_events` | `(asset_id=None, hours=24) -> List[Dict]` | `List[Dict]` | Recent enter/exit events |
| `get_asset_history` | `(asset_id, hours=24) -> List[LocationPoint]` | `List[LocationPoint]` | Ordered location history |
| `calc_trip_distance` | `(asset_id, hours=24) -> float` | `float` km | Cumulative Haversine trip distance |
| `detect_idle` | `(asset_id, threshold_minutes=30) -> Dict` | `Dict` | Idle analysis over rolling window |
| `get_fleet_status` | `() -> Dict` | `Dict` | Aggregate fleet snapshot |

### Asset

```python
@dataclass
class Asset:
    id: str
    name: str
    type: str           # vehicle | drone | container | sensor_node | robot
    location_lat: float
    location_lon: float
    status: str         # active | idle | offline | maintenance  (default: "active")
    last_seen: str      # ISO-8601 UTC
    speed_kmh: float    # default 0.0
    heading_deg: float  # default 0.0
    metadata: dict      # arbitrary key/value store
    created_at: str     # ISO-8601 UTC
```

### Geofence

```python
@dataclass
class Geofence:
    id: str
    name: str
    center_lat: float
    center_lon: float
    radius_km: float
    type: str   # "circle"  (polygon support extensible)
    active: bool
    created_at: str  # ISO-8601 UTC
```

### Helper Functions

```python
calc_distance(lat1, lon1, lat2, lon2) -> float   # km, Haversine
calc_bearing(lat1, lon1, lat2, lon2)  -> float   # degrees, 0–360
```

---

## 6. Architecture

```
┌─────────────────────────────────────────────────────┐
│                  FleetTracker                       │
│  ┌──────────┐  ┌────────────┐  ┌────────────────┐  │
│  │  Asset   │  │ Geofencing │  │   Analytics    │  │
│  │  CRUD    │  │  Engine    │  │  (idle/trip)   │  │
│  └────┬─────┘  └─────┬──────┘  └───────┬────────┘  │
│       └──────────────┴─────────────────┘           │
│                       │                             │
│              ┌─────────▼──────────┐                 │
│              │  SQLite (WAL mode) │                 │
│              │  assets            │                 │
│              │  locations         │  ← indexed      │
│              │  geofences         │                 │
│              │  geofence_events   │  ← indexed      │
│              └────────────────────┘                 │
└─────────────────────────────────────────────────────┘
```

- **Pure Python** — no external service dependencies; embeds anywhere Python 3.9+ runs.
- **SQLite WAL mode** — concurrent readers never block writers; safe for multi-threaded workers.
- **Per-write locking** — a single `threading.Lock` guards all write paths.
- **Self-initialising** — `init_db()` is idempotent; schema is created on first instantiation.
- **Dataclass domain model** — typed, serialisable, and easy to extend.
- **Indexed queries** — `locations(asset_id, timestamp)` and `geofence_events(asset_id, timestamp)` are indexed for fast range scans.

---

## 7. Configuration

| Variable / Parameter | Default | Description |
|---|---|---|
| `db_path` | `"fleet_tracker.db"` | SQLite database file path |
| `threshold_minutes` | `30` | Idle detection window (minutes) |
| `radius_km` | — | Geofence or proximity search radius |
| `accuracy_m` | `10.0` | Default GPS accuracy estimate (metres) |
| `source` | `"gps"` | Location source: `gps \| cell \| wifi \| manual` |
| `LOG_LEVEL` | `INFO` | Set via `logging.basicConfig(level=...)` |

---

## 8. Stripe Billing Integration

`blackroad-fleet-tracker` supports metered billing via **Stripe Metered Usage** so you can charge customers per tracked asset, per location update, or per API call.

### Prerequisites

```bash
pip install stripe
```

### Usage-based billing example

```python
import os
import stripe
from fleet_tracker import FleetTracker, Asset

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]  # never hardcode credentials

tracker = FleetTracker()

def track_with_billing(subscription_item_id: str,
                        asset_id: str, lat: float, lon: float) -> None:
    """Record a location update and report one usage unit to Stripe."""
    tracker.update_location(asset_id, lat, lon)

    stripe.SubscriptionItem.create_usage_record(
        subscription_item_id,
        quantity=1,
        action="increment",
    )
```

### Recommended Stripe products

| Product | Stripe feature | Use case |
|---|---|---|
| Per-asset seat fee | Recurring subscription | Monthly per-vehicle licence |
| Location update volume | Metered billing | Pay-as-you-go GPS pings |
| Geofence event alerts | Metered billing | Charge per enter/exit event |
| Fleet dashboard API calls | Metered billing | SaaS API usage billing |

### Environment variables

Store all Stripe keys in environment variables — never commit them to source control:

```bash
export STRIPE_SECRET_KEY="sk_live_..."
export STRIPE_WEBHOOK_SECRET="whsec_..."
```

> See the [Stripe Metered Billing guide](https://stripe.com/docs/billing/subscriptions/usage-based) for full setup instructions.

---

## 9. Testing

### Unit Tests

```bash
pytest test_fleet_tracker.py -v
```

The test suite covers:

| Test | Description |
|---|---|
| `test_haversine_known_distance` | NYC to uptown ~5.3 km accuracy |
| `test_haversine_zero` | Same-point distance is 0 |
| `test_bearing_north` | North bearing ≈ 0° |
| `test_update_location` | Location write & read-back |
| `test_invalid_lat_raises` | Out-of-range latitude rejected |
| `test_get_assets_near` | Proximity inclusion |
| `test_get_assets_near_excludes_far` | Proximity exclusion |
| `test_geofence_check_inside` | Point inside geofence |
| `test_geofence_check_outside` | Point outside geofence |
| `test_asset_history` | Location history length |
| `test_detect_idle` | Idle detection (no movement) |
| `test_detect_not_idle` | Not-idle detection (movement) |
| `test_trip_distance` | Trip distance > 0 |
| `test_unknown_asset_raises` | Unknown asset ID rejected |

### End-to-End Tests

Run the full demo end-to-end to verify database creation, asset registration, geofence evaluation, idle detection, and fleet status output:

```bash
python fleet_tracker.py
```

Expected output (values will vary slightly):

```
Distance to uptown NYC: 5.37 km
Assets within 5km: 2
Location points: 10
Trip distance: 7.4944 km
Idle: False
In warehouse geofence: False
{'total': 2, 'by_status': {'active': 2}, 'assets': [...]}
```

For integration testing against a live Stripe sandbox:

```bash
export STRIPE_SECRET_KEY="sk_test_..."
pytest test_fleet_tracker.py -v -m integration
```

---

## 10. Contributing

1. Fork the repository and create a feature branch from `main`.
2. Install development dependencies: `pip install -r requirements.txt`
3. Write tests for all new behaviour.
4. Ensure the full test suite passes: `pytest test_fleet_tracker.py -v`
5. Open a Pull Request with a clear description of the change and its motivation.

**Code style:** PEP 8, type-annotated public functions, dataclasses for domain objects.

---

## 11. BlackRoad Platform Repositories

| Repository | Description |
|---|---|
| [blackroad-smart-home](https://github.com/BlackRoad-Hardware/blackroad-smart-home) | Smart home controller: scenes, scheduling, device groups |
| [blackroad-sensor-network](https://github.com/BlackRoad-Hardware/blackroad-sensor-network) | IoT sensor aggregator with Z-score anomaly detection |
| [blackroad-automation-hub](https://github.com/BlackRoad-Hardware/blackroad-automation-hub) | Rules engine: triggers, conditions, actions |
| [blackroad-energy-optimizer](https://github.com/BlackRoad-Hardware/blackroad-energy-optimizer) | Energy tracking, peak analysis, CO2 equivalent |
| **blackroad-fleet-tracker** | **Fleet GPS tracking, geofencing, idle detection** ← you are here |

---

## 12. License

© BlackRoad OS, Inc. All rights reserved.

See [LICENSE](./LICENSE) for full terms.
