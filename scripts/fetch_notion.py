"""從 Notion 抓資料，只留可以公開的欄位，寫成 data/models.json 和 data/inventory.json。

在 GitHub Actions 每天跑一次（見 .github/workflows/update.yml），需要環境變數 NOTION_TOKEN。
只用 Python 標準函式庫，不用另外安裝套件。

公開規則（改這裡之前先想清楚）：
- 不輸出車牌、車主、電話、證件、收購價、成交價、差價、筆數。
- 場內車只列「盤點＝在場內」或「還沒盤點但從車場 App 新進場」的車；待盤點、不在場內、取消的不列。
- 測試車、範例車牌不列。
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.notion.com/v1"
VERSION = "2025-09-03"

DS_CASES = "cd123ed8-08ff-413e-b942-8b44cd167536"   # 案件
DS_MODELS = "2e8cbc6b-a619-45c7-a8cf-e69a069b2e19"  # 車款圖鑑
DS_MARKET = "41f27874-3256-81d4-b8e7-000bd7a1b2b7"  # 車款行情（熱銷分析）
DS_BRANDS = "5d1e7a8d-402f-4aca-ab85-a77023cfd693"  # 品牌

IN_YARD = ["場內待拆", "拆解中", "待出口"]
TEST_PLATE = re.compile(r"^(TEST|示範|範例)|^ABC-?1234$", re.I)
TEST_NOTE = re.compile(r"虛構|測試|範例|示範")
UNSURE = re.compile(r"確認|推測")
TW = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- Notion API ----------

def api(path, body=None):
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        sys.exit("沒有 NOTION_TOKEN，停止。")
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body or {}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        sys.exit(f"Notion API 錯誤 {e.code} {path}：{detail}")


def query_all(ds_id, flt=None):
    rows, cursor = [], None
    while True:
        body = {"page_size": 100}
        if flt:
            body["filter"] = flt
        if cursor:
            body["start_cursor"] = cursor
        res = api(f"/data_sources/{ds_id}/query", body)
        rows.extend(res.get("results", []))
        if not res.get("has_more"):
            return rows
        cursor = res.get("next_cursor")


# ---------- 讀欄位 ----------

def val(page, name):
    """把 Notion 屬性轉成簡單的值。不認得的型別回傳 None。"""
    p = (page.get("properties") or {}).get(name)
    if not p:
        return None
    t = p.get("type")
    v = p.get(t)
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v or []).strip() or None
    if t in ("select", "status"):
        return v.get("name") if v else None
    if t in ("number", "url", "checkbox"):
        return v
    if t == "date":
        return v.get("start") if v else None
    if t == "relation":
        return [x.get("id") for x in v or []]
    if t == "unique_id":
        if not v or v.get("number") is None:
            return None
        return f"{v['prefix']}-{v['number']}" if v.get("prefix") else str(v["number"])
    if t == "formula":
        ft = v.get("type")
        out = v.get(ft)
        if ft == "date":
            return out.get("start") if out else None
        if isinstance(out, str):
            return out.strip() or None
        return out
    return None


def norm_id(x):
    return (x or "").replace("-", "").lower()


def file_from_commons(url):
    """維基共享資源的 File: 網址 → 檔名（未編碼）。不是的話回傳 None。"""
    if not url or "/wiki/File:" not in url:
        return None
    return urllib.parse.unquote(url.split("/wiki/File:", 1)[1].split("#")[0].split("?")[0])


def clean_cc(cc):
    if not cc or UNSURE.search(cc):
        return None
    return cc.strip()


def clean_alias(alias):
    if not alias or UNSURE.search(alias):
        return None
    return alias.strip()


def tier(n, high=15, mid=5):
    if n >= high:
        return 2
    if n >= mid:
        return 1
    return 0


# ---------- 組資料 ----------

def build_models(brand_pages, model_pages, market_pages):
    brands = {}
    for b in brand_pages:
        brands[norm_id(b["id"])] = {
            "brand": val(b, "品牌"),
            "brand_zh": val(b, "中文名稱"),
            "group": val(b, "車系"),
        }

    counts = {}
    names = {val(m, "車款") for m in model_pages}
    for row in market_pages:
        name = val(row, "車款") or ""
        if name not in names:   # 「LEXUS RX」「SUBARU XV」這種，去掉品牌字再對一次
            rest = name.split(" ", 1)[-1]
            if rest in names:
                name = rest
        kind = val(row, "類別")
        c = counts.setdefault(name, {"整車": 0, "引擎": 0})
        if kind in c:
            c[kind] += int(val(row, "成交筆數") or 0)

    out = []
    for m in model_pages:
        name = val(m, "車款")
        how = val(m, "怎麼認") or ""
        if not name or "寫錯" in how:
            continue
        rel = val(m, "品牌") or []
        b = brands.get(norm_id(rel[0])) if rel else None
        c = counts.get(name, {"整車": 0, "引擎": 0})
        total = c["整車"] + c["引擎"]
        out.append({
            "name": name,
            "brand": (b or {}).get("brand"),
            "brand_zh": (b or {}).get("brand_zh"),
            "group": (b or {}).get("group"),
            "type": val(m, "車型"),
            "alias": clean_alias(val(m, "別名")),
            "cc": clean_cc(val(m, "排氣量")),
            "photo": file_from_commons(val(m, "照片來源")),
            "photo_page": val(m, "照片來源"),
            "tier": tier(total),
            "export_whole": tier(c["整車"]),
            "export_engine": tier(c["引擎"]),
            "_sort": total,
        })
    out.sort(key=lambda x: (-x["_sort"], x["name"]))
    for x in out:
        del x["_sort"]
    return out


def guess_model(text, models):
    """從「Toyota Altis 2003」這種文字認車款。ALTIS 跟 COROLLA 同時出現時算 ALTIS。"""
    if not text:
        return None
    low = text.lower()
    hits = []
    for m in models:
        for key in [m["name"]] + ([m["alias"]] if m.get("alias") else []):
            k = key.lower()
            if len(k) >= 2 and k in low:
                hits.append((len(k), m["name"]))
    if not hits:
        return None
    names = {h[1] for h in hits}
    if "ALTIS" in names:
        return "ALTIS"
    return max(hits)[1]


def build_inventory(case_pages, models):
    by_name = {m["name"]: m for m in models}
    parts, export = [], []
    for p in case_pages:
        plate = val(p, "車牌") or ""
        note = val(p, "備註") or ""
        if TEST_PLATE.search(plate) or TEST_NOTE.search(note):
            continue
        if val(p, "盤點") in ("待盤點", "不在場內") or val(p, "目前關卡") == "取消":
            continue
        loc = val(p, "車輛位置")
        if loc not in IN_YARD:
            continue

        spec = val(p, "車種年份") or ""
        m = re.search(r"內勤確認車型[:：]\s*([^｜|]+)", note)
        intake = m.group(1).strip() if m else ""
        model = val(p, "車款") or val(p, "車款（選單）") or guess_model(spec, models) or guess_model(intake, models)
        if model and model.startswith("（"):   # 「（認不出）」
            model = guess_model(spec, models) or guess_model(intake, models)
        year = val(p, "年份")
        if not year:
            y = re.search(r"(19|20)\d{2}", spec + " " + intake)
            year = int(y.group(0)) if y else None
        info = by_name.get(model or "", {})

        ref = val(p, "場內編號")
        ref = str(int(ref)) if isinstance(ref, (int, float)) else val(p, "案件編號")
        got = val(p, "收車日") or val(p, "接案日")

        car = {
            "ref": ref,
            "model": model,
            "brand": val(p, "品牌") if (val(p, "品牌") or "").isascii() and val(p, "品牌") else info.get("brand"),
            "year": int(year) if year else None,
            "type": info.get("type"),
            "color": val(p, "顏色"),
            "condition": val(p, "車況"),
            "since": got[:7] if got else None,
        }
        kind = val(p, "類型") or ""
        ok_export = (val(p, "能不能外銷") or "").startswith("✓")
        if kind == "外銷出口" or loc == "待出口" or (kind.startswith("自購") and ok_export):
            export.append(car)
        else:
            parts.append(car)
    key = lambda c: (c["since"] or "", c["ref"] or "")
    parts.sort(key=key, reverse=True)
    export.sort(key=key, reverse=True)
    return parts, export


def main():
    brand_pages = query_all(DS_BRANDS)
    model_pages = query_all(DS_MODELS)
    market_pages = query_all(DS_MARKET)
    case_filter = {"and": [
        {"property": "盤點", "select": {"does_not_equal": "待盤點"}},
        {"property": "盤點", "select": {"does_not_equal": "不在場內"}},
        {"property": "目前關卡", "status": {"does_not_equal": "取消"}},
        {"or": [{"property": "車輛位置", "select": {"equals": v}} for v in IN_YARD]},
    ]}
    case_pages = query_all(DS_CASES, case_filter)

    models = build_models(brand_pages, model_pages, market_pages)
    parts, export = build_inventory(case_pages, models)
    now = datetime.now(TW).isoformat(timespec="minutes")

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "models.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": now, "models": models}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "data", "inventory.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": now, "parts": parts, "export": export}, f, ensure_ascii=False, indent=1)
    print(f"車款 {len(models)}、零件車 {len(parts)}、外銷車 {len(export)}，更新時間 {now}")


if __name__ == "__main__":
    main()
