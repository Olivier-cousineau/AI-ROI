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
(`workflow_dispatch`). Il fusionne d'abord les liquidations Canadian Tire avec les enrichissements
manuels, calcule les ROI, écrit `output/marketplace.json`, puis commit/push les fichiers mis à jour
en cas de changement (commit avec `[skip ci]`).

Pour déclencher manuellement: GitHub > Actions > Recompute ROI > Run workflow.

## Output principal

Le fichier principal généré par le pipeline est `output/marketplace.json`.

Exemple de commande:

```bash
python scripts/merge_enrichment.py \
  --deals input/canadiantire_all_liquidations.json \
  --enrichment input/manual_enrichment.json \
  --out input/market_ready.json

python scripts/recompute_roi.py --input input/market_ready.json --output output/marketplace.json --top 300
```

## Enrichissement manuel (Step 2)

Le fichier `input/manual_enrichment.json` est une liste d'objets simples à éditer à la main.
Chaque entrée est jointe aux deals Canadian Tire via une clé `key`.

Exemple (voir `input/manual_enrichment.sample.json`) :

```json
[
  {
    "key": "ct|sku:123456",
    "title_hint": "ProForm 550R",
    "amazon": { "asin": "B0XXXX", "price": 349.99, "match_confidence": 0.85 },
    "ebay": { "price": 329.99 },
    "keepa": { "sales_per_month": 25, "avg_price": 339.99, "rank": 12000 },
    "notes": "Modèle proche de la série 550R."
  }
]
```

### Comment déterminer la clé

- Si le deal a un SKU: `ct|sku:<SKU>`
- Sinon, si une URL est présente: `ct|url:<URL>`
- Sinon: `ct|title:<titre_normalisé>` (fallback automatisé côté script)

### Lancement local

```bash
python scripts/merge_enrichment.py \
  --deals input/canadiantire_all_liquidations.json \
  --enrichment input/manual_enrichment.json \
  --out input/market_ready.json

python scripts/recompute_roi.py --input input/market_ready.json --output output/marketplace.json --top 300
```

Le fichier `output/marketplace.json` se remplit progressivement au fur et à mesure que
`input/manual_enrichment.json` grandit.
