# TechNexion QC WiFi/BT Stress Test Tool

This repository provides a production-line Quality Control (QC) stress test suite for WiFi (QCA9377 and similar) and Bluetooth on TechNexion SoM-based devices. It includes:
- A PyQt5 GUI application that drives tests over UART to the DUT
- A robust shell test script for WiFi throughput validation using iperf
- Configurable SSID group profiles for single or multi-station setups
- A log analyzer tool for post-test inspection
- Optional systemd services to host iperf2 servers

Use this README to install, configure, and run the QC test.

---

## Repository Layout

- `wifi_test_newgui.py` — Main GUI application (PyQt5) for WiFi/BT QC. Drives DUT over serial by invoking `wifi_test.sh`.
- `wifi_test.sh` — Core WiFi validation script. Handles driver bring-up, SSID selection, RSSI checks, connection status, and iperf runs.
- `bt_ping.sh` — Bluetooth validation utility/script.
- `wifi_grp/` — SSID configuration groups:
  - `solo_wifi24g.conf`, `solo_wifi5g.conf`
  - `sta_a_wifi24g.conf`, `sta_a_wifi5g.conf`
  - `sta_b_wifi24g.conf`, `sta_b_wifi5g.conf`
- `wifi_stress_log_analyzer.py` — Python log analyzer for test outputs.
- `wifi_test_installer/` — Prebuilt binaries and installers:
  - `WiFiTestTool` (GUI), `wifi_stress_log_analyzer` (Analyzer)
  - `install_wifi_test_tool.sh`, `install_wifi_log_analyzer.sh` (install scripts)
  - `wifitesttool.desktop` (desktop launcher)
- `iperf`, `iperf2.2.n` — iperf executables for client/server operations.
- `iperfsrv_1.service`, `iperfsrv_2.service` — Optional systemd service units to run iperf2 servers (e.g., ports 5001/5002).
- `WIFI_STA_Group.txt` — Station grouping reference.
- Legacy folders: `GUI_OLD_V1/`, `OLD_QC_Scripts/`, `OLD_GUI/` (historical versions).

---

## Requirements

- A Linux-based host (operator PC) to run the GUI or CLI tools.
- Python 3.9+ (recommended) with pip for source builds.
- PyQt5, pyserial, and pyinstaller (if building from source).
- DUT (Device Under Test) with UART access and WiFi module (e.g., QCA9377).
- Access to SSIDs used for QC:
  - Default Solo SSIDs:
    - 2.4 GHz: `PD-RF-QC-2-4` (PSK hashed in config)
    - 5 GHz: `PD-RF-QC-5` (PSK hashed in config)
- An iperf2 server reachable from the DUT (can be hosted on the operator PC or a lab server).

---

## Quick Start (Use Prebuilt Binaries)

1. Download or clone this repository to your Linux host.
2. Navigate to `wifi_test_installer/`.
3. Install the GUI test tool:
   - `sudo bash install_wifi_test_tool.sh`
4. Install the log analyzer:
   - `sudo bash install_wifi_log_analyzer.sh`
5. Optional: Install a desktop launcher (if not already installed by the script):
   - Copy `wifitesttool.desktop` to `/usr/share/applications/`:
     - `sudo cp wifi_test_installer/wifitesttool.desktop /usr/share/applications/`
6. Launch the GUI:
   - From your application menu: “WiFi Test Tool”
   - Or from terminal: `/opt/technexion/WiFiTestTool` (path may vary based on installer)

---

## DUT Preparation

- Ensure the DUT has UART connected to the operator PC.
- The GUI will open a serial connection and run `bash wifi_test.sh` on the DUT.
- The WiFi driver/interface is auto-detected by `wifi_test.sh`:
  - Common interfaces: `wlan0` (bcmdhd/wlan), `mlan0` (Marvell), etc.
- Make sure the DUT can reach the iperf2 server (same subnet or appropriate routing).
- If using fixed IPs, configure networking appropriately, otherwise DHCP is attempted.

---

## Configure SSID Groups

The QC setup supports different station modes:
- SOLO (default)
- STA-A
- STA-B

Each station maps to SSID configs under `wifi_grp/`:
- SOLO: `solo_wifi24g.conf`, `solo_wifi5g.conf`
- STA-A: `sta_a_wifi24g.conf`, `sta_a_wifi5g.conf`
- STA-B: `sta_b_wifi24g.conf`, `sta_b_wifi5g.conf`

Edit these `.conf` files if you need custom SSIDs or PSKs. Example (solo 2.4G):

```
network={
    ssid="PD-RF-QC-2-4"
    #psk="12345678"
    psk=f0b17e4f1c602704ea15fca2c0c98352663d5c69aeb697bf541a75b824e945ae
}
```

---

## Running Tests (GUI)

1. Connect DUT via serial (UART).
2. Start “WiFi Test Tool”.
3. Select Station (SOLO / STA-A / STA-B). The GUI normalizes various inputs to these three modes.
4. Enter DUT information (S/N and MAC addresses):
   - Supported input formats:
     - `SN,MAC` (single 12-hex MAC → MAC1=MAC, MAC2=dummy)
     - `SN,MAC1,MAC2` (two 12-hex MACs)
     - `SN,001F,7B1E2A54` (scanner-split MAC → combined into MAC1, MAC2=dummy)
5. Press “Start Test”. The GUI will:
   - Drive `wifi_test.sh` on the DUT via UART
   - Optionally run BT validation (`bt_ping.sh`) depending on setup
   - Display live logs and status
6. Test results and logs are saved with enhanced filenames supporting dual MACs:
   - `YYYYMMDD_HHMMSS_SN_MAC1_MAC2_RESULT.txt`
   - Example: `20260102_143025_217522140692_001F7B1E2A54_001F7B1E2A55_PASS.txt`

Note: UI layout is optimized for production:
- Title (TechNexion logo left)
- Device Info
- Configuration (Station/SSID group)
- Control Buttons
- Test Status
- Log Display

---

## Running Tests (CLI)

You can run `wifi_test.sh` directly on the DUT (or via serial session):

- Show help:
  - `bash wifi_test.sh -h` or `bash wifi_test.sh --help`
- Select SSID group:
  - `bash wifi_test.sh -s solo`
  - `bash wifi_test.sh -s grpa`  (Station A)
  - `bash wifi_test.sh -s grpb`  (Station B)
  - Empty `-s` defaults to `solo`
- Set iperf reporting interval:
  - `bash wifi_test.sh -i 1` (default, detailed 1-second sampling)
  - `bash wifi_test.sh -i 5`
  - `bash wifi_test.sh -i 10`
- Set test duration:
  - `bash wifi_test.sh -d l1` / `-d l2` / `-d l3` (QC presets)
  - Or `bash wifi_test.sh -d <seconds>` for custom duration

What the script does:
- Detects WiFi driver and interface (e.g., `wlan0` or `mlan0`)
- Brings up the interface and connects to the selected SSID profiles
- Shows connection status and measures RSSI before and after tests
- Runs iperf client against the server using MBits/sec (`-f m`) output
- Executes both 2.4 GHz and 5 GHz tests (typically 3 attempts each) and aggregates results
- Provides clear pass/fail output and diagnostic hints if issues are detected

---

## Iperf Server Setup (Optional on Operator PC)

If you want to host iperf2 on the operator PC, use the provided systemd units:

1. Copy service files:
   - `sudo cp iperfsrv_1.service /etc/systemd/system/`
   - `sudo cp iperfsrv_2.service /etc/systemd/system/` (if using a second port)
2. Reload and enable:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now iperfsrv_1.service`
   - `sudo systemctl enable --now iperfsrv_2.service`
3. Verify:
   - `systemctl status iperfsrv_1.service`
   - Logs are appended to `/var/log/iperf2-server-5001.log` by default
4. Adjust ports/intervals if needed by editing the unit files:
   - Example ExecStart: `/usr/bin/iperf -s -i 5 -p 5001`

Alternatively, run on demand:
- `./iperf -s -p 5001 -i 1` (from the repo’s iperf binary)
- Ensure firewall allows the chosen port(s).

---

## Log Analysis

Use the GUI’s built-in log view or the separate analyzer:
- Prebuilt analyzer: `/opt/technexion/wifi_stress_log_analyzer` (path may vary)
- Source script: `wifi_stress_log_analyzer.py`
- Analyzer helps parse throughput samples, failures, and station grouping performance.

---

## Build From Source (Optional)

If you prefer building your own executables (for controlled environments):

1. Install dependencies:
   - `sudo apt update`
   - `sudo apt install python3 python3-pip`
   - `pip3 install pyqt5 pyserial pyinstaller`
2. Build the GUI:
   - Using the spec file:
     - `pyinstaller --clean -y wifi_test_newgui_2.spec`
   - Or direct:
     - `pyinstaller -F -w -n WiFiTestTool wifi_test_newgui.py`
3. Build the analyzer:
   - `pyinstaller --clean -y wifi_stress_log_analyzer.spec`
4. Distribute the generated binaries (in `dist/`) to your operator PCs.
5. Optionally install the desktop launcher by placing `wifitesttool.desktop` under `/usr/share/applications/`.

---

## Bluetooth Test (Optional)

If your QC requires BT validation:
- Use `bt_ping.sh` to validate BT connectivity/performance.
- The GUI can incorporate BT test steps and aggregate results alongside WiFi.
- Ensure BlueZ tools are available on the DUT and the target BT device is reachable.

---

## Troubleshooting

- Interface not up:
  - The script auto-loads drivers (`modprobe`). Check dmesg hints (mmc/wlan/qca).
- Cannot connect SSID:
  - Verify `wifi_grp/*.conf` SSID/PSK correctness and AP availability.
- Low throughput:
  - Check RSSI, channel congestion, server reachability, and DUT antenna connection.
- Iperf server unreachable:
  - Confirm IP, port, firewall, and logs at `/var/log/iperf2-server-5001.log`.
- Dual MAC input format:
  - Use `SN,MAC1,MAC2` (both 12-hex) for dual-interface devices.

---

## Notes

- GUI version string is maintained in `wifi_test_newgui.py` (`APP_VERSION`).
- Filenames include dual MACs since 2026-01-02 to better trace multi-radio devices.
- Legacy scripts are kept under `OLD_QC_Scripts/` and `GUI_OLD_V1/` for reference.
