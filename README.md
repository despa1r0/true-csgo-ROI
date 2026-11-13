# trueROI

Compare Counter-Strike 2 item prices across marketplaces and see the real
profit after fees.

- **Catalog** — local search over every tradable CS2 item ([ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API)).
- **Prices** — lowest ask, listings, buy orders and sales history per marketplace.
- **Profit** — server-side ROI with deposit, sell and withdrawal fees.
- **Calculator** — manual buy and sell prices with the same fee rules.

Stack: FastAPI, PostgreSQL, React + TypeScript + Vite, Docker Compose.

## Marketplaces

| Marketplace | Buy | Sell | Source | Needs |
| --- | :-: | :-: | --- | --- |
| CSFloat | ✓ | ✓ | official API | `CSFLOAT_API_KEY` |
| CSGO Market | ✓ | ✓ | official API | `CSGOMARKET_API_KEY` |
| White.Market | ✓ | ✓ | partner GraphQL API | `WHITEMARKET_PARTNER_TOKEN` |
| DMarket | ✓ | ✓ | official Trading API | nothing for prices; keys for listings and history |
| CS.MONEY | ✓ | ✓ | background browser worker | VPN recommended |
| Tradeit.gg | ✓ | — | store JSON (undocumented) | nothing |

Details: [CS.MONEY](docs/CSMONEY.md) · [DMarket](docs/DMARKET.md) · [Tradeit.gg](docs/TRADEIT.md)

## Run

```bash
cp .env.example .env        # add CSFLOAT_API_KEY and CSGOMARKET_API_KEY
docker compose up --build
```

Open <http://localhost:8005>. The first start imports the catalog and takes a few
minutes. On Windows, `.\start.ps1` does the same.

```bash
docker compose down         # stop, keep the database
docker compose down -v      # stop and delete the database
```

API reference: <http://localhost:8005/docs>.

## Develop

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest

cd frontend-react
npm ci
npm run dev                 # http://localhost:5173, proxies /api to :8005
npm test
npm run build
```

Browser checks against a running `npm run dev` (Playwright and Edge, fixture data):

```bash
python scripts/qa/check-frontend.py --output qa-output    # navigation, calculator layout
python scripts/qa/check-alignment.py --output qa-output   # centring and alignment
```

## How profit is calculated

All money is integer cents.

```text
effective_buy    = buy_price + deposit_fee
effective_payout = sell_price - sell_fee - withdraw_fee
profit           = effective_payout - effective_buy
ROI              = profit / effective_buy × 100
```

| Mode | Fees applied | Sell price |
| --- | --- | --- |
| Raw | none | lowest ask |
| Smart | deposit, sell, withdraw | lowest ask |
| Enhanced | sell, withdraw | lowest ask |
| Quick flip | sell, withdraw, optional deposit | best buy order |

Fee rates live in `backend/app/marketplaces_fees.py` and cannot be changed from
the browser. A lowest ask is a listing price, not a guaranteed sale.

## Add a marketplace

1. Adapter in `backend/app/marketplaces/` — talks to the provider, returns cents.
2. Data module and router — cache, `/api/skins/{id}/market/{name}` routes.
3. Entry in `MARKETPLACES` (`marketplaces_fees.py`) — capabilities and fees.
4. Reader in `market_comparison.py`.

The interface reads `/api/marketplaces`, so it needs no changes.

## Docs

- [Project status](docs/PROJECT_STATUS_2026-11-12.md)
- [Known issues](docs/KNOWN_ISSUES.md)
- [Frontend](docs/FRONTEND.md)
- [Deployment](docs/DEPLOY.md)
