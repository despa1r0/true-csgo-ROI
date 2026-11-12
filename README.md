# trueROI

A local catalog of Counter-Strike 2 items with a React interface, fast search,
marketplace data and server-side ROI calculation. The catalog comes from
[ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) and is stored in
PostgreSQL. Market data comes from adapters for CSFloat, CSGO Market,
White.Market, CS.MONEY and DMarket. Known production limitations are listed in
[docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

## Quick start

The app runs with Docker Compose: PostgreSQL, a one-off catalog import
(`catalog-seed`) and the FastAPI service. A CSFloat key and a CSGO Market key are
required. Without them, `start.ps1` stops and market data is unavailable.

The root `Dockerfile` is a multi-stage build: Node 22 builds `frontend-react`,
and the resulting `dist` is copied into the FastAPI runtime image.

The first run downloads skins and the additional ByMykel catalogs (cases,
capsules, stickers, charms, agents, collectibles, music, patches, graffiti,
keys, sticker slabs, tools and souvenir charms), creates the PostgreSQL schema
and imports market variants and collections. This takes a few minutes. Database
data is kept in a Docker volume.

### Linux

1. Install Docker Engine with Compose v2 and make sure your user can access Docker:

   ```bash
   docker compose version
   docker ps
   ```

2. Create `.env` from the template and add your keys:

   ```bash
   cp .env.example .env
   ```

   ```dotenv
   CSFLOAT_API_KEY=your_key
   CSGOMARKET_API_KEY=your_key
   ```

3. Build and start the services:

   ```bash
   docker compose up --build
   ```

   Add `-d` to run in the background. The logs print `Catalogue is ready` when
   the import has finished.

4. Open [http://localhost:8005](http://localhost:8005) or check the API:

   ```bash
   curl http://localhost:8005/api/health
   ```

### Windows

1. Install Docker Desktop, start it and wait for *Engine running*. Then check Compose from the repository root:

   ```powershell
   docker compose version
   ```

2. Run the start script:

   ```powershell
   .\start.ps1
   ```

   If `.env` is missing, the script creates it from `.env.example`. Fill in
   `CSFLOAT_API_KEY` and `CSGOMARKET_API_KEY`, then run the script again. To run
   in the background, use `.\start.ps1 -Detached`.

3. After `Catalogue is ready`, open [http://localhost:8005](http://localhost:8005).
   Check the API with `Invoke-WebRequest http://localhost:8005/api/health`.

### Managing the stack

```bash
docker compose ps            # service status
docker compose logs -f api   # API logs
docker compose down          # stop, keep the database
docker compose down -v       # stop and delete the database volume (full re-import on next start)
```

`down -v` deletes the PostgreSQL volume and all stored project data.

To refresh only the catalog while the database is running:

```bash
docker compose run --rm catalog-seed
```

The command is the same on Linux and in PowerShell.

## Features

- React + TypeScript UI in `frontend-react`, with Russian and English localization.
- Catalog on `/` with autocomplete, filters by item type, weapon, rarity and
  collection, wear variants and marketplace prices. Entries that cannot be reliably
  addressed or sold on marketplaces are excluded during import.
- Active listings from CSFloat, CSGO Market and White.Market when their APIs are
  available, with per-marketplace filters and an `All marketplaces` mode.
- DMarket through its official Trading API. The price index and best bid need no
  keys; listings, the target book and sales history need API keys. See
  [docs/DMARKET.md](docs/DMARKET.md).
- Background CS.MONEY integration. Wiki Market is kept as a fallback aggregated
  summary. Current status and open issues: [docs/PROJECT_STATUS_2026-10-03.md](docs/PROJECT_STATUS_2026-10-03.md).
- Stickers and charms are searchable as standalone items. The `has_stickers` and
  `has_charm` listing filters only check whether an attachment exists, not which one.
- Attachment hover shows its reference price when the provider supplies one.
  Missing prices are not calculated or substituted.
- Item analytics modal with price history, active listings, quick sell and
  marketplace comparison.
- History periods: 24 hours, 7 days, 14 days and the full available range. Charts
  use only real sales, with no synthetic points.
- CSFloat and CSGO Market provide public sales history (CSGO Market history has no
  float values). White.Market does not provide public sales history.
- Calculator at `/calculator` with manual buy and sell prices, optional skin
  selection, marketplace swap, and Raw, Smart, Enhanced, Quick flip and Custom modes.
- Separate checkboxes for deposit, sell and withdrawal fees. Fee rates are set on
  the server and cannot be edited in the browser.
- Marketplace capabilities drive which listings, history, quick sell, float,
  sticker, charm and `best_deal` sorting options are shown.
- Server-side comparison of trade directions, buy orders, quick-sell price and a
  beta liquidity score. Liquidity is diagnostic only and does not change profit or ROI.
- PostgreSQL cache for price indexes and variant details.
- Swagger UI at [http://localhost:8005/docs](http://localhost:8005/docs).

Additional docs: [docs/FRONTEND.md](docs/FRONTEND.md), [docs/CSMONEY.md](docs/CSMONEY.md),
[docs/DMARKET.md](docs/DMARKET.md).

CS.MONEY worker with the existing Surfshark VPN setup:

```bash
docker compose -f docker-compose.csmoney-test.yml up --build -d
```

## Architecture

```text
ByMykel / CSGO-API       CSFloat · CSGO Market · White.Market
         │                              │
         │ catalog-seed                 │ adapters
         ▼                              ▼
skins · skin_variants        normalized prices, listings,
· skin_collections           buy orders and public history
         │                              │
         └──────── PostgreSQL cache ────┘
                        │
                        ▼
          FastAPI: /api/* + Profit Engine
                        │
                        ▼
       frontend-react (React + TypeScript + Vite)
```

### Data flow

1. `catalog-seed` downloads skin variants, grouped collections and extra item
   categories from `CATALOG_EXTRA_SOURCE_BASE_URL`, then upserts them into PostgreSQL.
   Entries without a `market_hash_name`, account-bound items, preview/unreleased
   items and unsupported collectibles are skipped. Search always uses the local
   catalog, not marketplace APIs.
2. A user searches a base skin in `skins` and selects a variant in `skin_variants`
   (for example a specific wear or StatTrak™).
3. The API matches the variant to marketplaces by the exact English
   `market_hash_name`, not by `paint_index`. The same rule applies to new item types.
   Adapters return live minimum prices, listings, buy orders and, where supported, sales history.
4. Price indexes are stored in `marketplace_listings`. Variant details (listings,
   order book, history and liquidity) are stored in `marketplace_variant_details`,
   so reopening a card does not require calling the marketplace again.
5. For a selected comparison, the API fetches normalized data for both sides of the
   trade in parallel. The Profit Engine receives ready amounts and fee rules only.
   It has no knowledge of HTTP, FastAPI, PostgreSQL or external API formats.
6. The React client loads `/api/marketplaces` and enables UI elements based on
   capabilities, not a hard-coded list of marketplaces.

Provider routes live in separate routers under `backend/app/routers`: `csfloat.py`,
`csgomarket.py`, `whitemarket.py`, `csmoney.py` and `dmarket.py`. Their public URLs and OpenAPI
parameters are covered by contract tests. Shared range validation is in
`_validation.py`. `main.py` assembles the app and holds the shared catalog,
comparison, calculation and SPA routes.

### Data layers

| Layer | Contents | Purpose |
| --- | --- | --- |
| `skins` | base skin, weapon, rarity, image, float range | local search and grouping |
| `skin_variants` | exact market name, wear, StatTrak™, Souvenir | selecting an item that can be matched on a marketplace |
| `skin_collections` | collection links | collection filter |
| `marketplace_listings` | minimum price, quantity, fetch time, marketplace | price index cache |
| `marketplace_variant_details` | detailed listings, buy orders, history, metrics | modal and quick-sell cache (600 s TTL) |

Source records are kept in `raw_data JSONB`, so new source fields can be added
without a schema rewrite.

Each adapter isolates its marketplace's format. The shared minimal quote is
`MarketPrice`:

```text
marketplace · price_cents · item_url · listing_id? · float_value? · quantity? · fetched_at? · stale
```

Listing adapters also return `listing_id`, `price_cents`, `item_url`,
`float_value`, `paint_seed`, `paint_index`, `stickers` and `charms`. Fields a
marketplace does not provide are `null` or an empty list. For example, CSGO Market
public history has no float values, and its sticker IDs are not yet mapped to the
official catalog.

### Money and ROI

All money values are integer `*_cents`, never `float`:

```text
effective_buy    = buy_price + deposit_fee
effective_payout = sell_price - sell_fee - withdraw_fee
profit           = effective_payout - effective_buy
ROI              = profit / effective_buy × 100
```

Percentage and fixed fees are defined in `backend/app/marketplaces_fees.py`. The
modes `raw`, `smart`, `enhanced` and `quick_flip` select which rules apply. In
`quick_flip`, the sell price is the best buy order on the receiving marketplace.
The backend checks all available buy and quick-sell directions and sorts them by
net profit, so the lowest ask is not assumed to be the best option.

- `smart` is an ask-to-ask scenario with server-side fees. The sell price is the
  price of a future listing, not a guaranteed immediate sale.
- `quick_flip` uses the executable best bid on the receiving marketplace.
- The liquidity score is not part of any formula and does not affect `profit_cents` or ROI.

## API

Full request and response schemas are in Swagger at
[http://localhost:8005/docs](http://localhost:8005/docs).

```text
Catalog
GET  /api/health
GET  /api/catalog/filters
GET  /api/items/search?q=sticker&item_type=sticker
GET  /api/skins/search?q=redline&weapon=weapon_ak47&rarity=...&collection=...
GET  /api/skins/{skin_id}

Prices and listings
GET  /api/skins/{skin_id}/market/{csfloat|csgomarket|whitemarket|csmoney|dmarket}
GET  /api/skins/{skin_id}/markets/compare?profit_mode=smart&deposit_method=crypto&withdraw_method=crypto
GET  /api/skins/{skin_id}/market/{marketplace}/listings?wear=field-tested&variant=normal
GET  /api/listings/{listing_id}/market/csfloat/quick-sell
GET  /api/variants/{variant_id}/market/{marketplace}
GET  /api/variants/{variant_id}/market/csmoney/price-history

Marketplaces and calculation
GET  /api/marketplaces
GET  /api/market-overview
POST /api/calculate
```

- `/market/{marketplace}` returns the cached minimum price index for all variants of a skin.
- `/markets/compare` matches variants across two marketplaces and returns the
  cheapest price, gross spread and both sides of the trade with ROI. Accepts
  `profit_mode=raw|smart|enhanced|quick_flip`, `deposit_method=card|crypto`,
  `withdraw_method=card|crypto` and `use_deposit_fee`.
- `/listings` returns individual listings. Shared parameters: `wear`,
  `variant=any|normal|stattrak|souvenir`, `min_float`, `max_float`,
  `min_price_cents`, `max_price_cents`, `has_stickers`, `has_charm` and `limit`
  (1–50). CSFloat sorting (`best_deal|lowest_price`) is passed to its API. CSGO
  Market always sorts locally by lowest price; `sort_by` is echoed back for UI compatibility.
- `/api/variants/{variant_id}/market/...` lazily loads and caches details for one
  exact variant: active listings, buy orders, sales history and the beta liquidity estimate.
- `/api/listings/{listing_id}/market/csfloat/quick-sell` returns matching CSFloat
  buy orders for a specific listing.
- `POST /api/calculate` is a deterministic calculation with no marketplace calls.
  Body: `buy_price_cents`, `sell_price_cents`, `buy_marketplace`, `sell_marketplace`,
  and optional `profit_mode`, `deposit_method`, `withdraw_method`, `sell_mode`,
  `use_deposit_fee`, `use_sell_fee` and `use_withdraw_fee`. The user chooses which
  operations apply; the rates come from server configuration. The response includes
  each fee, effective buy and payout, break-even point, profit and three ROI values.

### Caching and freshness

- Price index: CSFloat cache TTL is `CSFLOAT_CACHE_TTL_SECONDS`. CSGO Market index
  cache is 300 s. An empty result is cached too, to avoid repeated identical requests.
- Variant details: cached for 600 s. They include active buy-now listings, matching
  buy orders and available sales history. If an external endpoint is restricted,
  the backend returns stored data with a safe error description.
- `listings`, `sales` and `buy_orders` have separate freshness timestamps. A failed
  refresh keeps the previous data and timestamp, so it does not extend the TTL of
  the failed part. The response includes a `components` object with `fresh`,
  `stale` or `unavailable` status for each part. Repeated requests retry only the
  stale part.

### Liquidity (beta)

This is a diagnostic estimate of quick-sell quality. It is not a sale probability
and not a profit adjustment factor:

```text
depth_score    = min(100, near_bid_depth * 10)
activity_score = min(100, sqrt(observed_sales_7d / 14) * 100)
execution      = 60% * price_retention + 40% * depth_score
score          = 40% * execution + 60% * activity_score
```

`price_retention` is the share of the minimum ask retained by the best bid.
`near_bid_depth` counts bids within 5% of the best bid. `observed_sales_7d` is the
number of observed sales in the last seven days. Bids are checked against a
specific active listing, so results for inventory items may differ because of float and stickers.

## Marketplace configuration

### CSFloat

```dotenv
CSFLOAT_API_KEY=your_key
CSFLOAT_CACHE_TTL_SECONDS=...    # price index TTL
CSFLOAT_DETAILS_TTL_SECONDS=...  # variant details TTL
```

The key is never sent to the frontend or returned by the API. The public CSFloat
price index loads separately from individual listings and can work when the
listings API is unavailable or rate-limited. A price on a card therefore does not
guarantee that a specific listing exists. Rate limiting follows the `X-RateLimit-*`
and `Retry-After` headers.

### CSGO Market

`backend/app/csgomarket.py` loads the public USD best-offers price list without an
API key and normalizes it to the shared `price_cents` / `quantity` format. Private
methods add listings and the order book. Sales history comes from public static JSON.

```dotenv
CSGOMARKET_API_KEY=your_key
CSGOMARKET_MAX_REQUESTS_PER_SECOND=0.5
```

A process-wide limiter spaces private calls at least 2.01 s apart. The rate is
capped at 0.5 requests/s (30 per minute), even if a higher value is set. The key is
never returned to clients or included in error messages. `extra.stickers` is stored
as a list of Steam class IDs. The official sticker catalog uses a different ID
system, so it is not used for unverified name or image matching.

### Checking keys

```bash
python -m backend.app.check_marketplace_keys
```

This sends one small read-only request per marketplace.

## Configuration

Catalog sources can be changed with `CATALOG_SOURCE_URL`,
`CATALOG_GROUPED_SOURCE_URL` and `CATALOG_EXTRA_SOURCE_BASE_URL`. The English
catalog is used on purpose, because its `market_hash_name` values match marketplace
search exactly. After upgrading from a skins-only version, run
`docker compose run --rm catalog-seed` again.

Other settings are in `.env.example`.

## Development and tests

Backend tests:

```bash
python -m pip install -r backend/requirements-dev.txt   # Windows: py -m pip ...
python -m pytest                                        # Windows: py -m pytest
```

Frontend (from `frontend-react`):

```bash
npm ci
npm run dev
npm test
npm run build
```

For local development the backend runs in API-only mode, and Vite proxies `/api`
to `http://127.0.0.1:8005`. Run each process in its own terminal:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8005 --reload
cd frontend-react && npm run dev
```

With `TRUE_ROI_FRONTEND_MODE=static`, the backend serves only `frontend-react/dist`
and fails with a clear error if the React bundle has not been built. The Docker
image sets this mode automatically.

To check sticker and charm support:

```bash
python -m pytest tests/test_listing_attachment_capabilities.py -q
```

This test confirms the boolean `has_stickers` / `has_charm` filters for attachments
inside a listing, and that there is no filter for a specific attachment name or ID.
Standalone sticker and charm items are available through catalog search. Behavior
depends on marketplace capabilities; CSGO Market does not provide charm data.
The frontend test `frontend-react/src/shared/api/endpoints.test.ts` checks that
these filters are passed through the API client.
