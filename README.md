# AI-ROI

Moteur ROI pour EconoPlus, basé sur FastAPI et Python 3.11+.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```bash
uvicorn main:app --reload
```

## Endpoints

### POST /v1/compute-roi

```bash
curl -X POST http://127.0.0.1:8000/v1/compute-roi \
  -H "Content-Type: application/json" \
  -d '{
    "deal": {"title": "Aspirateur", "price_sale": 199.99, "price_regular": 799.99, "source": "Canadian Tire"},
    "market": {"amazon_price": 349.99, "ebay_price": 329.99},
    "keepa": {"sales_per_month": 25, "avg_price": 339.99, "rank": 12000}
  }'
```

### POST /v1/match

```bash
curl -X POST http://127.0.0.1:8000/v1/match \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Aspirateur Robot", "brand": "EconoPlus", "sku": "EP-123", "upc": "123456789012"
  }'
```
