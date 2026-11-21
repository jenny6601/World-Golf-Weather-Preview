# 90 天高爾夫出國日期決策｜第一階段資料中心

## 目的與已確認的決策條件

- 行程：5 天 4 夜
- 打球：3 場
- 日期選擇首要目標：降低整段行程的降雨風險
- 範圍：全球球場座標；先建立共通資料標準，再逐國接入區域官方資料

本階段建立資料來源登錄、統一資料結構、來源語意規則及品質規範。第一階段以不需使用者自行申請帳號的 Open-Meteo 資料路線為主，不以 Copernicus CDS 帳號或 API Token 作為開發前提。日期排名、出國建議及自動化 API 擷取工作將在後續階段實作。

## 資料來源分級與實際啟用策略

### 第一階段主要資料來源（不需使用者申請 API Key）

1. **Open-Meteo ECMWF EC46**：延伸期資料，最長約 46 天；依 API 實際提供的週／日產品與變數使用，保留原生時間尺度。
2. **Open-Meteo ECMWF SEAS5**：季節預報，支援週／月尺度產品；90 天規劃以月尺度趨勢為主，不轉換成逐日預報。
3. **Open-Meteo Historical Archive**：建立球場周邊歷史降雨氣候基線，不視為現場雨量觀測。

### 可選的區域或交叉驗證來源（不阻擋第一階段）

4. **Copernicus C3S**：未來可作為多模式季節展望交叉驗證來源。若要啟用，屆時才需要 CDS 帳號、API token 及接受資料集條款；目前不要求使用者申請，也不列為第一階段驗收條件。
5. **日本 JMA**：日本地區官方長期展望，僅適用其發布的區域範圍；待確認可持續取得的官方資料格式後再接入。
6. **台灣 CWA**：台灣月長期展望，僅適用台灣，不外推至海外；需金鑰時由伺服器端設定，不要求使用者提供。

來源的狀態、端點、變數、更新頻率、憑證需求及限制見 `../data/long-range/sources.json`（網站路徑：`data/long-range/sources.json`）。

## 90 天資料解讀方式

- **第 1–16 天**：後續整合短中期逐日預報與多模式資料；以實際提供的逐日降雨資訊評估。
- **第 17–46 天**：優先使用 EC46 可取得的延伸期產品；若來源只提供週尺度統計，評估時也只能採週尺度證據。
- **第 47–90 天**：以 SEAS5 季節趨勢及歷史氣候基線作為日期窗口的背景風險，不宣稱能預測某一天是否下雨。
- 5 天 4 夜、3 場球的候選日期窗口，未來應以整段行程及預定打球日的降雨風險為核心；遠期資料只能形成趨勢分數與信心等級，不得偽裝成精確逐日機率。

## 關鍵語意規則（不可違反）

- `precipitation_mean`：降水平均／預報統計值；依供應商單位和時間尺度呈現，不可改稱單日雨量。
- `precipitation_anomaly`：相對模式氣候基準的降水異常，不是降雨機率。
- `precipitation_anomaly_gt0`：降水異常高於常年基準的機率，不是「下雨機率」。
- C3S 的 below/near/above normal tercile probability：低於／接近／高於常年類別機率，不是某一天會下雨的機率。
- 月資料不可拆成逐日資料；週資料不可偽裝成每日資料。
- 只有供應商明確提供且語意已確認的降雨事件機率，才能標示「降雨機率」。
- 未提供、缺值、過期或來源失敗時，必須保留狀態；不得用 0、歷史平均或其他模式的數值冒充。

## 統一觀測資料格式

每筆資料包含：

- 球場座標與時區
- 來源、供應商、模式
- 預報起訖日期及 lead day 範圍
- daily / weekly / monthly 時間解析度
- 模式發布時間與系統擷取時間
- 變數值、單位、統計型態及語意
- 系集成員數（如來源提供）
- 品質狀態、缺漏欄位及註記
- 原始資料參照及授權資訊

JSON Schema：`data/schemas/long-range-observation.schema.json`。

## 資料品質及更新原則

1. 每個來源獨立保存，不在擷取時先混成一個數字。
2. 保留 issued_at、retrieved_at、有效期間及模式名稱，讓後續可以追蹤預報版本。
3. 先依球場座標、時區及來源網格做空間／時間對齊；不得把城市平均直接當成球場現場觀測。
4. 來源資料必須標記有效、部分缺漏、未提供、過期或失敗。
5. 多模式融合前，需統一變數定義、單位、時間窗與氣候基準。
6. C3S 若未來啟用並進行機率校準，必須使用相同 originating system 的 hindcast，並記錄參考期間。
7. 歷史氣候基線與預報資料分開保存，避免把氣候平均當成未來預報。
8. 憑證只放 GitHub Actions Secrets；絕不寫入前端、JSON 資料檔或公開 commit。
9. 沒有 CDS 帳號、token 或 C3S 資料時，主要流程仍須可正常運作；不得將 C3S 標示為必要依賴。

## 第一階段不要求使用者提供的帳號或金鑰

- **Copernicus CDS**：第一階段不需要註冊、API token 或接受資料集條款。C3S 保留為未來可選交叉驗證來源。
- **CWA**：只有在後續決定接入台灣官方資料時，才評估 API 金鑰與資料集權限。
- **JMA**：先確認目的地官方區域產品及可持續取得的資料格式，再決定是否接入。
- 目前 GitHub Pages 是靜態網站；任何需保密的 API token 只能由 GitHub Actions 或其他伺服器端擷取，不得由瀏覽器直接呼叫帶密鑰 API。

## 第一階段驗收標準

- [ ] Open-Meteo EC46、SEAS5 與 Historical Archive 可作為不需使用者自行申請金鑰的主要資料路線。
- [ ] C3S 明確標示為未來可選來源；缺少 CDS 帳號或 token 不影響主要流程。
- [ ] 六類資料來源均有明確狀態、時間尺度及限制。
- [ ] 共通 JSON Schema 可解析，且拒絕不合法時間解析度或欄位型態。
- [ ] 能辨識降水量、降水異常、偏濕機率及真正降雨事件機率的差異。
- [ ] 所有資料可追溯至來源、模式、發布時間與擷取時間。
- [ ] 不以缺值補零、不將週／月資料下採樣成每日預報。
- [ ] 不改正式版、不部署到正式站；本分支僅供預覽與審查。

## 參考官方文件

- ECMWF Extended Range：https://www.ecmwf.int/en/forecasts/datasets/atmospheric-model-sub-seasonal-forecast-set-vi-sub-seasonal
- Open-Meteo Seasonal API：https://open-meteo.com/en/docs/seasonal-forecast-api
- Open-Meteo Historical Weather API：https://open-meteo.com/en/docs/historical-weather-api
- Copernicus C3S Seasonal Forecasts（未來可選）：https://climate.copernicus.eu/seasonal-forecasts
- CDS API setup（僅未來啟用 C3S 時需要）：https://cds.climate.copernicus.eu/en/how-to-api
- Taiwan CWA monthly outlook dataset：https://opendata.cwa.gov.tw/dataset/forecast/F-A0013-001


## 第二階段：自動擷取管線（初版）

已在開發分支新增以下元件，供手動預覽驗證：

- `scripts/fetch_long_range.py`：以球場已核實的 GPS 座標，分別呼叫 Open-Meteo Seasonal API 的 ECMWF EC46 與 SEAS5 模型；保存原始 JSON 回應，不先合併或轉換成日期分數。
- `data/long-range/courses.example.json`：球場座標輸入範本。目前清單刻意為空，避免將未核實座標當成正式球場資料。
- `tests/test_long_range_pipeline.py`：座標驗證、欄位檢查、原始回應保留及空清單行為測試。
- `.github/workflows/long-range-data-preview.yml`：僅提供手動觸發；執行測試並將擷取結果以 7 天期限的 Actions artifact 保存。權限為 contents: read，不會寫回 repository，也不會觸發正式部署。

### 擷取管線限制與注意事項

1. API 使用 `https://seasonal-api.open-meteo.com/v1/seasonal`；EC46 擷取 46 天，SEAS5 擷取 90 天，實際可用欄位與時段以供應商回應為準。
2. 每筆原始快照包含模型、球場座標、請求參數、HTTP 狀態、擷取時間及供應商原始 payload。
3. 供應商 API 回應未必提供可驗證的模式初始化時間；因此不把 `retrieved_at` 冒充 `issued_at`。
4. 本版先保存原始供應商資料，不自行推算每日降雨機率、不將異常值換算為雨天機率，也不產生 5 天行程排名。
5. 目前範例球場清單為空，須先將 World Golf Weather 中已核實的全球球場 ID、名稱、國家代碼及 GPS 座標匯入，才會實際呼叫 API。空清單時 workflow 只產生 `no_targets_configured` manifest，不會假造資料。
6. 本版以 Actions artifact 作為短期驗證輸出（保留 7 天）；尚未建立長期資料庫或自動更新正式網站。

### 第二階段初版驗收項目

- [ ] 將既有全球球場主檔安全匯入擷取目標清單，並核對座標及時區。
- [ ] 手動執行 workflow，確認 EC46 與 SEAS5 的實際 API 回應及時間範圍。
- [ ] 檢查各球場、各模式的成功／部分成功／失敗狀態與資料完整性。
- [ ] 確認 artifact 僅供預覽、無 repository 寫入、無正式部署。
- [ ] 再決定長期儲存方式及更新頻率；未完成資料品質驗證前，不啟動日期排名。
