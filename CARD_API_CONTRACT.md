# 香音商品 API 接線紀錄（2026-10-16）

## 已確認的正式來源

GET `https://tsubang-card-library.lin-xiao-bang.chatgpt.site/api/cards`

從 Railway 同網路環境實測：
- HTTP 200；application/json
- 回傳 JSON 物件，頂層包含 `cards`、`series`、`sections` 等欄位
- `cards` 有 2,981 筆（當次診斷取樣的數量，隨網站庫存可能變動）
- 商品欄位包含 `number`、`display_name`、`name`、`custom_name`、`official_name`、`rarity`、`price`、`quantity`、`series`、`group_name`
- 對此 API 加上 `q` 查詢參數的實測失敗；故**只對正式網址做不帶參數的 GET，拿全量資料後在 Bot 伺服器記憶體本地搜尋**
- 不取用 `admin`、`import_source_url` 等欄位做 Discord 訊息

## Railway

`CARD_SEARCH_API_URL` 已在既有服務設成正式 HTTPS URL。
不需要另設 `CARD_SEARCH_QUERY_PARAM`。
若未來網站將端點改為唯讀權杖保護，可用 `CARD_SEARCH_API_TOKEN`，只允許讀取商品，不能給管理員憑證。

## 公開客服回覆

- 依卡號和 `display_name` 等正式名稱比對，版本靠 `number` + `rarity` 區分，不合併。
- `quantity` 當成網站當次公佈的可售數量，`price` 當成單張售價；未知不是 0。
- 只輸出卡號／卡名／版本／可售數量／價格，不傳管理網址或其他後台欄位。
- 查不到：明講查不到；讀取錯誤：明講查詢失敗；問「這張」沒卡號／名稱：要求補充。
- 本功能只有 GET，不改價、不修改庫存、不操作交易車或訂單。

## 程式檢驗

`python -m unittest -v test_inventory_lookup.py`

Railway Pre-Deploy 在每次新版部署前執行測試；測試包括不同版本分列、缺價／零庫存、拒絕猜數量、不輸出後台資料、僅用不帶參數的 GET。
