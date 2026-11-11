"""Record this week's hydrant/valve maintenance counts in data/history.json.
Run by .github/workflows/snapshot.yml (weekly), or by hand: python scripts/snapshot.py
Uses only the Python standard library."""
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone

LAYERS = {
    "hydrants": "https://services3.arcgis.com/3WQsNEWSVGwHihXP/arcgis/rest/services/Water_Management_Layer_2_view/FeatureServer/1",
    "valves":   "https://services3.arcgis.com/3WQsNEWSVGwHihXP/arcgis/rest/services/Water_Management_Layer_2_view/FeatureServer/2",
}
DATE_FIELD, DUE_SOON_YEARS, CYCLE_YEARS = "lastmaint", 4, 5
YEAR_MS = 365.25 * 86400000
HISTORY = os.path.join(os.path.dirname(__file__), "..", "data", "history.json")


def get(url, **params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=60) as r:
        j = json.load(r)
    if "error" in j:
        raise RuntimeError(f"{url}: {j['error'].get('message')}")
    return j


def counts(url, now_ms):
    t = {"current": 0, "due": 0, "overdue": 0, "none": 0}
    offset = 0
    while True:
        j = get(url + "/query", where="1=1", outFields=DATE_FIELD, returnGeometry="false",
                orderByFields="OBJECTID", resultOffset=offset, resultRecordCount=1000, f="json")
        feats = j.get("features", [])
        for f in feats:
            last = f["attributes"].get(DATE_FIELD)
            if last is None:
                t["none"] += 1
                continue
            yrs = (now_ms - last) / YEAR_MS
            t["current" if yrs < DUE_SOON_YEARS else "due" if yrs < CYCLE_YEARS else "overdue"] += 1
        if not j.get("exceededTransferLimit") or not feats:
            return t
        offset += len(feats)


now = datetime.now(timezone.utc)
point = {"date": now.strftime("%Y-%m-%d")}
for key, url in LAYERS.items():
    try:
        point[key] = counts(url, now.timestamp() * 1000)
    except Exception as e:  # keep the other layer if one fails
        print(f"{key}: skipped ({e})")
if len(point) == 1:
    raise SystemExit("No layers could be read; history not updated.")

history = json.load(open(HISTORY)) if os.path.exists(HISTORY) else []
history = [p for p in history if p.get("date") != point["date"]] + [point]
json.dump(history, open(HISTORY, "w"), indent=1)
print(json.dumps(point))
