# Discord DJ Bot - 全面程式碼審查與風險分析報告

在您完成基礎建設後，我替整個系統進行了一次深度的技術盤點。包含 `music.py`、`sticker.py`、資料庫存取層以及 API 連線層。
整體架構上非常清晰，且大量利用了 `asyncio.to_thread` 防止阻塞 Discord Event Loop，這是非常優秀的設計。但仍有一些隱患與邊界漏洞需要在未來大規模部署時注意。

以下是為您梳理出的 **10 大潛在風險與可能性**：

## 1. 記憶體流失風險 (Memory Leaks)
> [!WARNING]
> **無限增長的歷史紀錄**
在 `music.py` 的 `play_next` 函式中，每播放完一首歌就會無條件附加到 `self.histories[ctx.guild.id].append(...)`。如果機器人在某個伺服器 24 小時不間斷播放背景電台 (`F!radio`)，經過一兩個月後，該伺服器的 `histories` 陣列將會累積數以萬計的字典物件。這會導致記憶體無限制增長，最終讓 Python 拋出 `MemoryError` 甚至由作業系統強制擊殺程序（OOM Killer）。
**建議修正**：為史紀錄長度設定上限（例如：`if len(history) > 100: history.pop(0)`）。

## 2. 關於 `F!remove` 與列隊操作的競態條件 (Race Condition)
> [!CAUTION]
> **刪歌錯位災難**
雖然 `F!remove` 具有 `self.remove_locks` 防治兩個人同時呼叫指令。但他防護不了「時間差」造成的陣列偏移：
當列隊有 3 首歌，小明呼叫 `F!remove` 正在猶豫要刪第 2 首，此時這 **30 秒等待期內** 當前歌曲播完了，`play_next` 會把列隊的第 1 首 `pop` 掉。此時列隊裡的歌曲全部往前移一位（原本的第 2 首變成第 1 首）。
若小明這時候回覆了 `2`，系統卻刪除到了**原本的第 3 首**！
**建議修正**：顯示清單時，將「流水號」改綁定歌曲的唯一 UUID，不要依賴動態的 `List Index` 進行刪除。

## 3. SQLite 資料庫的執行緒阻塞 (Blocking Event Loop)
> [!TIP]
> **Synchronous DB Calls in Async Functions**
`record_play` 已經完美地使用 `to_thread` 包裝。但是，在 `playlist_save`, `playlist_load` 以及 `F!guess` 的勝利計算等指令中，仍直接在 `async def` 內呼叫 `self.cursor.execute()`。
這代表當硬碟忙碌，或 SQLite 本身進行 Lock 時，將會發生數十毫秒的**全域延遲**，這期間整個機器人都將無法處理任何人的 Discord 訊息。
**建議修正**：將所有存取資料庫的操作一律隔離至 `run_in_executor` 中執行。

## 4. `F!guess` 猜歌遊戲的影片長短漏洞 
> [!NOTE]
> **找不到 15 秒後的音軌**
`F!guess` 會使用 `start_time = random.randint(15, 60)` 隨機從歌曲中抽取一段開始播放。
但是如果 `play_history` 中紀錄的是一首「網路迷因音效」或「超短廢片」，總長度只有 **10 秒**，FFmpeg 尋找 `-ss 30` 時會直接失敗或是立刻結束，導致沒有聲音播出來。
**建議修正**：在 `yt-dlp` `extract_info` 當下，檢查檔案的 `duration` 欄位，再決定 `random.randint` 的上限。

## 5. Spotify API 阻塞與連線池用盡 (Rate Limit Blocked)
> [!WARNING]
> **Spotipy 的隱藏陷阱**
`get_track_info_from_spotify` 是同步寫法，利用 `run_in_executor` 放進執行緒池。
`spotipy` 套件的預設行為是：「遇到 Spotify API 頻率限制 (HTTP 429) 時，會執行 `time.sleep(retry_after)` 並且重試」。
這意味著如果有人惡意傳送大量 Spotify 巨型清單，該 Request 所在的執行緒會被**鎖住好幾秒甚至幾分鐘**。如果執行緒池 (Thread Pool) 被塞滿，機器人將無法再處理任何其他背景運算（包含解析正常的 YouTube 歌單）。
**建議修正**：關閉 `spotipy` 的自動 sleep (例如使用 `requests_timeout` 限制)，或改用純異步的 Spotify 串接工具，遇到 429 時立刻報錯回群組。

## 6. Dashboard (UI 面板) 競態重複產生
當 `on_message` 收到訊息而呼叫 `update_dashboard(force_resend=True)` 時，同時有人瘋狂狂按「暫停」按鈕，可能會有兩個 Task 同時意圖「刪除舊訊息並發送新訊息」。
如果運氣不好，Discord 可能因此產生「兩個」永遠存在的儀表板。
**建議修正**：加入每伺服器的 `dashboard_lock = asyncio.Lock()`，確保同一個群組內同時間只能有一個實體進行儀表板重繪。

## 7. `yt-dlp` 的永久懸掛 (Hanging)
在 `YTDLSource.from_query` 中，雖然放進了 `to_thread` 執行，但是 `yt-dlp` 未設定請求超時 (`socket_timeout`)。
如果指定的來源網站伺服器當機（不只是 YouTube，也可以是 Soundcloud 或任何第三方網站），執行緒可能會卡死長達數小時之久。
**建議修正**：在 `YTDL_OPTIONS` 新增 `'socket_timeout': 15`。

## 8. Apple Music 爬蟲的正則表達式邊界 (Regex Vulnerability)
利用 `re.search(r'<title>(.*?)</title>')` 爬取 Apple Music 非常輕量，但萬一 Apple Music 的網頁將單引號轉為 HTML Entities (例如 `&#39;`) 或包含其他特殊的不可見字元，您的播放器可能解析出 `Don&#39;t Stop Believin&#39; (Official Audio)` 去 YouTube 搜尋，影響準確度。
**建議修正**：引入 `html.unescape()` 來清除這些 HTML 字元。

## 9. API 回傳空陣列時 AI DJ 取值錯誤 (IndexError)
在 `call_openrouter` 及 `F!dj` 函式中：
如果遇到 API 審查阻擋（例如情境中包含敏感暴力字眼）或者 AI 胡言亂語跳脫格式，`json.loads()` 返回的可能是一個合法的空陣列 `[]`。
當系統執行 `song = song_list[0]` 時會引發 `IndexError` 造成拋出例外，進而使 `F!dj` 無法回應使用者任何有用的錯誤內容。
**建議修正**：先判斷 `if not song_list or len(song_list) == 0:`。

## 10. `F!radio` 受到網路閃斷被永遠移除
在 `play_next` 時，如果機器人想無縫切換到 `radio_url`，萬一這瞬間網路不穩，`YTDLSource.from_query` 會報錯。
系統會直接印出 `❌ 無法連線至直播源`，然後將背景廣播從字典中 **移除 (`pop`)**！
這代表伺服器的 24 小時駐紮功能直接被破壞，直到下一個管理員發現並手動重打 `F!radio` 為止。
**建議修正**：如果只是暫時連線異常，應該加上簡單的 Retry（例如退讓或暫停 10 秒後重連），而不是立刻把駐站設定拔除。

---

> 以上是本次深度的 Code Review 報告。如果您希望我對上述任一項問題進行針對性修補（例如：實作記憶體排堵、防止刪歌錯位、或者是修復 DB 阻塞），都可以隨時下達指令！
