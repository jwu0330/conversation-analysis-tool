# 對話紀錄統計分析系統

讓研究者**不用寫程式、也不用在 Excel 反覆手動計算**，就能對對話紀錄資料進行
描述統計、組間比較、統計檢定、效果量計算、圖表視覺化與結果匯出的網頁工具。

採「**先選欄位，再選分析**」流程，所有結果皆可重複產生並匯出。

## 功能（v2：前端重構為 4 界面）

| 界面 | 功能 |
| --- | --- |
| 首頁（`app.py`） | 資料上傳、品質檢查、**結果匯出**（上傳／匯出兩個分頁） |
| 📈 敘述性統計 | 描述統計（含中位數）、次數／累積排名、相關分析、兩組 t 檢定、交叉熱力圖 |
| 📐 統計分析 | **SPSS 式共變數分析 ANCOVA**（一鍵：描述→Levene→斜率同質→型 III→調整後平均→事後比較） |
| 🔀 序列分析 | 個人序列、轉移分析（含 GSEQ，預設只顯著偏多）、趨勢分析 |

> 完整界面規格與統計方法對照見 **[`docs/前端架構說明.md`](docs/前端架構說明.md)**，後端驗證以該文件為準。

## 專案結構

```
.
├── app.py                     # 首頁（上傳＋檢查＋匯出）
├── pages/                     # Streamlit 多分頁（依檔名數字排序）
│   ├── 1_📈_敘述性統計.py
│   ├── 2_📐_統計分析.py       # ANCOVA
│   └── 3_🔀_序列分析.py
├── docs/前端架構說明.md        # 界面規格與統計方法對照（後端驗證基準）
├── src/
│   ├── state.py               # 跨分頁 session state 工具
│   ├── sequence/              # 序列分析（Lag-1 轉移、GSEQ、趨勢迴歸）
│   └── core/                  # 與 UI 分離的純函式（可測試、可重用）
│       ├── data_loader.py     # 上傳與讀取（Excel/CSV，自動編碼）
│       ├── data_quality.py    # 摘要、缺漏值、重複檢查
│       ├── column_types.py    # 欄位型態辨識
│       ├── descriptive.py     # 描述統計 + 相關分析
│       ├── grouping.py        # 交叉表（供交叉熱力圖）
│       ├── stat_tests.py      # t 檢定 / 卡方 + 效果量
│       ├── ancova.py          # SPSS 式共變數分析（型 III）
│       ├── charts.py          # Plotly 圖表
│       └── exporter.py        # Excel 匯出
├── sample_data/generate_sample.py   # 模擬對話紀錄資料產生器
├── tests/test_core.py         # 核心邏輯單元測試
├── requirements.txt
├── Dockerfile
└── README.md
```

**設計原則**：核心分析邏輯全放在 `src/core/`（純 pandas/scipy 函式，不依賴 Streamlit），
UI 只負責呼叫與顯示。要新增 Bloom/SOLO 分類或 GSEQ 序列分析時，只需在 `core/` 加模組、
在 `pages/` 加分頁，不動既有程式。

## 一、本機部署

```bash
# 1. 建立虛擬環境
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. 安裝套件
pip install -r requirements.txt

# 3.（可選）產生模擬資料
python sample_data/generate_sample.py

# 4. 啟動
streamlit run app.py
```

瀏覽器開啟 http://localhost:8501 。

## 二、Streamlit Cloud 部署

1. 將本專案推上 GitHub。
2. 於 [share.streamlit.io](https://share.streamlit.io) 連接此 repo。
3. 主程式設定為 `app.py`，Python 依賴自動讀取 `requirements.txt`。
4. 部署後取得可分享網址。

## 三、Docker 部署

```bash
docker build -t conversation-analysis .
docker run -p 8501:8501 conversation-analysis
```

開啟 http://localhost:8501 。後續可再加上帳號密碼與資料庫。

## 測試

```bash
python tests/test_core.py       # 內建簡易 runner
# 或
python -m pytest -q             # 若已安裝 pytest
```

## 快速啟動（Windows）

雙擊專案根目錄的 **`run.bat`** 即可。第一次會自動建立虛擬環境並安裝套件，之後每次雙擊直接啟動網頁。要關閉就關掉那個黑色視窗。

## 網頁跑不起來？故障排除

先執行診斷腳本，它會逐項檢查並告訴你問題在哪：

```bash
.venv\Scripts\python.exe scripts\check_env.py   # Windows
./.venv/bin/python scripts/check_env.py         # macOS/Linux
```

常見狀況對照：

| 症狀 | 原因 | 解法 |
| --- | --- | --- |
| 瀏覽器打不開、連線被拒 | 伺服器沒在跑（關過視窗／電腦重開／程序被中止） | 重新雙擊 `run.bat`，或 `streamlit run app.py` |
| `Port 8501 is already in use` | 上次沒關乾淨，埠被占用 | 換埠：`streamlit run app.py --server.port=8502`，或關掉舊的黑視窗 |
| `ModuleNotFoundError` | 套件沒裝，或沒啟動虛擬環境 | `pip install -r requirements.txt`（先確認已 activate `.venv`） |
| `python 不是內部或外部命令` | 沒裝 Python 或沒加入 PATH | 重新安裝 Python，勾選 **Add Python to PATH** |
| 網頁一直轉圈／改了程式沒更新 | 舊的執行階段卡住 | 瀏覽器按 F5；或關掉視窗重開 |
| 頁面顯示「尚未載入資料」 | 還沒上傳或載入範例 | 首頁點「🎯 一鍵載入內建範例資料」 |

> 注意：關掉終端機視窗＝關掉網頁。網頁只有在那個視窗（或 `run.bat`）持續執行時才連得上。

## 授權

依專案需求自訂。
