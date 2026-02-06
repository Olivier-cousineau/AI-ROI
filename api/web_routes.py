"""Web/API routes for AI-ROI result exploration."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

from lib.enrich.ebay_item_details import fetch_ebay_item_details

router = APIRouter()
DEFAULT_RESULTS_PATH = Path(os.getenv("AI_ROI_RESULTS_PATH", "output/roi_results.json"))


@router.get("/api/ebay/item")
def ebay_item_endpoint(item_id: str = Query(..., min_length=3)) -> JSONResponse:
    """Fetch and cache eBay item details by item_id."""
    payload = fetch_ebay_item_details(item_id)
    status_code = 200 if payload.get("ok") else 400
    error = payload.get("error")
    if error == "rate_limited":
        status_code = 429
    elif error in {"request_failed", "ebay_error"}:
        status_code = 502
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/api/ai-roi/results")
def ai_roi_results_endpoint() -> JSONResponse:
    """Return the latest computed AI-ROI results JSON payload."""
    if not DEFAULT_RESULTS_PATH.exists():
        return JSONResponse(status_code=404, content={"ok": False, "message": "ROI results file not found."})

    with DEFAULT_RESULTS_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return JSONResponse(status_code=500, content={"ok": False, "message": "Invalid ROI results format."})
    payload["ok"] = True
    return JSONResponse(status_code=200, content=payload)


@router.get("/ai-roi", response_class=HTMLResponse)
def ai_roi_page() -> str:
    """Render a lightweight AI-ROI visual match page."""
    return """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>AI_ROI Matches</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    .wrap { max-width: 1200px; margin: 24px auto; padding: 0 16px; }
    .row { border: 1px solid #334155; border-radius: 12px; margin-bottom: 12px; padding: 12px; background: #111827; }
    .cards { display: grid; grid-template-columns: 1fr; gap: 10px; }
    @media (min-width: 960px) { .cards { grid-template-columns: 1fr 1fr; } }
    .card { border: 1px solid #334155; border-radius: 10px; padding: 10px; background: #0b1220; }
    .card img { width: 100%; max-height: 210px; object-fit: contain; border-radius: 8px; background: #020617; }
    .title { font-size: 14px; line-height: 1.25; min-height: 36px; margin: 8px 0; }
    .price { font-weight: 700; font-size: 18px; }
    button, .btn { display: inline-block; margin-top: 8px; background: #2563eb; color: white; border: none; border-radius: 8px; padding: 8px 10px; text-decoration: none; cursor: pointer; }
    .badge { display:inline-block; border-radius:999px; padding:2px 8px; font-size:12px; font-weight:700; margin-left:8px; }
    .HIGH { background:#166534; }
    .MED { background:#92400e; }
    .LOW { background:#991b1b; }
    .why { font-size: 12px; color: #93c5fd; margin-top: 6px; }
    .error { color: #fca5a5; font-size: 12px; margin-top: 6px; }
  </style>
</head>
<body>
<div class=\"wrap\"><h1>AI_ROI • CT vs eBay</h1><div id=\"list\"></div></div>
<script>
const MAX_AUTO_FETCH = Number(new URLSearchParams(location.search).get('autoTopN') || 0);
const state = {};

const toPrice = (value) => (typeof value === 'number' ? `$${value.toFixed(2)}` : 'N/A');
const esc = (v) => (v || '').toString().replace(/[&<>\"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));

function whyMatched(signals) {
  if (!signals) return 'No match signals available';
  const bits = [];
  if (signals.model_match) bits.push('Model match');
  if (signals.part_number_match) bits.push('Part# match');
  if (signals.brand_match) bits.push('Brand match');
  if (typeof signals.title_similarity === 'number') bits.push(`${signals.title_similarity.toFixed(2)} title sim`);
  return bits.length ? bits.join(' • ') : 'No strong signals';
}

async function fetchEbay(row, idx) {
  const itemId = row.ebay_match && row.ebay_match.item_id;
  if (!itemId) return;
  state[idx] = {loading: true}; render(window.rows);
  const res = await fetch(`/api/ebay/item?item_id=${encodeURIComponent(itemId)}`);
  const payload = await res.json();
  if (!payload.ok) {
    state[idx] = {loading:false, error: payload.message || payload.error || 'Fetch failed'}; render(window.rows); return;
  }
  row.ebay_match = {...row.ebay_match, ...(payload.item || {})};
  state[idx] = {loading:false, error: payload.warning || null};
  render(window.rows);
}

function rowHtml(row, idx) {
  const match = row.ebay_match || null;
  const st = state[idx] || {};
  const confidence = match && match.match_confidence ? match.match_confidence : 'LOW';
  const badge = `<span class=\"badge ${confidence}\">${confidence}</span>`;
  const ct = `<div class=\"card\"><img src=\"${esc(row.image || '')}\" alt=\"CT\" /><div class=\"title\">${esc(row.title)}</div><div class=\"price\">${toPrice(row.price_sale)}</div><a class=\"btn\" href=\"${esc(row.url || '#')}\" target=\"_blank\" rel=\"noreferrer\">Open CT</a></div>`;
  const eb = `<div class=\"card\"><img src=\"${esc(match && match.image || '')}\" alt=\"eBay\" /><div class=\"title\">${esc(match && match.title || 'No eBay details')}</div><div class=\"price\">${toPrice(match && match.price)}</div><div>${badge}</div><div class=\"why\">Why matched: ${whyMatched(match && match.match_signals)}</div>${match && match.item_web_url ? `<a class=\"btn\" href=\"${esc(match.item_web_url)}\" target=\"_blank\" rel=\"noreferrer\">Open eBay</a>` : `<button onclick=\"fetchEbay(window.rows[${idx}], ${idx})\" ${st.loading ? 'disabled' : ''}>${st.loading ? 'Loading…' : 'Fetch eBay details'}</button>`}${st.error ? `<div class=\"error\">${esc(st.error)}</div>` : ''}</div>`;
  return `<div class=\"row\"><div class=\"cards\">${ct}${eb}</div></div>`;
}

function render(rows) {
  window.rows = rows;
  document.getElementById('list').innerHTML = rows.map(rowHtml).join('');
}

(async function init(){
  const res = await fetch('/api/ai-roi/results');
  const payload = await res.json();
  const rows = (payload && payload.results) || [];
  render(rows);
  if (MAX_AUTO_FETCH > 0) {
    rows.slice(0, MAX_AUTO_FETCH).forEach((row, i) => {
      if (row.ebay_match && row.ebay_match.item_id && !row.ebay_match.item_web_url) fetchEbay(row, i);
    });
  }
})();
</script>
</body>
</html>
    """
