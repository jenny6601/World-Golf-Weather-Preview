# 90 天高爾夫出國日期決策｜第一階段資料中心

## 目的與已確認的決策條件

- 行程：5 天 4 夜
- 打球：3 場
- 日期選擇首要目標：降低整段行程的降雨風險
- 範圍：全球球場座標；先建立共通資料標準，再逐國接入區域官方資料

本階段只建立資料來源登錄、統一資料結構、來源語意規則及品質規範；尚未建立日期排名、出國建議或自動化 API 擷取工作。

## 資料來源分級

1. ECMWF EC46：延伸期週尺度資料，最長約 46 天。
2. ECMWF SEAS5：季節預報，支援週／月尺度產品；90 天規劃以月尺度趨勢為主。
3. Copernicus C3S：多模式季節展望；透過 CDS API 取得資料，需帳號、API token、接受資料集條款，且預報必須與相同系統的 hindcast 配對。
4. 日本 JMA：日本地區官方長期展望，僅適用其發布的區域範圍。
5. 台灣 CWA：台灣月長期展望，僅適用台灣，不外推至海外。
6. Open-Meteo Historical Archive：建立球場周邊歷史降雨氣候基線，不視為現場雨量觀測。

來源的狀態、端點、變數、更新頻率、憑證需求及限制見 `../data/long-range/sources.json`（網站路徑：`data/long-range/sources.json`）。

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
6. C3S 預報機率校準時，必須使用相同 originating system 的 hindcast，並記錄參考期間。
7. 歷史氣候基線與預報資料分開保存，避免把氣候平均當成未來預報。
8. 憑證只放 GitHub Actions Secrets；絕不寫入前端、JSON 資料檔或公開 commit。

## 第一階段尚未完成／需要帳號設定

- C3S：使用者需建立 CDS 帳號、取得 API token，並對所需資料集接受使用條款；完成後才可設定 `CDS_API_TOKEN`。
- CWA：需提供合法 API 金鑰並確認所需資料集存取權，才可設定 `CWA_API_KEY`。
- JMA：需先確認適用目的地的官方區域產品及可持續取得的資料格式。
- 目前 GitHub Pages 是靜態網站；任何需保密的 API token 只能由 GitHub Actions 或其他伺服器端擷取，不得由瀏覽器直接呼叫帶密鑰 API。

## 第一階段驗收標準

- [ ] 六類資料來源均有明確狀態、時間尺度及限制。
- [ ] 共通 JSON Schema 可解析，且拒絕不合法時間解析度或欄位型態。
- [ ] 能辨識降水量、降水異常、偏濕機率及真正降雨事件機率的差異。
- [ ] 所有資料可追溯至來源、模式、發布時間與擷取時間。
- [ ] 不以缺值補零、不將週／月資料下採樣成每日預報。
- [ ] 不改正式版、不部署到正式站；本分支僅供預覽與審查。

## 參考官方文件

- ECMWF Extended Range：https://www.ecmwf.int/en/forecasts/datasets/atmospheric-model-sub-seasonal-forecast-set-vi-sub-seasonal
- Open-Meteo Seasonal API：https://open-meteo.com/en/docs/seasonal-forecast-api
- Copernicus C3S Seasonal Forecasts：https://climate.copernicus.eu/seasonal-forecasts
- CDS API setup：https://cds.climate.copernicus.eu/en/how-to-api
- Taiwan CWA monthly outlook dataset：https://opendata.cwa.gov.tw/dataset/forecast/F-A0013-001
