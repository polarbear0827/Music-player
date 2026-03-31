# 🎶 Discord AI Music DJ (智慧電台系統)

一套專為多人大型伺服器量身訂做、結合 **Groq LLM (Llama 3 70B)** 的超強溫馨智慧音樂電台。
不但擁有全方位的串流音樂庫（YouTube、Spotify、Apple Music），更具備了強悍的防呆安全鎖與情境智慧找歌功能。

---

## 🌟 核心特色 (Features)

### 🤖 真・AI 電台靈魂 (Powered by Llama 3)
- **情境精準找歌 (`F!dj`)**：不用再想歌單了！直接輸入你現在的心情（例如：`F!dj 我今天要通宵寫扣，給首戰鬥歌`），AI 會運用零延遲的推演立刻幫你從海量歌曲中找出最適合的一首並自動加入播放。
- **無縫串場廣播**：每次切換歌曲時，AI 會根據歌名與點歌者的名稱，即時說一句 30 字以內的溫馨加油短語，就像是真的電台 DJ 在廣播一樣暖心！
- **日常閒聊功能 (`F!chat`)**：無聊時可以隨時 Call 機器人出來瞎聊，它永遠充滿顏文字與正能量。

### 💿 多平台點歌直連
- 🎥 **YouTube**: 輸入歌曲名稱自動回傳精華前 5 名選單供你點選 (`ytsearch5`)
- 🍏 **Apple Music**: 獨家原生輕量爬蟲機制，Apple Music 連結一樣通吃！
- ☁️ **SoundCloud** & 🎧 **Spotify**: 完美支援直連與龐大的播放清單/專輯一鍵解壓縮。

### 🏆 玩家成就排行榜 (`F!rank`)
系統自建輕量 SQLite 資料庫 (`music_rank.db`)。
支援 `F!rank day / month / year / all`，一眼看出群組裡的隱藏重度點歌王是誰！

### 🛡️ 企業級防護機制 (Security & Stability)
機器人內建「防呆三煞車」，不畏懼群組裡搗亂的使用者：
1. **防止 AI 惡意癱瘓**：加上 10 秒硬性冷卻鎖與 150 字 Prompt 截斷。
2. **防死檔遞迴當機**：YouTube 發生死檔時永遠冷卻 2 秒鐘再繼續播下首，不傷系統計算力。
3. **無痛刪歌 (`F!remove`) 防撞鎖**：具備絕對伺服器 5 秒鎖，絕不會發生兩人在刪歌時因清單位移而發生的誤刪災難。
4. **巨型清單防爆閥**：Spotify 單次最高載入 200 首歌，完美拒絕千萬首垃圾清單洗版。

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

# Groq 智慧推理金鑰 (電台 DJ 對話引擎，非常關鍵！)
GROQ_API_KEY=your_groq_api_key_here
```
> **隱私宣導**：本專案已透過 `.gitignore` 嚴格將你的 `.env` 列入隔離清單，你可以放心備份到 GitHub。

### 第四步：電台開播囉！
直接執行：
```bash
python main.py
```

---

## 🕹️ 指令大全 (Commands)

*所有的指令開頭皆為 `F!`*

| 指令 | 說明 |
| :--- | :--- |
| `F!dj <情境>` | **[AI 智選]** 告訴 DJ 你當下的心情，讓它直接為你上 1 首神曲 |
| `F!chat <內容>` | **[AI 對話]** 跟溫馨電台 DJ 快樂聊天打招呼 |
| `F!play <網址/名稱>` | 手動呼叫機器人播放 / 搜尋 YouTube, Spotify, Apple 等歌曲 |
| `F!pause` / `F!resume` | 暫停音樂 / 繼續播放 |
| `F!skip` / `F!stop` | 跳過當前歌曲 / 停止播放、清空所有排隊列與記憶並離開頻道 |
| `F!back` | **[神級還原]** 切回上一首播放過的歌曲 |
| `F!queue` | 檢視當前列隊名單 |
| `F!remove` | **[安全名單]** 選取並刪除 Queue 中的指定歌曲 (具備排他防搶鎖) |
| `F!rank [參數]` | 結算全伺服器最愛點歌的 DJ 積分榜 (支援 day/month/year) |

---
*Built with Llama 3 & Antigravity.*
