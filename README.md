# 🎶 Discord-Music-Player-Bot (進階 DJ 系統)

一套專為多人伺服器量身訂做、包含排行榜互動與高品質三大音樂鏈解析的智慧 Discord 機器人！

---

## 🌟 核心特色 (Features)
- **多平台點歌直連**：
  - 🎥 **YouTube**: 輸入名稱自動提供超貼心前 5 名搜尋選單 (`ytsearch`)
  - 🍏 **Apple Music**: 原創輕量爬蟲機制，只要貼連結就自動解析為播放串流！
  - ☁️ **SoundCloud** & 🎧 **Spotify**: 原生支援直連與龐大的專輯/播放清單自動展開！
- **玩家成就排行榜**：每一次點歌都會記錄於本地資料庫 (`music_rank.db`)，自動篩選日/月/年輕重度使用者。
- **無縫中斷重生機制**：專利 `.back` 歷史紀錄指令，誤點下一首也能立刻救回原有的歌！

---

## 🔒 檔案資安宣告 (Security)
本專案已對所有的隱私與機密資料設定了嚴密的黑名單（請檢視 `.gitignore`），因此如果你把它推上 GitHub，**絕對不會外洩**：
1. **你的任何 Token (.env 檔)**
2. **所有使用者的點歌紀錄追蹤庫 (music_rank.db)**

---

## 🛠️ 下載與環境安裝 (Setup Guide)

### 第一步：環境準備
請確保你的電腦或伺服器具備：
1. **Python 3.10** 或更高版本
2. [FFmpeg](https://ffmpeg.org/download.html) 程式（需設定並加入你的作業系統環境變數 PATH，機器人才能編碼音樂並推向語音頻道）

### 第二步：安裝依賴套件
為避免套件衝突，建議你建立虛擬環境 (Virtual Environment)，接著執行：
```bash
pip install -r requirements.txt
```

### 第三步：填寫 API 金鑰 (.env)
系統中附帶了一份 `.env.example`，請將它複製一份並改名為 `.env`，接著填入你的相關金鑰：
```env
# 你的 Discord Bot Token (不可外流)
DISCORD_TOKEN=your_token_here

# Spotify 開發者金鑰 (用於展開歌單與專輯，必須填寫)
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here
```

### 第四步：啟動
只要環境變數檔 (.env) 就緒，直接執行：
```bash
python main.py
```
若終端出現登入成功的訊息，機器人就隨時可以為你播歌了！

---

## 🕹️ 指令大全 (Commands)

*所有的指令開頭皆為 `F!`*

| 指令 | 說明 |
| :--- | :--- |
| `F!play <歌曲網址/名稱>` | 呼叫機器人進語音頻道並播放（自動辨識 YouTube, Spotify, Apple 等） |
| `F!pause` / `F!resume` | 暫停音樂 / 繼續播放 |
| `F!skip` | 跳過當前歌曲 |
| `F!back` | **[神級還原]** 切回上一首播放過的歌曲 |
| `F!queue` | 檢視當前列隊名單（最多列出 15 首） |
| `F!remove` | **[互動表單]** 選取並刪除 Queue 中的指定歌曲 |
| `F!stop` | 停止播放、清空所有排隊列與記憶，並強制退出語音頻道 |
| `F!rank [day/month/year/all]` | **[互動榜單]** 結算全伺服器最愛點歌的 DJ 排行榜 |

---

## 🤖 作者與版權
由 Antigravity 建置與優化架構。
