# Test run input

This folder contains a small BestBuy-like input file used when running the
`Recompute ROI` workflow in TESTRUN mode.

## How to run the workflow in TESTRUN mode

1. Open the **Recompute ROI** workflow in GitHub Actions.
2. Click **Run workflow**.
3. Set the inputs:
   - `testrun`: `true`
   - `testrun_file`: `input/testrun/deals.json`
   - `source`: `bestbuy`
   - `top`: `300`

The workflow will skip cloning EconoPlus, and it will use
`input/testrun/deals.json` as the deals input.

## Notes

- The input file includes both top-level deal fields (for `build_market_ready.py`)
  and nested `deal/market/keepa` blocks (for `recompute_roi.py`).
- The workflow continues to emit `output/marketplace.json` and
  `output/roi_results.json` as usual.
