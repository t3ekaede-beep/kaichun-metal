"""用 data/*.json 和 src/*.html 產生整個網站（寫到儲存庫根目錄）。

只用 Python 標準函式庫。改網頁文字：改 src/ 底下的檔案，再跑 python scripts/build.py。
"""

import html
import json
import os
import re
import urllib.parse
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://t3ekaede-beep.github.io/kaichun-metal/"
LINE_ID = "@375juggy"
LINE_ADD = "https://line.me/R/ti/p/" + LINE_ID
MAP = ("https://www.google.com/maps/search/?api=1&query=%E9%96%8B%E7%BE%A4%E9%87%91%E5%B1%AC%E8%A1%8C"
       "&query_place_id=ChIJ3XGffF9tbjQRUe3NIeFh1gE")
# 訪客統計（GoatCounter，不用 cookie、不記個資）。到 goatcounter.com 註冊後，把網站代碼填在這裡；
# 空字串＝完全不載入統計，LINE 按鈕的計數標記也不會有作用。
GOATCOUNTER = os.environ.get("GOATCOUNTER_CODE", "")
# 詢價格式：客戶須知頁顯示的內容、一鍵 LINE 帶入的內容，都用這一份，改一處就好
PARTS_FMT = ["【詢價】", "車款＋排氣量＋年份：{car}", "要什麼零件：", "數量：",
             "零件編號或照片：有的話一起傳", "自取或寄送：", "怎麼稱呼："]
MIN_SHOW = 5          # 一類車少於這個數字，就不列清單，改顯示「整理中」
HOME_INV = 4          # 首頁顯示幾台
HOME_MODELS = 14      # 首頁顯示幾款（電腦版剛好兩排）
TYPES = ["房車", "掀背", "休旅", "多人座", "廂型車", "貨車"]
TYPE_EN = {"房車": "Sedan", "掀背": "Hatchback", "休旅": "SUV", "多人座": "MPV", "廂型車": "Van", "貨車": "Truck"}
TIER = {2: "常有", 1: "偶爾有"}
TIER_EN = {2: "Often", 1: "Sometimes"}

e = lambda s: html.escape(str(s), quote=True) if s is not None else ""


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def line_msg(text):
    return f"https://line.me/R/oaMessage/{urllib.parse.quote(LINE_ID)}/?{urllib.parse.quote(text)}"


def parts_fmt(car=""):
    return "\n".join(PARTS_FMT).replace("{car}", car)


def photo_url(file, width=500):   # 500 是維基的標準縮圖尺寸，快取命中比較快
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(file)}?width={width}"


SIL = '<svg class="sil" viewBox="0 0 300 110" aria-hidden="true"><use href="#sil"/></svg>'


def photo(m, alt, root=""):
    if m and m.get("photo"):
        return (f'<img src="{e(photo_url(m["photo"]))}" alt="{e(alt)}" loading="lazy" decoding="async" '
                f'width="500" height="375" referrerpolicy="no-referrer">')
    return SIL


def nice_time(iso, en=False):
    try:
        d = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    if en:
        return d.strftime("%d %b %Y, %H:%M") + " (Taiwan time)"
    return f"{d.year} 年 {d.month} 月 {d.day} 日 {d.hour:02d}:{d.minute:02d}"


def en_name(m):
    """英文頁用的車款名：中文名就換成別名（例如 普羅密歐 → PREMIO）。"""
    name = m["name"]
    if not name.isascii() and m.get("alias") and m["alias"].isascii():
        name = m["alias"]
    if not name.isascii():
        return None
    brand = (m.get("brand") or "").title() if m.get("brand") not in ("BMW", "VW") else m.get("brand")
    return f"{brand} {name}".strip()


# ---------- 卡片 ----------

def model_card(m):
    alias = f'<small>{e(m["alias"])}</small>' if m.get("alias") else ""
    meta = " ・ ".join(x for x in [m.get("brand_zh") or m.get("brand"), m.get("type"), m.get("cc")] if x)
    tier = f'<span class="tier">{TIER[m["tier"]]}</span>' if m.get("tier") in TIER else ""
    credit = f'<a class="credit-link" href="{e(m["photo_page"])}" rel="nofollow">出處</a>' if m.get("photo") else ""
    search = " ".join(x for x in [m["name"], m.get("alias"), m.get("brand"), m.get("brand_zh")] if x).lower()
    msg = line_msg(parts_fmt(f"{m['name']}　年份："))
    return (f'<article class="card" data-search="{e(search)}" data-brand="{e(m.get("brand"))}" data-type="{e(m.get("type"))}">'
            f'<div class="ph">{photo(m, m["name"])}{tier}</div>'
            f'<div class="cb"><h3>{e(m["name"])}{alias}</h3><div class="meta">{e(meta)}</div>'
            f'<div class="acts"><a class="btn sm" href="{e(msg)}">LINE 問零件</a>{credit}</div></div></article>')


def car_card(c, models, kind):
    m = models.get(c.get("model") or "")
    title = " ".join(str(x) for x in [c.get("model") or "車款確認中", c.get("year")] if x)
    meta = " ・ ".join(x for x in [c.get("brand"), c.get("type"), c.get("color"), c.get("condition")] if x)
    since = f'{int(c["since"][5:7])} 月進場' if c.get("since") else ""
    ask = "的零件，需要：" if kind == "parts" else "，想整台買"
    msg = line_msg(f"我想問場內車源 {c.get('ref')}：{title}{ask}")
    search = " ".join(x for x in [c.get("model"), c.get("brand"), m and m.get("alias")] if x).lower()
    return (f'<article class="card" data-search="{e(search)}" data-brand="{e(c.get("brand"))}" data-type="{e(c.get("type"))}">'
            f'<div class="ph">{photo(m, title)}<span class="tag">{e(c.get("ref"))}</span></div>'
            f'<div class="cb"><h3>{e(title)}</h3><div class="meta">{e(meta)}</div><div class="meta">{e(since)}</div>'
            f'<div class="acts"><a class="btn sm" href="{e(msg)}">LINE 問這台</a></div></div></article>')


def empty_state(n, kind):
    what = "零件車" if kind == "parts" else "外銷整車"
    ask = line_msg("我想問有沒有這台車：車款＋年份：" if kind == "parts" else "我想問外銷整車：車款＋年份＋數量：")
    return (f'<div class="empty"><div class="big">盤點中</div><div><b>{what}清單整理中</b>'
            f'<p>場內的車正在盤點、建檔，整理好就會自動出現在這裡。現在想找車，直接用 LINE 問最快。</p>'
            f'<div class="btns"><a class="btn sm dark" href="{e(ask)}">LINE 問有沒有這台</a>'
            f'<a class="btn sm" href="models.html">看常收車款</a></div></div></div>')


def chips(values, label_all="全部"):
    out = [f'<button type="button" class="chip" data-v="{e(v)}" aria-pressed="false">{e(t)}</button>' for v, t in values]
    return "".join(out)


def filters(cars, target):
    brands = sorted({c.get("brand") for c in cars if c.get("brand")})
    types = [t for t in TYPES if any(c.get("type") == t for c in cars)]
    return (f'<div class="filters" data-target="{target}">'
            f'<div class="chips" data-key="brand" role="group" aria-label="品牌">{chips([(b, b) for b in brands])}</div>'
            f'<div class="chips" data-key="type" role="group" aria-label="車型">{chips([(t, t) for t in types])}</div></div>'
            f'<p class="count" aria-live="polite"></p>')


def inv_block(cars, models, kind):
    if len(cars) < MIN_SHOW:
        return empty_state(len(cars), kind)
    gid = f"grid-{kind}"
    return filters(cars, "#" + gid) + f'<div class="cards" id="{gid}">' + "".join(car_card(c, models, kind) for c in cars) + "</div>"


def mini(m, href, label=None):
    return (f'<a class="mini" href="{e(href)}"><div class="ph">{photo(m, m["name"])}</div>'
            f'<b>{e(label or m["name"])}</b></a>')


# ---------- 版型 ----------

SPRITE = ('<svg width="0" height="0" style="position:absolute" aria-hidden="true"><symbol id="sil" viewBox="0 0 300 110">'
          '<path fill="currentColor" d="M8 84V62q2-11 22-13l52-4 30-29q6-6 15-6h76q10 0 17 8l28 27 30 5q14 3 14 16v18z"/>'
          '<circle cx="76" cy="84" r="22" fill="currentColor"/><circle cx="234" cy="84" r="22" fill="currentColor"/></symbol></svg>')

NAV_ZH = [("index.html", "首頁"), ("inventory.html", "場內車源"), ("models.html", "常收車款"),
          ("guide.html", "客戶須知"), ("about.html", "車場介紹"), ("en/", "English")]
NAV_EN = [("#stock", "Export stock"), ("#how", "How to buy"), ("#contact", "Contact"), ("../", "中文")]


def mark_clicks(text):
    """給 LINE 連結加上點擊計數標記（有填 GoatCounter 代碼才會真的計數，沒填就是無害的屬性）。"""
    def tag(m):
        cls, href = m.group(1), m.group(2)
        if "oaMessage" in href:
            name = "line-ask-parts" if "%E3%80%90%E8%A9%A2%E5%83%B9" in href else "line-ask"
        else:
            name = "line-add"
        return f'<a {cls}data-goatcounter-click="{name}" data-goatcounter-no-session="1" href="{href}"'
    return re.sub(r'<a ((?:class="[^"]*" )?)href="(https://line\.me/[^"]*)"', tag, text)


def layout(page, body, title, desc, root, lang="zh"):
    zh = lang == "zh"
    url = BASE + ("" if page == "index.html" else page)
    nav = NAV_ZH if zh else NAV_EN
    links = "".join(
        f'<a href="{(root + h) if zh else h}"' + (' aria-current="page"' if h == page else "") + f'>{t}</a>'
        for h, t in nav)
    line_btn = mark_clicks(f'<a class="cta" href="{LINE_ADD}">{"LINE 詢價" if zh else "LINE"}</a>')
    alt = (f'<link rel="alternate" hreflang="zh-Hant-TW" href="{BASE}">'
           f'<link rel="alternate" hreflang="en" href="{BASE}en/">')
    contact = (CONTACT_ZH if zh else CONTACT_EN).replace("{{MAP}}", e(MAP)).replace("{{LINE_ADD}}", LINE_ADD)
    foot = (f'<footer class="ft"><div class="wrap"><span>開群金屬行｜高雄市阿蓮區中正路 16 巷 3-90 號</span>'
            f'<nav aria-label="頁尾">' + "".join(f'<a href="{root}{h}">{t}</a>' for h, t in NAV_ZH) + '</nav>'
            f'<span>價錢以 LINE 報價為準{"｜本站用不使用 cookie 的訪客統計" if GOATCOUNTER else ""}</span></div></footer>') if zh else (
            f'<footer class="ft"><div class="wrap"><span>Kai-Chun Metal (開群金屬行), Alian District, Kaohsiung, Taiwan</span>'
            f'<span>Prices are quoted on LINE</span></div></footer>')
    stats = (f'<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
             if GOATCOUNTER else "")
    body = mark_clicks(body + contact)
    contact = ""
    return f'''<!DOCTYPE html>
<html lang="{"zh-Hant-TW" if zh else "en"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="theme-color" content="#f6c400">
<link rel="canonical" href="{url}">{alt}
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="icon" href="{root}favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:locale" content="{"zh_TW" if zh else "en_US"}">
<meta property="og:site_name" content="開群金屬行">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@800&amp;display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/site.css">
{JSONLD if page in ("index.html", "about.html") else ""}
</head>
<body>
<a class="skip" href="#main">{"跳到內容" if zh else "Skip to content"}</a>
{SPRITE}
<header class="hdr"><div class="bar">
<a class="brand" href="{root}index.html"><span class="plate" aria-hidden="true">開</span><b>{"開群金屬行" if zh else "Kai-Chun Metal"}</b></a>
<nav class="main" aria-label="{"主選單" if zh else "Main"}">{links}</nav>
{line_btn}
</div></header>
<main id="main">
{body}
{contact}
</main>
{foot}
<script src="{root}assets/site.js" defer></script>
{stats}
</body>
</html>
'''


CONTACT_ZH = '''<section class="band contact" id="contact"><div class="wrap sec">
  <div>
    <h2>用 LINE 問最快</h2>
    <p class="lead">照客戶須知的格式傳，我們看得懂就能直接報價。現場在拆車的時候常常接不到電話，LINE 留言不會漏掉。</p>
    <div class="btns" style="margin-top:18px"><a class="btn dark" href="{{LINE_ADD}}">加 LINE 好友</a></div>
  </div>
  <div class="cgrid">
    <div><small>LINE ID</small><span>@375juggy</span></div>
    <div><small>營業時間</small><span class="nw">週一到週五 8:00–17:00</span><br><span class="nw">週六 10:00–17:00</span><br>中午 12:00–13:00 休息，週日公休</div>
    <div><small>地址</small><span>高雄市阿蓮區中正路 16 巷 3-90 號</span><br><a href="{{MAP}}">用 Google 地圖導航</a></div>
    <div><small>付款</small><span>現金、轉帳</span><br>可以開發票</div>
  </div>
</div></section>'''

CONTACT_EN = '''<section class="band contact" id="contact"><div class="wrap sec">
  <div>
    <h2>Contact us on LINE</h2>
    <p class="lead">Send the model, year, quantity, and whether you want whole cars or engines.</p>
    <div class="btns" style="margin-top:18px"><a class="btn dark" href="{{LINE_ADD}}">Add us on LINE</a></div>
  </div>
  <div class="cgrid">
    <div><small>LINE ID</small><span>@375juggy</span></div>
    <div><small>Opening hours (GMT+8)</small><span class="nw">Mon–Fri 8:00–17:00</span><br><span class="nw">Sat 10:00–17:00</span><br>Lunch break 12:00–13:00, closed Sunday</div>
    <div><small>Address</small><span>No. 3-90, Ln. 16, Zhongzheng Rd., Alian Dist., Kaohsiung City 822, Taiwan</span><br><a href="{{MAP}}">Open in Google Maps</a></div>
    <div><small>Yard</small><span>Alian, Kaohsiung</span><br>Visits by appointment</div>
  </div>
</div></section>'''

JSONLD = ('<script type="application/ld+json">' + json.dumps({
    "@context": "https://schema.org", "@type": "AutoPartsStore", "name": "開群金屬行", "url": BASE,
    "image": BASE + "og.png",
    "description": "高雄阿蓮的汽車回收場：中古零件、報廢車收購、機車殼廢料收購、外銷整車與引擎。",
    "address": {"@type": "PostalAddress", "streetAddress": "阿蓮里中正路16巷3-90號", "addressLocality": "阿蓮區",
                "addressRegion": "高雄市", "postalCode": "822", "addressCountry": "TW"},
    "geo": {"@type": "GeoCoordinates", "latitude": 22.882908, "longitude": 120.3438987},
    "hasMap": MAP.replace("&amp;", "&"),
    "openingHoursSpecification": [
        {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "opens": "08:00", "closes": "12:00"},
        {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "opens": "13:00", "closes": "17:00"},
        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Saturday", "opens": "10:00", "closes": "12:00"},
        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Saturday", "opens": "13:00", "closes": "17:00"}],
    "paymentAccepted": "現金, 轉帳", "sameAs": [LINE_ADD]}, ensure_ascii=False) + "</script>")


# ---------- 組頁面 ----------

def main():
    md = json.loads(read("data/models.json"))
    inv = json.loads(read("data/inventory.json"))
    models = md["models"]
    by_name = {m["name"]: m for m in models}
    parts, export = inv.get("parts", []), inv.get("export", [])
    updated = nice_time(inv.get("updated"))
    scene = read("src/scene.svg")

    common = {"{{LINE}}": LINE_ADD, "{{MAP}}": e(MAP), "{{SCENE}}": scene, "{{UPDATED}}": e(updated),
              "{{FMT}}": e(parts_fmt("例 ALTIS 1.8 2013").replace("要什麼零件：", "要什麼零件：例 右前大燈", 1)),
              "{{PARTS_LINE}}": e(line_msg(parts_fmt())),
              "{{N_MODELS}}": str(len(models)), "{{N_PARTS}}": str(len(parts)), "{{N_EXPORT}}": str(len(export))}

    def fill(text, extra):
        for k, v in {**common, **extra}.items():
            text = text.replace(k, v)
        return text

    # 首頁
    shown = parts + export
    if len(parts) >= MIN_SHOW or len(export) >= MIN_SHOW:
        pool = (parts if len(parts) >= MIN_SHOW else []) + (export if len(export) >= MIN_SHOW else [])
        home_inv = '<div class="cards">' + "".join(
            car_card(c, by_name, "parts" if c in parts else "export") for c in pool[:HOME_INV]) + "</div>"
    else:
        home_inv = empty_state(len(shown), "parts")
    home_models = "".join(mini(m, "models.html") for m in models[:HOME_MODELS])

    # 常收車款篩選
    brands = []
    for m in models:
        if m.get("brand") and m["brand"] not in [b for b, _ in brands]:
            brands.append((m["brand"], m.get("brand_zh") or m["brand"]))
    brands.sort(key=lambda b: -sum(1 for m in models if m.get("brand") == b[0]))
    brand_chips = chips([(b, z.split("（")[0]) for b, z in brands])
    type_chips = chips([(t, t) for t in TYPES if any(m.get("type") == t for m in models)])

    # 英文頁
    def en_strip(key):
        out = []
        for m in models:
            n = en_name(m)
            if n and m.get(key, 0) >= 1:
                out.append(mini(m, "#contact", f"{n} · {TIER_EN[m[key]]}"))
        return "".join(out[:12])

    if len(export) >= MIN_SHOW:
        en_stock = '<div class="cards">' + "".join(
            (f'<article class="card"><div class="ph">{photo(by_name.get(c.get("model") or ""), c.get("model") or "")}'
             f'<span class="tag">{e(c.get("ref"))}</span></div><div class="cb"><h3>{e(en_name(by_name.get(c.get("model") or "", {"name": c.get("model") or ""})) or c.get("model"))} {e(c.get("year") or "")}</h3>'
             f'<div class="meta">{e(TYPE_EN.get(c.get("type"), ""))}</div><div class="acts"><a class="btn sm" href="{e(line_msg("Hi, I am interested in export stock " + str(c.get("ref")) + "."))}">Ask on LINE</a></div></div></article>')
            for c in export) + "</div>"
    else:
        en_stock = ('<div class="empty"><div class="big">Listing soon</div><div><b>Stock list coming soon</b>'
                    '<p>We are photographing and listing the cars in our yard. Until the list is ready, tell us what you need on LINE and we will check.</p>'
                    f'<div class="btns"><a class="btn sm dark" href="{e(line_msg("Hi, I am looking for: model / year / quantity / whole car or engine:"))}">Ask on LINE</a></div></div></div>')

    pages = [
        ("index.html", "home.html", "開群金屬行｜高雄阿蓮汽車回收、中古零件、廢料收購",
         "高雄阿蓮的汽車回收場：中古零件、報廢車收購、機車殼廢料、外銷整車與引擎。看場內車源和常收車款，LINE @375juggy 詢價。",
         {"{{HOME_INV}}": home_inv, "{{HOME_MODELS}}": home_models}),
        ("guide.html", "guide.html", "客戶須知｜開群金屬行",
         "買中古零件怎麼報價、零件 7 天內退換、機車殼廢料怎麼賣、報廢車要帶什麼文件，一頁看完。", {}),
        ("inventory.html", "inventory.html", "場內車源｜開群金屬行",
         "開群金屬行場內現有的零件車和外銷整車，每天早上自動更新，看到想要的直接 LINE 問。",
         {"{{INV_PARTS}}": inv_block(parts, by_name, "parts"), "{{INV_EXPORT}}": inv_block(export, by_name, "export")}),
        ("models.html", "models.html", "常收車款｜開群金屬行",
         f"開群金屬行常收的 {len(models)} 款車：ALTIS、CAMRY、VIOS、喜美、得利卡等，零件比較有機會有，LINE 直接問。",
         {"{{MODELS_GRID}}": "".join(model_card(m) for m in models), "{{BRAND_CHIPS}}": brand_chips, "{{TYPE_CHIPS}}": type_chips}),
        ("about.html", "about.html", "車場介紹｜開群金屬行",
         "開群金屬行在高雄阿蓮：一台報廢車進場後怎麼處理、我們守哪些規矩、來車場之前要知道的事。", {}),
    ]
    for out, src, title, desc, extra in pages:
        body = fill(read("src/" + src), extra)
        write(out, layout(out, body, title, desc, ""))

    en_body = fill(read("src/en.html"), {"{{LINE_EN}}": e(line_msg("Hi, I am looking for: model / year / quantity / whole car or engine:")),
                             "{{EN_WHOLE}}": en_strip("export_whole"), "{{EN_ENGINE}}": en_strip("export_engine"),
                             "{{EN_STOCK}}": en_stock, "{{UPDATED_EN}}": e(nice_time(inv.get("updated"), en=True))})
    write("en/index.html", layout("en/", en_body, "Kai-Chun Metal | Used cars and engines for export from Taiwan",
                                  "Auto recycling yard in Kaohsiung, Taiwan supplying whole used cars and used engines for export. Toyota, Honda, Nissan, Mitsubishi. Contact on LINE @375juggy.",
                                  "../", lang="en"))

    urls = ["", "inventory.html", "models.html", "guide.html", "about.html", "en/"]
    day = (inv.get("updated") or "")[:10]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{day}</lastmod></url>" for u in urls) + "</urlset>\n")
    print(f"網站產生完成：車款 {len(models)}、零件車 {len(parts)}、外銷車 {len(export)}")


if __name__ == "__main__":
    main()
