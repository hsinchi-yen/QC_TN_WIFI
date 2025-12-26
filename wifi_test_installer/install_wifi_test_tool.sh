#!/usr/bin/env bash
set -e

APP_NAME="WiFiTestTool"
APP_ID="wifitesttool"  # 用在 .desktop 檔名與 id
INSTALL_DIR="/opt/wifitest/"

echo "== WiFiTestTool installer =="

# 檢查檔案是否存在（相對於目前目錄）
for f in WiFiTestTool wifi_stress.svg technexion_logo.svg; do
    if [ ! -f "$f" ]; then
        echo "Error: $f not found in current directory."
        exit 1
    fi
done

echo "[1/4] Install binary and UI logo to ${INSTALL_DIR} (need sudo)..."
sudo mkdir -p "${INSTALL_DIR}"
sudo cp WiFiTestTool "${INSTALL_DIR}/"
sudo cp technexion_logo.svg "${INSTALL_DIR}/"
sudo chmod 755 "${INSTALL_DIR}/WiFiTestTool"

echo "[2/4] Install app icon (wifi_stress.svg) to user icon theme..."
ICON_BASE="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
mkdir -p "${ICON_BASE}/scalable/apps"
mkdir -p "${ICON_BASE}/48x48/apps"

cp wifi_stress.svg "${ICON_BASE}/scalable/apps/${APP_ID}.svg"
cp wifi_stress.svg "${ICON_BASE}/48x48/apps/${APP_ID}.svg"

echo "[3/4] Create .desktop launcher..."
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "${DESKTOP_DIR}"

cat > "${DESKTOP_DIR}/${APP_ID}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=WiFi Test Tool
Comment=TechNexion WiFi stress and validation tool
#Exec=${INSTALL_DIR}/WiFiTestTool
Exec=sh -c 'cd /opt/wifitest && ./WiFiTestTool'
Icon=${APP_ID}
Terminal=false
Categories=Network;Utility;
StartupNotify=true
EOF

# 讓桌面環境重新掃描 .desktop 檔，忽略錯誤
if command -v update-desktop-database >/dev/null 2>&1; then
    echo "[4/4] Update desktop database..."
    update-desktop-database "${DESKTOP_DIR}" || true
fi

echo "Done."
echo "You should now see 'WiFi Test Tool' in your application menu with the wifi_stress.svg icon."
