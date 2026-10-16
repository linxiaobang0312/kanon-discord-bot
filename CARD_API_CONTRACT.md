# 香音商品唯讀查詢：網站 API 接口需求

此文件是 **對接需求**，不是聲稱網站已經提供的真實端點。請網站維護者確認實際路徑、驗證方式與欄位，並以現有資料庫實作或映射。不得重建資料庫或改變現有交易、扣庫存流程。

## 網站提供
- HTTPS GET 公開商品搜尋 API，例如 `/api/public/cards?q=<卡號或名稱>&limit=20`（**僅為範例**）。
- 只回公開資訊，沒有任何後台連結、私人資料或管理權限。
- 搜尋需支援完整卡號或名稱；同名不同版本回傳不同 items，不可以合併。
- `available_quantity` 必須是**當下可售數量**，不能是原始進貨量、總庫存、已保留數，或讀取失敗時代入 0。
- `unit_price` 是**當下公開單張售價**；缺價用 null，不要代入 0。
- 查無項目時回傳空 items；系統錯誤要用非 2xx 或 `ok:false`，不可假裝查無庫存。
- 若資料需要權限，另行提供只讀服務 Token，放 Railway 的 `CARD_SEARCH_API_TOKEN`，不要放 GitHub、網址或 Discord 聊天。

## 預期回傳範例（僅示範欄位）

~~~json
{
  "items": [
    {
      "card_id": "sample-version-1",
      "card_number": "EX-001-R",
      "card_name": "範例角色",
      "variant": "R",
      "available_quantity": 2,
      "unit_price": 50,
      "currency": "TWD"
    },
    {
      "card_id": "sample-version-2",
      "card_number": "EX-001-P",
      "card_name": "範例角色",
      "variant": "P",
      "available_quantity": 0,
      "unit_price": 120,
      "currency": "TWD"
    }
  ],
  "has_more": false
}
~~~

## Discord / Railway 設定
- `CARD_SEARCH_API_URL`：**真正的完整 HTTPS 查詢 API**，不是網站首頁，也不是 `/admin` 或 `/api/trades`。
- `CARD_SEARCH_QUERY_PARAM`（可選，預設 `q`）：API 搜尋參數名稱。
- `CARD_SEARCH_API_TOKEN`（可選）：只讀權杖；不應使用管理員密碼或交易通知 webhook。
- 不提供查詢 API 時，香音只會明確說目前無法取得庫存，不會用 AI 編數字。

## 使用情境
- `@香音 PL!HS-pb1-007-P+ 還有嗎？` → 逐項回卡號、卡名、版本、可售量、單價。
- `@香音 範例角色庫存` → 同名不同版本分開列。
- `@香音 這張還有嗎？` → 請使用者提供卡號／卡名，不能憑空知道「這張」是哪一張。
- 回覆絕不包含管理後台 URL、API 網址、內部交易資料。

## 目前確認狀況
Discord 端唯讀 adapter 已提交；網站真正 API 路徑、授權規則與 JSON 尚未驗證，因此**尚未完成端到端即時庫存連線**。
