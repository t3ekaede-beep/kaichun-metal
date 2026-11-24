# 開群金屬行 客戶網站

公開網址：https://t3ekaede-beep.github.io/kaichun-metal/

## 頁面

| 頁面 | 檔案 | 內容來源 |
| --- | --- | --- |
| 首頁 | `index.html` | `src/home.html` |
| 場內車源 | `inventory.html` | `src/inventory.html`＋`data/inventory.json` |
| 常收車款 | `models.html` | `src/models.html`＋`data/models.json` |
| 客戶須知 | `guide.html` | `src/guide.html` |
| 車場介紹 | `about.html` | `src/about.html` |

根目錄的 `.html` 都是產生出來的，**不要直接改**。改文字就改 `src/`，再跑 `python scripts/build.py`。

## 每天怎麼更新

`.github/workflows/update.yml` 每天台灣時間 6:17 執行：

1. `scripts/fetch_notion.py`：用 Notion API 讀「案件」「車款圖鑑」「車款行情」「品牌」，只留可以公開的欄位，寫成 `data/*.json`。
2. `scripts/build.py`：用 `data/*.json` 和 `src/*.html` 產生網頁。
3. 資料有變就存回儲存庫，再發布到 GitHub Pages。

需要：
- 儲存庫 Settings → Secrets and variables → Actions，有一個 `NOTION_TOKEN`（Notion 內部整合的金鑰，只給「讀取內容」權限）。
- Settings → Pages → Source 選 **GitHub Actions**。

沒有 `NOTION_TOKEN` 時，會用儲存庫裡現有的 `data/*.json` 產生網頁。

## 公開規則

- 不公開車牌、車主、電話、證件、收購價、成交價、差價、成交筆數。
- 場內車源只列「盤點＝在場內」或從車場 App 新進場、還沒盤點的車；待盤點、不在場內、取消、測試車不列。
- 一類車少於 5 台時不列清單，顯示「整理中」。
- 車款照片用車款圖鑑裡的維基共享資源照片，每張都附出處連結。
