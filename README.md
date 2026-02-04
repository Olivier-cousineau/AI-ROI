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
    "market": {"amazon_price": 349.99, "ebay_price": 329.99, "match_confidence": 0.8},
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

Cet endpoint ne fait aucun lookup externe. Il normalise le titre, extrait des signaux (marque, modèle, taille, etc.)
et renvoie des requêtes génériques pour Amazon/eBay ainsi qu'une confiance heuristique.

## GitHub Actions: recompute ROI

### CI (tests)

Le workflow `CI` lance les tests à chaque push ou pull request sur `main`.

### Recompute ROI

Le workflow `Recompute ROI` exécute `scripts/recompute_roi.py` via cron (`5 8 * * *`) et manuel
(`workflow_dispatch`). Il lit `input/deals.sample.json`, calcule les ROI, écrit
`output/marketplace.json`, puis commit/push le fichier seulement en cas de changement
(commit avec `[skip ci]`).

Pour déclencher manuellement: GitHub > Actions > Recompute ROI > Run workflow.

## Output principal

Le fichier principal généré par le pipeline est `output/marketplace.json`.

Exemple de commande:

```bash
python scripts/recompute_roi.py --input input/deals.sample.json --output output/marketplace.json --top 300
```
