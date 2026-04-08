<p align="center">
  <img src="assets/banner.png" width="800">
</p>

# 🎶 Discord AI Music DJ (智慧電台系統)

一套專為多人大型伺服器量身訂做、結合 **OpenRouter (Minimax M2.5)** 的超強溫馨智慧音樂電台。
不但擁有全方位的串流音樂庫（YouTube、Spotify、Apple Music），更具備了強悍的防呆安全鎖與情境智慧找歌功能。

---

## 🌟 核心特色 (Features)

### 🤖 真・AI 電台靈魂 (Powered by Minimax M2.5)
- **情境精準找歌 (`F!dj`)**：不用再想歌單了！直接輸入你現在的心情（例如：`F!dj 我今天要通宵寫扣，給首戰鬥歌`），AI 會運用零延遲的推演立刻幫你從海量歌曲中找出最適合的一首並自動加入播放。
- **無縫串場廣播**：每次切換歌曲時，AI 會根據歌名與點歌者的名稱，即時說一句 30 字以內的溫馨加油短語，就像是真的電台 DJ 在廣播一樣暖心！
- **日常閒聊功能 (`F!chat`)**：無聊時可以隨時 Call 機器人出來瞎聊，它永遠充滿顏文字與正能量。
- **個人化 API 金鑰**：使用者可透過 `F!setkey` 綁定自己的 OpenRouter Key，享受專屬的 AI 推理頻寬，不受全域限制、不看別人臉色！
- **高穩定性架構**：內建 `FakeCtx` 模擬機制與 OpenRouter 安全防護，確保 AI 服務不中斷。

### 📻 派對與不打烊社群系統
- **🎀 粉紅派對 Live 儀表板 (Live Dashboard)**：徹底告別傳統機器人的洗版地獄！播放器會化身為「全頻道唯一」的動態 UI 面板，並內建 Discord 原生 **[⏯實體按鈕]**。任何人不須打指令就能無延遲切歌、暫停、或一鍵開啟電台！
- **百萬大歌星 (`F!guess`)**：從伺服器過去的**歷史點播紀錄**中盲抽 15 秒精華，看誰能最快在聊天室猜出歌名！內建積分排行榜。
- **伺服器專屬私房歌單 (`F!playlist`)**：一鍵將當前 Queue 裡的所有歌曲封存為伺服器的專屬歌單，隨時 `load` 回來開趴。
- **24/7 不打烊沉浸電台 (`F!radio`)**：當歌曲播完時，自動無縫切換至 **Lofi Girl / Jazz / Synthwave** YouTube 24H 直播源。有人點歌時會「自動讓位插隊」，播完再切回廣播！

### 🧽 海綿寶寶迷因貼圖系統 (Sticker System)
- **海量資料庫**：內建超過 **8,200 張** 海綿寶寶經典截圖與迷因，支援模糊關鍵字搜尋。
- **精準搜尋 (`F!sticker`)**：輸入關鍵字，機器人會列出最接近的 5 個選項，由你點擊按鈕決定送出哪一張。
- **隨機驚喜 (`F!ssr`)**：隨機抽出一張經典貼圖，讓聊天室瞬間充滿海綿寶寶的魔力。

### 💿 多平台點歌直連
- 🎥 **YouTube**: 輸入歌曲名稱自動回傳精華前 5 名選單供你點選 (`ytsearch5`)
- 🍏 **Apple Music**: 獨家原生輕量爬蟲機制，Apple Music 連結一樣通吃！
- ☁️ **SoundCloud** & 🎧 **Spotify**: 完美支援直連與龐大的播放清單/專輯一鍵解壓縮。

### 🏆 玩家成就排行榜 (`F!rank`)
系統自建輕量 SQLite 資料庫 (`music_rank.db`)。
支援 `F!rank day / month / year / all`，一眼看出群組裡的隱藏重度點歌王是誰！

### 🛡️ 企業級防護機制 (Security & Stability)
機器人內建「防呆八煞車」，不畏懼群組裡搗亂的使用者：
1. **防止 AI 惡意癱瘓**：加上 10 秒硬性冷卻鎖與 150 字 Prompt 截斷。**新版內建 OpenRouter 與 Groq 雙智慧引擎備援機制 (Fallback)!**
2. **防死檔遞迴當機**：YouTube 發生死檔時永遠冷卻 2 秒鐘再繼續播下首，不傷系統計算力。
3. **無痛刪歌 (`F!remove`) 防撞鎖**：自研 UUID 快照比對尋址，徹底解決切歌期間陣列位移導致的「殺錯歌」災難！
4. **巨型清單防爆閥**：Spotify 單次最高載入 200 首歌，且內嵌 Timeout 脫離機制，拒絕千萬首垃圾清單導致連線池枯竭。
5. **資料庫背景引擎**：全系統 SQLite 讀寫接軌防卡頓 Thread Pool，萬人伺服器運轉保證行雲流水。
6. **面板雙胞胎免疫**：引入核心級非同步鎖 (`asyncio.Lock`)，完全杜絕手殘狂點造成的面版崩壞複製蟲。
7. **嚴格的記憶體把控**：歷史查詢緩存最高極限鎖定 200 首（避開背景電台污染），阻絕無限循環導致的 OOM 崩潰。
8. **電台韌性連線**：廣播遭遇暫時性網路阻斷時不罷工，直接排定 10 秒後「韌性重啟連線」，確保沉浸式體驗永不斷電。

---

## 🛠️ 下載與環境安裝 (Setup Guide)

### 第一步：環境準備
請確保你的電腦或伺服器具備：
1. **Python 3.10** 或更高版本
2. [FFmpeg](https://ffmpeg.org/download.html) 程式（需加入作業系統環境變數 PATH，這對轉檔與播放至關重要）

### 第二步：安裝依賴套件
```bash
pip install -r requirements.txt
```

### 第三步：填入你的大腦核心 (.env)
系統中附帶了一份 `.env.example`。請將它複製一份並改名為 `.env`，然後填滿以下關鍵鑰匙（請記得保持秘密）：
```env
# Discord 開發者 Token (絕對不可外流)
DISCORD_TOKEN=your_token_here

# Spotify 開發者金鑰 (展開歌單用)
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here

# Groq 智慧推理金鑰 (電台 DJ 高速備援引擎，確保無縫廣播！新版功能！)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenRouter 智慧推理金鑰 (電台 DJ 對話引擎，支援最新 Minimax-M2.5-Free！)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx

### 第四步：電台開播囉！ (部署方式 2 選 1)

#### 🐳 推薦：使用 Docker 一鍵啟動 (適合 24H 伺服器/掛機)
有了 Docker，你**不需要安裝 Python 也不用管煩人的 FFmpeg！**
確定你有安裝 Docker 後，只要一行指令：
```bash
docker compose up -d
```
> **資料不遺失保證**：透過 Docker Compose，機器人的資料庫 (`music_rank.db`) 會自動掛載並保存在你的本機資料夾，即使容器砍掉重建，你們的猜歌分數與私房歌單也永遠都在！

#### 💻 傳統：本機 Python 運行
確保你已經裝好 `FFmpeg` 到環境變數中，直接執行：
```bash
python main.py
```

---

## 🕹️ 指令大全 (Commands)

*所有的指令開頭皆為 `F!`，且**指令名稱不分大小寫**（例如 `F!play` 與 `f!PLAY` 效果相同）。*

| 指令 | 說明 |
| :--- | :--- |
| `F!dj <情境>` | **[AI 智選]** 告訴 DJ 你當下的心情，讓它直接為你上 1 首神曲 |
| `F!chat <內容>` | **[AI 對話]** 跟溫馨電台 DJ 快樂聊天打招呼 |
| `F!play <網址/名稱>` | 手動呼叫機器人播放 / 搜尋 YouTube, Spotify, Apple 等歌曲 |
| `F!np` / `F!nowplaying` | 顯示當前詳細播放資訊（含進度條、點播者、Loop 狀態） |
| `F!pause` / `F!resume` | 暫停音樂 / 繼續播放 |
| `F!skip` / `F!stop` | 跳過當前歌曲 / 停止播放、清空所有排隊列與記憶並離開頻道 |
| `F!back` | **[神級還原]** 切回上一首播放過的歌曲 |
| `F!queue` | 檢視當前列隊名單 |
| `F!shuffle` / `F!loop` | 打亂列隊 / 切換循環模式 (Off / Single / Queue) |
| `F!volume <1-100>` | 設定播放音量 (縮寫: `F!vol`) |
| `F!remove` | **[安全名單]** 選取並刪除 Queue 中的指定歌曲 (具備排他防搶鎖) |
| `F!rank [參數]` | 結算全伺服器最愛點歌的 DJ 積分榜 (支援 day/month/year) |
| `F!guess` | **[小遊戲]** 啟動音樂猜猜看（基於伺服器歷史點播紀錄） |
| `F!playlist <指令>` | **[歌單管理]** 支援 `save`, `load`, `list` 伺服器專屬歌單 |
| `F!radio <類型>` | **[24H 電台]** 設定背景頻道 (lofi, jazz, synth, off) |
| `F!sticker <關鍵字>` | **[貼圖]** 搜尋海綿寶寶貼圖，並透過按鈕選取送出 (縮寫: `F!ss`) |
| `F!ssr` | **[貼圖]** 隨機送出一張海綿寶寶貼圖 (縮寫: `F!sticker_random`) |
| `F!setkey <key>` | **[API 設定]** 綁定個人的 OpenRouter API Key (推薦在私訊使用) |
| `F!delkey` | **[API 設定]** 刪除個人的 OpenRouter API Key |
| `F!sticker_count` | 統計目前海量貼圖資料庫的總數 |

---
*Built with Minimax M2.5 & Antigravity.*
