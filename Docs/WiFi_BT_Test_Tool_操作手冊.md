# WiFi / Bluetooth 測試工具操作手冊

**文件版本**: 1.0  
**發布日期**: 2025-12-26  
**適用對象**: 線上操作人員

---

## 目錄

1. [測試環境準備](#1-測試環境準備)
2. [GUI 介面操作說明](#2-gui-介面操作說明)
3. [測試流程說明](#3-測試流程說明)
4. [測試站 SSID 對應表](#4-測試站-ssid-對應表)
5. [故障排除指南](#5-故障排除指南)
6. [附錄 - 命令列模式操作](#6-附錄---命令列模式操作)

---

## 1. 測試環境準備

### 1.1 DUT Image 確認

在開始測試前，請確認 DUT (Device Under Test) 的測試 Image 符合以下條件：

| 檢查項目 | 說明 |
|---------|------|
| **Image 日期** | 必須為 **2025/12/24** 之後版本 |
| **測試腳本** | 確認 DUT 內含以下檔案：<br>• `/wifi_grp/` 資料夾 (含 6 個 .conf 設定檔)<br>• `wifi_test.sh`<br>• `bt_ping.sh` |

### 1.2 硬體連接

1. 將 UART 線連接至 Host PC 與 DUT
2. 確認 DUT 電源已開啟
3. 確認測試站 AP (Access Point) 已開機並運作正常

### 1.3 Host PC BT Dongle

若需進行 BT 測試，請確認：
- Host PC 已安裝藍牙 Dongle
- 藍牙 Dongle 狀態為 UP RUNNING

---

## 2. GUI 介面操作說明

### 2.1 啟動工具

執行 `wifi_test_newgui.py` 或對應的執行檔。

### 2.2 介面區域說明

```
┌─────────────────────────────────────────────────────────────┐
│  [TechNexion Logo]   WiFi / Bluetooth Stress Test           │
├─────────────────────────────────────────────────────────────┤
│  Device Information                                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ UART Port: [下拉選單]        [Refresh]              │    │
│  │ SN,MAC:    [輸入欄位]        [Clear]                │    │
│  │ Test Date: 2025-12-26                               │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Configuration                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ WiFi Band: [5G] [2.4G]    Test Level: [L0-L3]       │    │
│  │ BT Priority: [WiFi First] [BT First] [Disable]      │    │
│  │ Host BT MAC: [下拉選單/顯示]                         │    │
│  │ WIFI Station: [Solo/Station A/Station B]            │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  [Start Test]                    [Terminate Test]           │
├─────────────────────────────────────────────────────────────┤
│  Test Status                                                │
│  WiFi: [---]  BT: [---]  Overall: [Ready]  Time: [00:00]   │
├─────────────────────────────────────────────────────────────┤
│  Test Execution Log                            [Watch]      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ (Log 顯示區)                                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 各區域功能說明

#### 2.3.1 Device Information (設備資訊)

| 欄位 | 說明 |
|-----|------|
| **UART Port** | 選擇連接 DUT 的串口<br>• 自動篩選 ttyUSB* 與 ttyACM* 裝置<br>• 點擊 **[Refresh]** 重新掃描 |
| **SN,MAC** | 輸入 DUT 的序號與 MAC 位址<br>• 格式: `序號,MAC` (如: `217522140692,001F7B1E2A54`)<br>• 點擊 **[Clear]** 清除欄位並重置狀態 |
| **Test Date** | 自動顯示當前日期 |

#### 2.3.2 Configuration (測試設定)

| 選項 | 說明 |
|-----|------|
| **WiFi Band Priority** | 選擇優先測試的頻段<br>• **5G** (預設): 先測 5GHz，再測 2.4GHz<br>• **2.4G**: 先測 2.4GHz，再測 5GHz |
| **Test Level** | 選擇測試時間長度<br>• **L0**: 10 秒 (快速檢測)<br>• **L1**: 30 秒 (快速驗證)<br>• **L2**: 120 秒 (標準測試，預設)<br>• **L3**: 180 秒 (延長壓力測試) |
| **BT Test Priority** | 選擇 BT 測試順序<br>• **WiFi First** (預設): 先測 WiFi，後測 BT<br>• **BT First**: 先測 BT，後測 WiFi (自動鎖定 5G 優先)<br>• **Disable**: 不執行 BT 測試 |
| **Host BT MAC** | 顯示 Host PC 的藍牙 MAC 位址<br>• 若有多個 BT Dongle，可選擇要使用的裝置 |
| **WIFI Station** | 選擇測試站使用的 AP 設定<br>• **Solo**: 獨立測試站<br>• **Station A**: A 組測試站<br>• **Station B**: B 組測試站 |

#### 2.3.3 Control Buttons (控制按鈕)

| 按鈕 | 功能 |
|-----|------|
| **Start Test** | 開始執行測試 (綠色按鈕) |
| **Terminate Test** | 中斷執行中的測試 (紅色按鈕) |

#### 2.3.4 Test Status (測試狀態)

| 狀態欄 | 說明 |
|-------|------|
| **WiFi** | WiFi 測試狀態 (---, Testing, PASS, FAIL) |
| **BT** | BT 測試狀態 (---, Testing, PASS, FAIL) |
| **Overall** | 整體狀態 (Ready, Testing, PASS, FAIL) |
| **Test Time** | 測試經過時間 (MM:SS 格式) |

#### 2.3.5 Test Execution Log (測試記錄)

| 功能 | 說明 |
|-----|------|
| **Log 顯示區** | 即時顯示測試過程的詳細記錄 |
| **Watch 按鈕** | 監控 Console 輸出 (等待 DUT 開機完成) |

---

## 3. 測試流程說明

### 3.1 標準測試流程

```
步驟1: 選擇 UART Port
       ↓
步驟2: 設定測試參數 (Band / Level / BT Priority / Station)
       ↓
步驟3: 輸入 SN,MAC (自動啟動測試)
       或
       點擊 [Start Test] 按鈕
       ↓
步驟4: 等待測試完成
       ↓
步驟5: 查看測試結果 (PASS/FAIL 對話框)
       ↓
步驟6: 點擊 [Clear] 準備下一台 DUT
```

### 3.2 操作步驟詳解

#### 步驟 1: 選擇 UART Port

1. 點擊 **UART Port** 下拉選單
2. 選擇對應的串口 (如: `/dev/ttyUSB0`)
3. 確認 **Overall** 狀態顯示為 **Ready** (藍色)

> ⚠️ 若顯示 **Device Not Connected** (紅色)，請檢查連接線或 DUT 電源

#### 步驟 2: 設定測試參數

根據測試需求設定以下選項：

| 參數 | 一般測試建議值 |
|-----|--------------|
| WiFi Band | 5G (預設) |
| Test Level | L2 (標準 120 秒) |
| BT Priority | WiFi First (預設) |
| WIFI Station | 依據實際測試站選擇 |

#### 步驟 3: 輸入 SN,MAC 或啟動測試

**自動啟動**: 在 SN,MAC 欄位輸入完整資訊後，系統自動開始測試
- 格式: `序號,MAC` (如: `217522140692,001F7B1E2A54`)

**手動啟動**: 點擊 **[Start Test]** 按鈕

#### 步驟 4: 等待測試完成

測試過程中：
- **WiFi/BT 狀態欄** 會顯示 **Testing** (橙色)
- **Log 區域** 會即時顯示測試過程
- **Test Time** 會顯示經過時間

> 💡 若需中斷測試，點擊 **[Terminate Test]** 按鈕

#### 步驟 5: 查看測試結果

測試完成後會彈出結果對話框：
- **PASS** (綠色): 測試通過
- **FAIL** (紅色): 測試失敗

對話框會在 10 秒後自動關閉，或點擊 **OK** 立即關閉。

#### 步驟 6: 準備下一台測試

點擊 **[Clear]** 按鈕：
- 清除 SN,MAC 欄位
- 重置所有狀態為初始值
- 清空 Log 記錄

---

## 4. 測試站 SSID 對應表

### 4.1 WIFI Station 選項對應

| Station 選項 | 5G SSID | 2.4G SSID | 設定檔路徑 |
|-------------|---------|-----------|-----------|
| **Solo** | PD-RF-QC-5 | PD-RF-QC-2-4 | `/wifi_grp/solo_wifi*.conf` |
| **Station A** | PD-RF-QC-5-STA-A | PD-RF-QC-2-4-STA-A | `/wifi_grp/sta_a_wifi*.conf` |
| **Station B** | PD-RF-QC-5-STA-B | PD-RF-QC-2-4-STA-B | `/wifi_grp/sta_b_wifi*.conf` |

### 4.2 AP 設定詳情

#### Solo (獨立測試站)

| 項目 | 5G | 2.4G |
|-----|----|----|
| SSID | PD-RF-QC-5 | PD-RF-QC-2-4 |
| Channel | 36/40/44/48 | 1, 6, 11 |
| Password | 12345678 | 12345678 |

#### Station A (A 組測試站)

| 項目 | 5G | 2.4G |
|-----|----|----|
| SSID | PD-RF-QC-5-STA-A | PD-RF-QC-2-4-STA-A |
| Channel | 36/40/44/48 | 1, 6, 11 |
| Password | 12345678 | 12345678 |

#### Station B (B 組測試站)

| 項目 | 5G | 2.4G |
|-----|----|----|
| SSID | PD-RF-QC-5-STA-B | PD-RF-QC-2-4-STA-B |
| Channel | 36/40/44/48 | 1, 6, 11 |
| Password | 12345678 | 12345678 |

> ⚠️ **重要**: 請確認選擇的 Station 與實際測試站 AP 一致

---

## 5. 故障排除指南

### 5.1 常見問題與解決方案

#### 問題 1: UART Port 顯示 "No valid ports found"

**原因**: 系統未偵測到串口裝置

**解決方案**:
1. 檢查 UART 線是否正確連接
2. 確認 DUT 電源已開啟
3. 點擊 **[Refresh]** 重新掃描
4. 若使用 USB 轉 UART，確認驅動程式已安裝

#### 問題 2: Overall 狀態顯示 "Device Not Connected"

**原因**: 無法偵測到 DUT 的 prompt

**解決方案**:
1. 確認 DUT 已完成開機 (使用 **Watch** 功能監控)
2. 檢查 UART 線連接是否正確
3. 確認 Baud Rate 設定正確 (預設 115200)

#### 問題 3: WiFi 測試失敗 - wlan0 interface not found

**原因**: WiFi 網路介面未啟動

**解決方案**:
1. 確認 DUT Image 版本正確 (≥ 2025/12/24)
2. 確認 WiFi 模組已正確安裝
3. 重新刷入測試 Image

#### 問題 4: WiFi 測試失敗 - Throughput 過低

**原因**: WiFi 連線品質不佳或 AP 問題

**解決方案**:
1. 確認 DUT 與 AP 距離適中 (建議 1-3 公尺)
2. 確認 AP 運作正常
3. 檢查是否有其他干擾源
4. 確認選擇正確的 WIFI Station

#### 問題 5: BT 測試失敗 - HCI device not found

**原因**: 藍牙裝置初始化失敗

**解決方案**:
1. 確認 Host PC BT Dongle 狀態為 UP
2. 確認 DUT 的 BT 功能正常
3. 嘗試重新執行測試

#### 問題 6: BT 測試失敗 - l2ping failed

**原因**: 藍牙連線測試失敗

**解決方案**:
1. 確認 Host PC BT Dongle 距離 DUT 在有效範圍內 (< 5 公尺)
2. 減少周圍藍牙干擾
3. 嘗試更換 BT Dongle

### 5.2 使用 Watch 功能監控 DUT 開機

當 DUT 處於開機中或未偵測到 prompt 時：

1. 點擊 **[Watch]** 按鈕
2. 觀察 Log 輸出，等待系統開機完成
3. 當偵測到 `_qc:~#` prompt 時，Watch 模式自動停止
4. **Overall** 狀態變為 **Ready**，可開始測試

---

## 6. 附錄 - 命令列模式操作

當需要手動排除問題時，可透過 UART Console 直接操作測試腳本。

### 6.1 WiFi 測試腳本 (wifi_test.sh)

#### 基本用法

```bash
bash wifi_test.sh [選項]
```

#### 參數說明

| 參數 | 說明 | 範例 |
|-----|------|------|
| `-h, --help` | 顯示說明 | `bash wifi_test.sh -h` |
| `-d, --duration` | 測試時間<br>l0=10s, l1=30s, l2=120s, l3=180s<br>或自訂秒數 | `bash wifi_test.sh -d l1`<br>`bash wifi_test.sh -d 60` |
| `-c, --channel` | WiFi 頻段優先順序<br>ax=5G 優先, bgn=2.4G 優先 | `bash wifi_test.sh -c bgn` |
| `-s, --ssid` | SSID 群組選擇<br>solo, grpa, grpb | `bash wifi_test.sh -s grpa` |
| `-i, --interval` | iperf 顯示間隔 (1, 5, 10 秒) | `bash wifi_test.sh -i 5` |

#### 常用組合範例

```bash
# 標準測試 (L2, 5G 優先, Solo 站)
bash wifi_test.sh

# 快速測試 (L0, 10 秒)
bash wifi_test.sh -d l0

# 使用 Station A 設定
bash wifi_test.sh -s grpa

# 2.4G 優先測試
bash wifi_test.sh -c bgn

# 完整設定範例
bash wifi_test.sh -d l2 -c ax -s grpb -i 1
```

### 6.2 BT 測試腳本 (bt_ping.sh)

#### 基本用法

```bash
bash bt_ping.sh [BT_MAC]
```

#### 參數說明

| 參數 | 說明 | 範例 |
|-----|------|------|
| `BT_MAC` | 目標藍牙 MAC 位址 (選填) | `bash bt_ping.sh E8:48:B8:C8:20:00` |

若未提供 MAC，腳本會自動掃描附近的藍牙裝置。

#### 使用環境變數

```bash
# 設定環境變數後執行
BT_MAC=E8:48:B8:C8:20:00 bash bt_ping.sh
```

### 6.3 測試判定標準

#### WiFi 測試

| 頻段 | Throughput 門檻 |
|-----|----------------|
| 5GHz | ≥ 50 Mbps |
| 2.4GHz | ≥ 10 Mbps |

#### BT 測試

| 項目 | 標準 |
|-----|------|
| l2ping | 0% packet loss |
| 最大嘗試次數 | 6 次 |

---

## 附錄 A: Log 檔案說明

測試完成後，Log 檔案自動儲存於：

```
wifi_stress_log_YYYYMMDD/
└── YYYYMMDD_HHMMSS_序號_MAC_結果.txt
```

範例：`wifi_stress_log_20251226/20251226_143500_217522140692_001F7B1E2A54_PASS.txt`

---

## 附錄 B: 測試結果狀態說明

| 狀態 | 顏色 | 說明 |
|-----|------|------|
| `---` | 灰色 | 未執行/待測試 |
| `Testing` | 橙色 | 測試進行中 |
| `PASS` | 綠色 | 測試通過 |
| `FAIL` | 紅色 | 測試失敗 |
| `Ready` | 藍色 | 設備就緒，可開始測試 |
| `Device Not Connected` | 紅色 | 設備未連接 |
| `Terminated` | 灰色 | 測試已中斷 |

---

**文件結束**

如有任何問題，請聯繫 RD 團隊。
