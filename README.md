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

#### Mode test (une seule ville)

Pour réduire la charge (ex: API eBay), définir une seule ville dans le workflow `Recompute ROI`:

```bash
CT_STORE_FOLDER="0271-st-jerome-qc"
MAX_MARKETPLACE_ITEMS=50
```

Laisser `CT_STORE_FOLDER` vide pour traiter toutes les villes. Si `CT_STORE_FOLDER` est défini,
le workflow limite automatiquement les items marketplace (par défaut 50, sinon 25).

Pour fusionner une seule ville côté script:

```bash
python scripts/merge_all_stores.py --store-only 0271-st-jerome-qc
```

Variables d'environnement utiles:

- `MAX_MARKETPLACE_ITEMS` (défaut: 25)
- `EBAY_CONCURRENCY` (défaut: 1)
- `EBAY_MIN_DELAY_MS` (défaut: 1200)
- `EBAY_ACCESS_TOKEN` (optionnel, prioritaire pour `/api/ebay/item`; sinon rafraîchissement via `.cache/ebay_token.json`)
- `EBAY_ITEM_CACHE_DIR` (défaut: `/tmp/ai_roi_ebay_item_cache`)
- `AI_ROI_RESULTS_PATH` (défaut: `output/roi_results.json`, utilisé par `/api/ai-roi/results`)

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
    "key": "ct|pn:123456",
    "title_hint": "ProForm 550R",
    "amazon": { "asin": "B0XXXX", "price": 349.99, "match_confidence": 0.85 },
    "ebay": { "price": 329.99 },
    "keepa": { "sales_per_month": 25, "avg_price": 339.99, "rank": 12000 },
    "notes": "Modèle proche de la série 550R."
  }
]
```

### Comment déterminer la clé

- Si le deal a un part number: `ct|pn:<PART_NUMBER>`
- Sinon, si une URL est présente: `ct|url:<URL>`
- Sinon: `ct|title:<titre_normalisé>` (fallback automatisé côté script, basé sur la normalisation du titre)

Le part number est extrait automatiquement depuis plusieurs champs possibles (ex: `partNumber`,
`itemNumber`, `productNumber`, etc.). Si aucun part number n'est détecté, le script utilise l'URL
ou le titre normalisé.

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
