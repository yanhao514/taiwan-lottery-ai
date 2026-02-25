# 🎰 台彩全能大數據分析引擎 (Taiwan Lottery AI)

這是一個基於 Python 與 Streamlit 開發的即時彩券分析工具。利用 Selenium 自動爬取台灣彩券官網的最新開獎結果，並結合大數據統計與 AI 演算法，提供冷熱門號碼分析與拖牌預測。

 
*(這裡之後可以放一張你程式執行時的截圖)*

## 🚀 功能特色

* **自動爬蟲**：一鍵抓取 大樂透、威力彩、今彩539、3星彩、4星彩 最新開獎結果。
* **智慧更新**：自動比對資料庫，只抓取缺少的期數，省時又省流量。
* **AI 策略分析**：
    * 🔥 **全熱門號**：近 20 期最常出現的數字。
    * ❄️ **全冷門號**：近 20 期未出現或極少出現的遺漏字。
    * 🌗 **冷熱平衡**：結合熱門與冷門的平衡策略。
    * 🧩 **拖牌精選**：根據上一期號碼的歷史軌跡，預測下一期最容易被「拖」出來的號碼。
* **視覺化圖表**：提供號碼出現頻率的統計長條圖。
* **報表匯出**：可將分析結果下載為 TXT 檔，方便線下畫單。

## 🛠️ 技術架構

* **語言**：Python 3.9+
* **網頁框架**：Streamlit
* **爬蟲核心**：Selenium + Chromium (Headless Mode)
* **資料處理**：Pandas, Regex

## ☁️ 如何在 Streamlit Cloud 部署

本專案已最佳化，可直接部署於 Streamlit Community Cloud。

1.  Fork 本專案到你的 GitHub。
2.  在 Streamlit Cloud 新增 App，連結此儲存庫。
3.  設定 `packages.txt` 以安裝 Chromium：
    ```text
    chromium
    chromium-driver
    ```
4.  點擊 Deploy 即可使用！

## 📦 本地端安裝與執行

如果你想在自己的電腦上執行：

1.  安裝套件：
    ```bash
    pip install -r requirements.txt
    ```
2.  執行程式：
    ```bash
    streamlit run app.py
    ```

## ⚠️ 免責聲明

* 本工具僅供程式研究與統計分析使用，**不保證中獎**。
* 購買彩券請量力而為，切勿沉迷賭博。

---
*Created by [你的名字] - 2026*
