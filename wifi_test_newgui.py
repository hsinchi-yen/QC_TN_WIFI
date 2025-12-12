#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WiFi Stress Test Tool for Production Line
Author: Production Test Team
Date: 2025-12-11
Description: UART-based WiFi throughput test tool for QCA9377 on SoM platforms.
"""

import sys
import os
import serial
import serial.tools.list_ports
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QTextEdit, QLineEdit, QGroupBox, QGridLayout,
                             QSizePolicy)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QPalette, QColor
import re
import time


class SerialWorker(QThread):
    """串口工作線程"""
    log_received = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    test_completed = pyqtSignal(str, str, str, str)  # wifi_result, bt_result, full_log, bt_mac
    wifi_completed = pyqtSignal(str)  # wifi test result
    bt_started = pyqtSignal()  # bt test started signal
    bt_completed = pyqtSignal(str)  # bt test completed signal with result
    wifi_started = pyqtSignal()  # wifi test started signal (for BT first mode)
    
    @staticmethod
    def clean_terminal_output(text):
        """清理終端控制字符，避免動態輸出問題"""
        # 移除 ANSI 轉義序列（顏色代碼等）
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text)
        
        # 處理回車符：只保留回車符後的內容（覆蓋前面的內容）
        if '\r' in text:
            # 分割成行
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                if '\r' in line:
                    # 回車符表示覆蓋，只保留最後一個 \r 之後的內容
                    parts = line.split('\r')
                    # 過濾掉空字符串，保留最後一個非空部分
                    non_empty = [p for p in parts if p.strip()]
                    if non_empty:
                        cleaned_lines.append(non_empty[-1])
                else:
                    cleaned_lines.append(line)
            text = '\n'.join(cleaned_lines)
        
        return text
    
    def __init__(self, port, baudrate=115200, test_command="bash wifi_test.sh", bt_mac="", bt_first=False):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_running = False
        self.should_terminate = False
        self.full_log = ""
        self.test_command = test_command
        self.bt_mac = bt_mac
        self.bt_first = bt_first
        self.wifi_result = "UNKNOWN"
        self.bt_result = "UNKNOWN"
        
    def run(self):
        """執行測試流程"""
        try:
            # 打開串口
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5
            )
            
            # 等待系統就緒
            self.status_changed.emit("Ready")
            prompt_detected = self.wait_for_prompt()
            
            if not prompt_detected:
                # 未偵測到設備連接
                self.log_received.emit("\nERROR: Device not connected or login prompt not detected!")
                self.status_changed.emit("Device Not Connected")
                self.test_completed.emit("NOT_CONNECTED", "SKIP", "", "")
                self.cleanup()
                return
            
            if self.should_terminate:
                self.cleanup()
                return
            
            # 根據 bt_first 決定測試順序
            if self.bt_first and self.bt_mac:
                # BT 優先測試
                self.log_received.emit("\n" + "=" * 60)
                self.log_received.emit("BT Test Priority Mode: Testing BT first")
                self.log_received.emit("=" * 60)
                self.status_changed.emit("Testing")
                self.bt_started.emit()
                self.run_bt_test_first()
                # BT First 模式自己處理完整流程，直接返回
                return
            else:
                # WiFi 優先測試（原有邏輯）
                self.status_changed.emit("Testing")
                command = self.test_command + "\n"
                self.serial_conn.write(command.encode('utf-8'))
                self.log_received.emit(f">>> Sent command: {command.strip()}")
            
            # 讀取測試輸出
            self.is_running = True
            while self.is_running:
                if self.should_terminate:
                    # 發送 Ctrl+C 中斷
                    self.serial_conn.write(b'\x03')
                    self.log_received.emit("\n>>> Sent Ctrl+C (Termination signal)")
                    time.sleep(0.5)
                    self.wait_for_prompt()
                    self.status_changed.emit("Terminated")
                    self.test_completed.emit("TERMINATED", "SKIP", self.full_log, "")
                    break
                
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        # 清理終端控制字符
                        line = self.clean_terminal_output(line)
                        # 只在有實際內容時才記錄和顯示
                        if line and line.strip():
                            self.full_log += line
                            self.log_received.emit(line.rstrip())
                            
                            # WiFi 測試完成行
                            if line and "WiFi Test Result:" in line and ("PASSED" in line or "FAILED" in line):
                                # 多讀取幾行以確保完整捕獲測試結果
                                for _ in range(5):
                                    extra = self.serial_conn.readline().decode('utf-8', errors='ignore')
                                    extra = self.clean_terminal_output(extra)
                                    if extra and extra.strip():
                                        self.full_log += extra
                                        self.log_received.emit(extra.rstrip())
                                
                                # 解析 WiFi 結果
                                self.wifi_result = self.parse_test_result(line)
                                self.log_received.emit("\n" + "=" * 60)
                                self.log_received.emit(f"WiFi Test Result: {self.wifi_result}")
                                self.log_received.emit("=" * 60)
                                self.wifi_completed.emit(self.wifi_result)
                                
                                # 如果有 BT MAC，繼續執行 BT 測試
                                if self.bt_mac and not self.should_terminate:
                                    self.log_received.emit("\n" + "=" * 60)
                                    self.log_received.emit("Starting Bluetooth Test...")
                                    self.log_received.emit(f"BT MAC: {self.bt_mac}")
                                    self.log_received.emit("=" * 60)
                                    self.bt_started.emit()
                                    
                                    # 執行 BT 測試
                                    self.run_bt_test()
                                else:
                                    # 沒有 BT 測試，直接完成
                                    self.is_running = False
                                    self.status_changed.emit(self.wifi_result)
                                    self.test_completed.emit(self.wifi_result, "SKIP", self.full_log, "")
                                break
                    except Exception as e:
                        self.log_received.emit(f"Error reading serial: {str(e)}")
                        
                time.sleep(0.01)
                
        except serial.SerialException as e:
            self.log_received.emit(f"Serial port error: {str(e)}")
            self.status_changed.emit("Stop")
            self.test_completed.emit("FAIL", "SKIP", self.full_log, "")
        except Exception as e:
            self.log_received.emit(f"Unexpected error: {str(e)}")
            self.status_changed.emit("Stop")
            self.test_completed.emit("FAIL", "SKIP", self.full_log, "")
        finally:
            self.cleanup()
    
    def run_bt_test_first(self):
        """BT 優先測試模式：先執行 BT 測試，再執行 WiFi 測試"""
        try:
            # 等待 prompt
            if not self.wait_for_prompt():
                self.log_received.emit("ERROR: Cannot detect prompt for BT test")
                self.bt_result = "FAIL"
                self.is_running = False
                self.test_completed.emit("SKIP", self.bt_result, self.full_log, self.bt_mac)
                return
            
            # 發送 BT 測試命令
            bt_command = f"bash bt_ping.sh {self.bt_mac}\n"
            self.serial_conn.write(bt_command.encode('utf-8'))
            self.log_received.emit(f">>> Sent command: {bt_command.strip()}")
            time.sleep(0.5)
            
            # 讀取 BT 測試輸出
            while not self.should_terminate:
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        # 清理終端控制字符
                        line = self.clean_terminal_output(line)
                        self.full_log += line
                        if line.strip():
                            self.log_received.emit(line.rstrip())
                        
                        # 檢測 BT 測試結果
                        if "Bluetooth Test Result:" in line:
                            # 讀取剩餘幾行
                            for _ in range(3):
                                extra = self.serial_conn.readline().decode('utf-8', errors='ignore')
                                extra = self.clean_terminal_output(extra)
                                self.full_log += extra
                                self.log_received.emit(extra.rstrip())
                            
                            # 解析 BT 結果
                            self.bt_result = self.parse_test_result(line)
                            self.log_received.emit("\n" + "=" * 60)
                            self.log_received.emit(f"Bluetooth Test Result: {self.bt_result}")
                            self.log_received.emit("=" * 60)
                            
                            # 發送 BT 測試完成信號
                            self.bt_completed.emit(self.bt_result)
                            
                            # BT 測試完成，開始 WiFi 測試
                            if not self.should_terminate:
                                self.log_received.emit("\n" + "=" * 60)
                                self.log_received.emit("Starting WiFi Test...")
                                self.log_received.emit("=" * 60)
                                # 發送 WiFi 測試開始信號
                                self.wifi_started.emit()
                                self.run_wifi_test_after_bt()
                            break
                    except Exception as e:
                        self.log_received.emit(f"Error reading BT test: {str(e)}")
                        
                time.sleep(0.01)
                
        except Exception as e:
            self.log_received.emit(f"BT test error: {str(e)}")
            self.bt_result = "FAIL"
            self.is_running = False
            self.test_completed.emit("SKIP", self.bt_result, self.full_log, self.bt_mac)
    
    def run_wifi_test_after_bt(self):
        """BT 測試後執行 WiFi 測試"""
        try:
            # 等待 prompt
            if not self.wait_for_prompt():
                self.log_received.emit("ERROR: Cannot detect prompt for WiFi test")
                self.wifi_result = "FAIL"
                self.is_running = False
                self.test_completed.emit(self.wifi_result, self.bt_result, self.full_log, self.bt_mac)
                return
            
            # 發送 WiFi 測試命令
            command = self.test_command + "\n"
            self.serial_conn.write(command.encode('utf-8'))
            self.log_received.emit(f">>> Sent command: {command.strip()}")
            time.sleep(0.5)
            
            # 讀取 WiFi 測試輸出
            while not self.should_terminate:
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        # 清理終端控制字符
                        line = self.clean_terminal_output(line)
                        # 只在有實際內容時才記錄和顯示
                        if line and line.strip():
                            self.full_log += line
                            self.log_received.emit(line.rstrip())
                        
                        # 檢測 WiFi 測試結果
                        if line and "WiFi Test Result:" in line and ("PASSED" in line or "FAILED" in line):
                            # 讀取剩餘幾行
                            for _ in range(5):
                                extra = self.serial_conn.readline().decode('utf-8', errors='ignore')
                                extra = self.clean_terminal_output(extra)
                                if extra and extra.strip():
                                    self.full_log += extra
                                    self.log_received.emit(extra.rstrip())
                            
                            # 解析 WiFi 結果
                            self.wifi_result = self.parse_test_result(line)
                            self.log_received.emit("\n" + "=" * 60)
                            self.log_received.emit(f"WiFi Test Result: {self.wifi_result}")
                            self.log_received.emit("=" * 60)
                            self.wifi_completed.emit(self.wifi_result)
                            
                            # 所有測試完成
                            self.is_running = False
                            final_result = "PASS" if self.wifi_result == "PASS" and self.bt_result == "PASS" else "FAIL"
                            self.status_changed.emit(final_result)
                            self.test_completed.emit(self.wifi_result, self.bt_result, self.full_log, self.bt_mac)
                            break
                    except Exception as e:
                        self.log_received.emit(f"Error reading WiFi test: {str(e)}")
                        
                time.sleep(0.01)
                
        except Exception as e:
            self.log_received.emit(f"WiFi test error: {str(e)}")
            self.wifi_result = "FAIL"
            self.is_running = False
            self.test_completed.emit(self.wifi_result, self.bt_result, self.full_log, self.bt_mac)
    
    def run_bt_test(self):
        """執行藍牙測試"""
        try:
            # 等待 prompt
            if not self.wait_for_prompt():
                self.log_received.emit("ERROR: Cannot detect prompt for BT test")
                self.bt_result = "FAIL"
                self.is_running = False
                self.test_completed.emit(self.wifi_result, self.bt_result, self.full_log, self.bt_mac)
                return
            
            # 發送 BT 測試命令
            bt_command = f"bash bt_ping.sh {self.bt_mac}\n"
            self.serial_conn.write(bt_command.encode('utf-8'))
            time.sleep(0.5)
            
            # 讀取 BT 測試輸出
            bt_log_started = False
            while not self.should_terminate:
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        # 清理終端控制字符
                        line = self.clean_terminal_output(line)
                        # 只在有實際內容時才記錄和顯示
                        if line and line.strip():
                            self.full_log += line
                            self.log_received.emit(line.rstrip())
                        
                        # 檢測 BT 測試結果
                        if line and "Bluetooth Test Result:" in line:
                            # 讀取剩餘幾行
                            for _ in range(3):
                                extra = self.serial_conn.readline().decode('utf-8', errors='ignore')
                                extra = self.clean_terminal_output(extra)
                                if extra and extra.strip():
                                    self.full_log += extra
                                    self.log_received.emit(extra.rstrip())
                                    self.log_received.emit(extra.rstrip())
                            
                            # 解析 BT 結果
                            self.bt_result = self.parse_test_result(line)
                            self.log_received.emit("\n" + "=" * 60)
                            self.log_received.emit(f"Bluetooth Test Result: {self.bt_result}")
                            self.log_received.emit("=" * 60)
                            
                            # 完成所有測試
                            self.is_running = False
                            final_result = "PASS" if self.wifi_result == "PASS" and self.bt_result == "PASS" else "FAIL"
                            self.status_changed.emit(final_result)
                            self.test_completed.emit(self.wifi_result, self.bt_result, self.full_log, self.bt_mac)
                            break
                    except Exception as e:
                        self.log_received.emit(f"Error reading BT test: {str(e)}")
                        
                time.sleep(0.01)
                
        except Exception as e:
            self.log_received.emit(f"BT test error: {str(e)}")
            self.bt_result = "FAIL"
            self.is_running = False
            self.test_completed.emit(self.wifi_result, self.bt_result, self.full_log, self.bt_mac)
    
    def wait_for_prompt(self):
        """等待命令提示符 _qc:~#，返回是否成功偵測到"""
        timeout = 3
        start_time = time.time()
        buffer = ""
        
        # 先發送 Enter 鍵來觸發 prompt 顯示
        try:
            self.serial_conn.write(b'\n')
            time.sleep(0.2)
        except:
            pass
        
        while time.time() - start_time < timeout:
            if self.should_terminate:
                return False
                
            if self.serial_conn.in_waiting > 0:
                try:
                    data = self.serial_conn.read(self.serial_conn.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    if data.strip():  # 只顯示非空內容
                        self.log_received.emit(data.rstrip())
                    
                    if "_qc:~#" in buffer or "root@" in buffer or "#" in buffer:
                        return True
                except:
                    pass
            time.sleep(0.1)
        
        # Timeout - 未偵測到 prompt
        return False
    
    def parse_test_result(self, line):
        """解析測試結果"""
        if "PASSED" in line:
            return "PASS"
        elif "FAILED" in line:
            return "FAIL"
        else:
            return "UNKNOWN"
    
    def terminate_test(self):
        """中斷測試"""
        self.should_terminate = True
    
    def cleanup(self):
        """清理串口連接"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()


class WiFiTestGUI(QMainWindow):
    """WiFi壓力測試主視窗"""
    
    def __init__(self):
        super().__init__()
        self.serial_worker = None
        self.test_elapsed_seconds = 0
        self.host_bt_mac = ""  # 初始化 BT MAC 變數
        self.init_ui()
        self.refresh_ports()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("WiFi Test Tool - Designed by TechNexion")
        self.setGeometry(100, 100, 1000, 700)
        self.setStyleSheet("QMainWindow { background-color: #f0f0f0; }")
        
        # 主widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # 標題
        title_label = QLabel("WiFi / Bluetooth Stress Test - Burn In")
        title_font = QFont("Arial", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
        main_layout.addWidget(title_label)
        
        # 設備信息區
        info_group = QGroupBox("Device Information")
        info_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        info_layout = QGridLayout()
        info_group.setLayout(info_layout)
        
        # UART端口選擇
        info_layout.addWidget(QLabel("UART Port:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(200)
        self.port_combo.currentIndexChanged.connect(self.check_port_connection)
        info_layout.addWidget(self.port_combo, 0, 1)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        info_layout.addWidget(refresh_btn, 0, 2)
        
        # SN,MAC輸入
        info_layout.addWidget(QLabel("SN,MAC:"), 1, 0)
        self.sn_mac_input = QLineEdit()
        self.sn_mac_input.setPlaceholderText("Enter SN,MAC (e.g., 217522140692,001F7B1E2A54)")
        self.sn_mac_input.textChanged.connect(self.on_sn_mac_changed)
        info_layout.addWidget(self.sn_mac_input, 1, 1)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_sn_mac)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        info_layout.addWidget(clear_btn, 1, 2)
        
        # 日期顯示
        info_layout.addWidget(QLabel("Test Date:"), 2, 0)
        self.date_label = QLabel(datetime.now().strftime("%Y-%m-%d"))
        self.date_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        info_layout.addWidget(self.date_label, 2, 1)
        
        main_layout.addWidget(info_group)
        
        # 狀態顯示區
        status_group = QGroupBox("Test Status")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)  # 減少元件之間的間距
        status_layout.setContentsMargins(10, 5, 10, 5)
        status_group.setLayout(status_layout)
        
        # WiFi 狀態
        wifi_label = QLabel("WiFi:")
        wifi_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        status_layout.addWidget(wifi_label)
        self.wifi_status_label = QLabel("---")
        self.wifi_status_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.wifi_status_label.setAlignment(Qt.AlignCenter)
        self.wifi_status_label.setMinimumHeight(40)
        self.wifi_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_test_status_color(self.wifi_status_label, "IDLE")
        status_layout.addWidget(self.wifi_status_label)

        
        # BT 狀態
        bt_label = QLabel("BT:")
        bt_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        status_layout.addWidget(bt_label)
        self.bt_status_label = QLabel("---")
        self.bt_status_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.bt_status_label.setAlignment(Qt.AlignCenter)
        self.bt_status_label.setMinimumHeight(40)
        self.bt_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_test_status_color(self.bt_status_label, "IDLE")
        status_layout.addWidget(self.bt_status_label)

        
        # Overall 狀態
        overall_label = QLabel("Overall:")
        overall_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        status_layout.addWidget(overall_label)
        self.status_label = QLabel("Stop")
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumHeight(40)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_status_color("Stop")
        status_layout.addWidget(self.status_label)

        
        # 測試時間顯示
        time_label = QLabel("Test Time:")
        time_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        status_layout.addWidget(time_label)
        self.time_label = QLabel("0 sec")
        self.time_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setMinimumHeight(40)
        self.time_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.time_label.setStyleSheet("""
            QLabel {
                background-color: #34495e;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        status_layout.addWidget(self.time_label)
        
        main_layout.addWidget(status_group)
        
        # Configuration 選項區
        config_group = QGroupBox("Configuration")
        config_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        config_layout = QHBoxLayout()
        config_group.setLayout(config_layout)
        
        config_layout.addWidget(QLabel("WiFi Band Priority:"))
        
        self.band_5g_btn = QPushButton("5G")
        self.band_5g_btn.setCheckable(True)
        self.band_5g_btn.setChecked(True)  # 預設選擇 5G
        self.band_5g_btn.clicked.connect(lambda: self.select_band("5G"))
        self.band_5g_btn.setMinimumHeight(40)
        self.band_5g_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #27ae60;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #229954;
            }
        """)
        config_layout.addWidget(self.band_5g_btn)
        
        self.band_24g_btn = QPushButton("2.4G")
        self.band_24g_btn.setCheckable(True)
        self.band_24g_btn.clicked.connect(lambda: self.select_band("2.4G"))
        self.band_24g_btn.setMinimumHeight(40)
        self.band_24g_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #27ae60;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #229954;
            }
        """)
        config_layout.addWidget(self.band_24g_btn)
        
        config_layout.addStretch()
        
        # Test Level 選項
        config_layout.addWidget(QLabel("Test Level:"))
        
        self.level_l0_btn = QPushButton("L0")
        self.level_l0_btn.setCheckable(True)
        self.level_l0_btn.setChecked(False)
        self.level_l0_btn.clicked.connect(lambda: self.select_test_level("l0"))
        self.level_l0_btn.setMinimumHeight(40)
        self.level_l0_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #16a085;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #138d75;
            }
        """)
        config_layout.addWidget(self.level_l0_btn)
        
        self.level_l1_btn = QPushButton("L1")
        self.level_l1_btn.setCheckable(True)
        self.level_l1_btn.setChecked(False)
        self.level_l1_btn.clicked.connect(lambda: self.select_test_level("l1"))
        self.level_l1_btn.setMinimumHeight(40)
        self.level_l1_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #16a085;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #138d75;
            }
        """)
        config_layout.addWidget(self.level_l1_btn)
        
        self.level_l2_btn = QPushButton("L2")
        self.level_l2_btn.setCheckable(True)
        self.level_l2_btn.setChecked(True)  # 預設選擇 L2
        self.level_l2_btn.clicked.connect(lambda: self.select_test_level("l2"))
        self.level_l2_btn.setMinimumHeight(40)
        self.level_l2_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #16a085;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #138d75;
            }
        """)
        config_layout.addWidget(self.level_l2_btn)
        
        self.level_l3_btn = QPushButton("L3")
        self.level_l3_btn.setCheckable(True)
        self.level_l3_btn.setChecked(False)
        self.level_l3_btn.clicked.connect(lambda: self.select_test_level("l3"))
        self.level_l3_btn.setMinimumHeight(40)
        self.level_l3_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #16a085;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #138d75;
            }
        """)
        config_layout.addWidget(self.level_l3_btn)
        
        config_layout.addStretch()
        
        # BT Test Priority 選項
        config_layout.addWidget(QLabel("BT Test Priority:"))
        
        self.bt_wifi_first_btn = QPushButton("WiFi First")
        self.bt_wifi_first_btn.setCheckable(True)
        self.bt_wifi_first_btn.setChecked(True)  # 預設選擇 WiFi First
        self.bt_wifi_first_btn.clicked.connect(lambda: self.select_bt_priority("WiFi First"))
        self.bt_wifi_first_btn.setMinimumHeight(40)
        self.bt_wifi_first_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #3498db;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #2980b9;
            }
        """)
        config_layout.addWidget(self.bt_wifi_first_btn)
        
        self.bt_first_btn = QPushButton("BT First")
        self.bt_first_btn.setCheckable(True)
        self.bt_first_btn.setChecked(False)
        self.bt_first_btn.clicked.connect(lambda: self.select_bt_priority("BT First"))
        self.bt_first_btn.setMinimumHeight(40)
        self.bt_first_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #9b59b6;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #8e44ad;
            }
        """)
        config_layout.addWidget(self.bt_first_btn)
        
        self.bt_disable_btn = QPushButton("Disable")
        self.bt_disable_btn.setCheckable(True)
        self.bt_disable_btn.setChecked(False)
        self.bt_disable_btn.clicked.connect(lambda: self.select_bt_priority("Disable"))
        self.bt_disable_btn.setMinimumHeight(40)
        self.bt_disable_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #e74c3c;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked:hover {
                background-color: #c0392b;
            }
        """)
        config_layout.addWidget(self.bt_disable_btn)
        
        config_layout.addStretch()
        
        # BT MAC 下拉選單 (多個裝置時顯示)
        config_layout.addWidget(QLabel("Host BT MAC:"))
        self.bt_mac_combo = QComboBox()
        self.bt_mac_combo.setMinimumWidth(200)
        self.bt_mac_combo.currentIndexChanged.connect(self.on_bt_mac_selected)
        self.bt_mac_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #3498db;
                border-radius: 3px;
                background-color: white;
            }
            QComboBox:disabled {
                background-color: #ecf0f1;
            }
        """)
        config_layout.addWidget(self.bt_mac_combo)
        
        # BT MAC 文字框 (單一裝置時顯示)
        self.bt_mac_label = QLineEdit()
        self.bt_mac_label.setMinimumWidth(200)
        self.bt_mac_label.setReadOnly(True)
        self.bt_mac_label.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #3498db;
                border-radius: 3px;
                background-color: #ecf0f1;
            }
        """)
        self.bt_mac_label.setVisible(False)  # 初始隱藏
        config_layout.addWidget(self.bt_mac_label)
        
        main_layout.addWidget(config_group)
        
        # 檢測 BT MAC
        QTimer.singleShot(500, self.detect_bt_mac)
        
        # 控制按鈕區
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Test")
        self.start_btn.clicked.connect(self.start_test)
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        button_layout.addWidget(self.start_btn)
        
        self.terminate_btn = QPushButton("Terminate Test")
        self.terminate_btn.clicked.connect(self.terminate_test)
        self.terminate_btn.setEnabled(False)
        self.terminate_btn.setMinimumHeight(50)
        self.terminate_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        button_layout.addWidget(self.terminate_btn)
        
        main_layout.addLayout(button_layout)
        
        # Log顯示區
        log_group = QGroupBox("Test Execution Log")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Courier New", 9))
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
            }
        """)
        log_layout.addWidget(self.log_display)
        
        main_layout.addWidget(log_group)
        
        # 更新日期計時器
        self.date_timer = QTimer()
        self.date_timer.timeout.connect(self.update_date)
        self.date_timer.start(60000)  # 每分鐘更新
        
        # 測試時間計時器
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.update_test_time)
        self.test_timer.setInterval(1000)  # 每秒更新
        
    def refresh_ports(self):
        """刷新可用串口列表"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        
        # 只顯示 ttyUSB* 和 ttyACM*
        for port in ports:
            if 'ttyUSB' in port.device or 'ttyACM' in port.device:
                self.port_combo.addItem(f"{port.device} - {port.description}")
        
        if self.port_combo.count() == 0:
            self.port_combo.addItem("No valid ports found")
        
        # 同時刷新 BT MAC 狀態
        self.detect_bt_mac()
            
    def detect_bt_mac(self):
        """偵測本機藍牙 MAC 位址"""
        try:
            import subprocess
            result = subprocess.run(['hciconfig', '-a'], capture_output=True, text=True, timeout=2)
            output = result.stdout
            
            # 解析 hciconfig 輸出，支援多個 BT 裝置
            lines = output.split('\n')
            bt_devices = []  # 儲存 (interface, mac, is_up) 的列表
            
            i = 0
            while i < len(lines):
                line = lines[i]
                if 'hci' in line and ':' in line:
                    # 提取介面名稱
                    hci_interface = line.split(':')[0].strip()
                    bt_mac = ""
                    bt_up = False
                    
                    # 在接下來的幾行找 BD Address 和 UP 狀態
                    for j in range(i, min(i+15, len(lines))):
                        # 檢查 BD Address
                        if 'BD Address:' in lines[j]:
                            parts = lines[j].split('BD Address:')
                            if len(parts) > 1:
                                bt_mac = parts[1].strip().split()[0]
                        # 檢查 UP 狀態
                        if 'UP' in lines[j] and 'RUNNING' in lines[j]:
                            bt_up = True
                    
                    if bt_mac:
                        bt_devices.append((hci_interface, bt_mac, bt_up))
                i += 1
            
            # 更新 UI 顯示
            self.bt_mac_combo.clear()
            
            if bt_devices:
                # 根據裝置數量決定顯示方式
                if len(bt_devices) == 1:
                    # 只有一個裝置：使用文字框顯示
                    self.bt_mac_combo.setVisible(False)
                    self.bt_mac_label.setVisible(True)
                    
                    interface, mac, is_up = bt_devices[0]
                    # 如果是 DOWN，嘗試啟動
                    if not is_up:
                        try:
                            subprocess.run(['hciconfig', interface, 'up'], 
                                         capture_output=True, text=True, timeout=2)
                            # 再次檢查狀態
                            check_result = subprocess.run(['hciconfig', interface], 
                                                         capture_output=True, text=True, timeout=2)
                            is_up = 'UP' in check_result.stdout and 'RUNNING' in check_result.stdout
                        except:
                            pass
                    
                    status = "UP" if is_up else "DOWN"
                    display_text = f"{interface}: {mac} ({status})"
                    self.bt_mac_label.setText(display_text)
                    self.host_bt_mac = mac
                else:
                    # 多個裝置：使用下拉選單
                    self.bt_mac_combo.setVisible(True)
                    self.bt_mac_label.setVisible(False)
                    
                    for interface, mac, is_up in bt_devices:
                        # 如果是 DOWN，嘗試啟動
                        if not is_up:
                            try:
                                subprocess.run(['hciconfig', interface, 'up'], 
                                             capture_output=True, text=True, timeout=2)
                                # 再次檢查狀態
                                check_result = subprocess.run(['hciconfig', interface], 
                                                             capture_output=True, text=True, timeout=2)
                                is_up = 'UP' in check_result.stdout and 'RUNNING' in check_result.stdout
                            except:
                                pass
                        
                        # 添加到下拉選單
                        status = "UP" if is_up else "DOWN"
                        color_code = "🟦" if is_up else "🔴"
                        display_text = f"{interface}: {mac} ({status})"
                        self.bt_mac_combo.addItem(display_text, mac)  # 將 MAC 儲存為 user data
                    
                    # 設置第一個為預設選擇並更新 host_bt_mac
                    if self.bt_mac_combo.count() > 0:
                        self.bt_mac_combo.setCurrentIndex(0)
                        self.host_bt_mac = self.bt_mac_combo.itemData(0)
                        if not self.host_bt_mac:
                            self.host_bt_mac = ""
            else:
                # 沒有找到裝置
                self.bt_mac_combo.setVisible(True)
                self.bt_mac_label.setVisible(False)
                self.bt_mac_combo.addItem("No BT device found", "")
                self.host_bt_mac = ""
                
        except Exception as e:
            self.bt_mac_combo.setVisible(True)
            self.bt_mac_label.setVisible(False)
            self.bt_mac_combo.clear()
            self.bt_mac_combo.addItem(f"Error: {str(e)}", "")
            self.host_bt_mac = ""
    
    def on_bt_mac_selected(self, index):
        """當選擇不同的 BT MAC 時更新"""
        if index >= 0:
            # 從 combo box 的 user data 中獲取 MAC 地址
            self.host_bt_mac = self.bt_mac_combo.itemData(index)
            if not self.host_bt_mac:
                self.host_bt_mac = ""
    
    def update_test_status_color(self, label, status):
        """更新測試狀態顏色 (WiFi/BT 個別狀態)"""
        color_map = {
            "IDLE": "#95a5a6",      # 灰色 - 未測試
            "Testing": "#f39c12",   # 橙色 - 測試中
            "PASS": "#27ae60",      # 綠色 - 通過
            "FAIL": "#e74c3c",      # 紅色 - 失敗
            "SKIP": "#95a5a6"       # 灰色 - 跳過
        }
        
        color = color_map.get(status, "#95a5a6")
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        
        # 設置顯示文字
        if status == "IDLE":
            label.setText("---")
        else:
            label.setText(status)
    
    def update_date(self):
        """更新日期顯示"""
        self.date_label.setText(datetime.now().strftime("%Y-%m-%d"))
    
    def update_test_time(self):
        """更新測試時間顯示"""
        self.test_elapsed_seconds += 1
        minutes = self.test_elapsed_seconds // 60
        seconds = self.test_elapsed_seconds % 60
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
    
    def select_bt_priority(self, priority):
        """選擇 BT Test Priority"""
        if priority == "WiFi First":
            self.bt_wifi_first_btn.setChecked(True)
            self.bt_first_btn.setChecked(False)
            self.bt_disable_btn.setChecked(False)
            # 重新啟用 WiFi Band Priority 按鈕
            self.band_5g_btn.setEnabled(True)
            self.band_24g_btn.setEnabled(True)
        elif priority == "BT First":
            self.bt_wifi_first_btn.setChecked(False)
            self.bt_first_btn.setChecked(True)
            self.bt_disable_btn.setChecked(False)
            # 當選擇 BT First 時，自動切換到 5G 優先並禁用 WiFi Band Priority 按鈕
            self.band_5g_btn.setChecked(True)
            self.band_24g_btn.setChecked(False)
            self.band_5g_btn.setEnabled(False)
            self.band_24g_btn.setEnabled(False)
        else:  # Disable
            self.bt_wifi_first_btn.setChecked(False)
            self.bt_first_btn.setChecked(False)
            self.bt_disable_btn.setChecked(True)
            # 重新啟用 WiFi Band Priority 按鈕
            self.band_5g_btn.setEnabled(True)
            self.band_24g_btn.setEnabled(True)
    
    def select_test_level(self, level):
        """選擇 Test Level"""
        if level == "l0":
            self.level_l0_btn.setChecked(True)
            self.level_l1_btn.setChecked(False)
            self.level_l2_btn.setChecked(False)
            self.level_l3_btn.setChecked(False)
        elif level == "l1":
            self.level_l0_btn.setChecked(False)
            self.level_l1_btn.setChecked(True)
            self.level_l2_btn.setChecked(False)
            self.level_l3_btn.setChecked(False)
        elif level == "l2":
            self.level_l0_btn.setChecked(False)
            self.level_l1_btn.setChecked(False)
            self.level_l2_btn.setChecked(True)
            self.level_l3_btn.setChecked(False)
        else:  # l3
            self.level_l0_btn.setChecked(False)
            self.level_l1_btn.setChecked(False)
            self.level_l2_btn.setChecked(False)
            self.level_l3_btn.setChecked(True)
    
    def select_band(self, band):
        """選擇 WiFi Band"""
        if band == "5G":
            self.band_5g_btn.setChecked(True)
            self.band_24g_btn.setChecked(False)
        else:  # 2.4G
            self.band_5g_btn.setChecked(False)
            self.band_24g_btn.setChecked(True)
    
    def clear_sn_mac(self):
        """清除 SN,MAC 欄位並重新啟用輸入"""
        self.sn_mac_input.clear()
        self.sn_mac_input.setPlaceholderText("Enter SN,MAC (e.g., 217522140692,001F7B1E2A54)")
        
        # 重置 WiFi 和 BT 狀態顯示
        self.update_test_status_color(self.wifi_status_label, "IDLE")
        self.update_test_status_color(self.bt_status_label, "IDLE")
    
    def on_sn_mac_changed(self, text):
        """當 SN,MAC 輸入改變時檢查是否符合格式並自動啟動測試"""
        # 如果正在測試中，不處理
        if not self.start_btn.isEnabled():
            return
        
        text = text.strip()
        
        # 檢查格式: SN,MAC 或只有 SN
        if ',' in text:
            parts = text.split(',')
            if len(parts) >= 2:
                sn = parts[0].strip()
                mac = parts[1].strip()
                
                # SN 至少 8 位，MAC 至少 12 位
                if len(sn) >= 8 and len(mac) >= 12:
                    # 符合條件，自動啟動測試
                    QTimer.singleShot(100, self.start_test)
        else:
            # 只有 SN，至少 12 位
            if len(text) >= 12:
                # 符合條件，自動啟動測試
                QTimer.singleShot(100, self.start_test)
    
    def check_port_connection(self):
        """檢查 UART Port 連接狀態"""
        port_text = self.port_combo.currentText()
        
        if not port_text or port_text == "No valid ports found":
            self.update_status_color("Stop")
            return
        
        # 獲取端口名稱
        port = port_text.split(' - ')[0]
        
        # 顯示檢查中
        self.update_status_color("Checking")
        
        # 嘗試連接並檢查 prompt
        try:
            test_conn = serial.Serial(
                port=port,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5
            )
            
            # 發送 Enter 鍵
            test_conn.write(b'\n')
            time.sleep(0.3)
            
            # 讀取回應
            buffer = ""
            timeout = 2
            start_time = time.time()
            prompt_found = False
            
            while time.time() - start_time < timeout:
                if test_conn.in_waiting > 0:
                    data = test_conn.read(test_conn.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    if "_qc:~#" in buffer or "root@" in buffer or "#" in buffer or "$" in buffer:
                        prompt_found = True
                        break
                time.sleep(0.1)
            
            test_conn.close()
            
            if prompt_found:
                self.update_status_color("Ready")
            else:
                self.update_status_color("Device Not Connected")
                
        except serial.SerialException as e:
            self.update_status_color("Device Not Connected")
        except Exception as e:
            self.update_status_color("Device Not Connected")
    
    def update_status_color(self, status):
        """更新狀態顏色"""
        color_map = {
            "Ready": "#3498db",                # 藍色
            "Testing": "#f39c12",              # 橙色
            "PASS": "#3498db",                 # 藍色
            "FAIL": "#e74c3c",                 # 紅色
            "Terminated": "#95a5a6",           # 灰色
            "Stop": "#7f8c8d",                 # 深灰色
            "Device Not Connected": "#e74c3c", # 紅色
            "Checking": "#f39c12"              # 橙色
        }
        
        color = color_map.get(status, "#7f8c8d")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        self.status_label.setText(status)
    
    def start_test(self):
        """開始測試"""
        # 驗證輸入
        if self.port_combo.currentText() == "No valid ports found":
            self.log_display.append("ERROR: No valid UART port selected!")
            return
        
        # 解析 SN,MAC 輸入
        sn_mac_text = self.sn_mac_input.text().strip()
        if sn_mac_text and ',' in sn_mac_text:
            parts = sn_mac_text.split(',')
            sn = parts[0].strip()
            # 使用第一個 MAC（parts[1]），忽略第二個 MAC（parts[2] 如果存在）
            mac = parts[1].strip() if len(parts) > 1 else "dummy"
        elif sn_mac_text:
            sn = sn_mac_text
            mac = "dummy"
        else:
            sn = "dummy"
            mac = "dummy"
        
        # 獲取串口名稱
        port_text = self.port_combo.currentText()
        port = port_text.split(' - ')[0]
        
        # 保存測試開始時間和端口資訊
        self.test_start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.test_port = port
        
        # 清空Log
        self.log_display.clear()
        self.log_display.append("=" * 60)
        self.log_display.append("WiFi Stress Test Started")
        self.log_display.append(f"Date: {self.test_start_time}")
        self.log_display.append(f"Port: {port}")
        self.log_display.append(f"SN: {sn}")
        self.log_display.append(f"MAC: {mac}")
        self.log_display.append("=" * 60)
        
        # 禁用開始按鈕,啟用終止按鈕
        self.start_btn.setEnabled(False)
        self.terminate_btn.setEnabled(True)
        
        # 保存 SN 和 MAC 供後續使用
        self.current_sn = sn
        self.current_mac = mac
        
        # 檢查 BT 測試優先順序
        bt_first = self.bt_first_btn.isChecked()
        bt_disabled = self.bt_disable_btn.isChecked()
        
        # 檢查 Test Level
        if self.level_l0_btn.isChecked():
            test_level = "l0"
        elif self.level_l1_btn.isChecked():
            test_level = "l1"
        elif self.level_l3_btn.isChecked():
            test_level = "l3"
        else:
            test_level = "l2"  # 預設
        
        # 根據選擇的 band 和 test level 生成測試命令
        # 注意：當 BT First 時，WiFi 測試固定為 5G 優先
        if bt_first:
            test_command = f"bash wifi_test.sh -d {test_level}"  # 固定使用 5G 優先
            band_info = "5G (BT First mode)"
        elif self.band_5g_btn.isChecked():
            test_command = f"bash wifi_test.sh -d {test_level}"
            band_info = "5G"
        else:  # 2.4G
            test_command = f"bash wifi_test.sh -d {test_level} -c bgn"
            band_info = "2.4G"
        
        self.log_display.append(f"Band: {band_info}")
        self.log_display.append(f"Test Level: {test_level.upper()}")
        self.log_display.append(f"Command: {test_command}")
        self.log_display.append("=" * 60)
        
        # 重置並啟動測試計時器
        self.test_elapsed_seconds = 0
        self.time_label.setText("0 sec")
        self.test_timer.start()
        
        # 根據測試優先順序更新狀態
        if bt_disabled:
            self.log_display.append("Test Priority: WiFi Only (BT Disabled)")
            self.update_test_status_color(self.wifi_status_label, "Testing")
            self.update_test_status_color(self.bt_status_label, "IDLE")
            # 不傳遞 BT MAC，跳過 BT 測試
            bt_mac_to_use = ""
        elif bt_first:
            self.log_display.append("Test Priority: BT First (WiFi will test 5G first)")
            self.update_test_status_color(self.bt_status_label, "Testing")
            self.update_test_status_color(self.wifi_status_label, "IDLE")
            bt_mac_to_use = self.host_bt_mac
        else:
            self.log_display.append("Test Priority: WiFi First")
            self.update_test_status_color(self.wifi_status_label, "Testing")
            self.update_test_status_color(self.bt_status_label, "IDLE")
            bt_mac_to_use = self.host_bt_mac
        
        self.log_display.append("=" * 60)
        
        # 啟動串口工作線程
        self.serial_worker = SerialWorker(port, test_command=test_command, bt_mac=bt_mac_to_use, bt_first=bt_first)
        self.serial_worker.log_received.connect(self.append_log)
        self.serial_worker.status_changed.connect(self.on_status_changed)
        self.serial_worker.wifi_completed.connect(self.on_wifi_completed)
        self.serial_worker.bt_started.connect(self.on_bt_started)
        self.serial_worker.bt_completed.connect(self.on_bt_completed)
        self.serial_worker.wifi_started.connect(self.on_wifi_started)
        self.serial_worker.test_completed.connect(self.on_test_completed)
        self.serial_worker.start()
    
    def terminate_test(self):
        """終止測試"""
        if self.serial_worker:
            self.log_display.append("\n" + "=" * 60)
            self.log_display.append("TERMINATING TEST...")
            self.log_display.append("=" * 60)
            self.serial_worker.terminate_test()
            self.terminate_btn.setEnabled(False)
    
    def append_log(self, text):
        """添加Log"""
        self.log_display.append(text)
        # 自動滾動到底部
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
    
    def on_wifi_completed(self, wifi_result):
        """WiFi 測試完成處理"""
        self.update_test_status_color(self.wifi_status_label, wifi_result)
    
    def on_bt_started(self):
        """BT 測試開始處理"""
        if not self.bt_first_btn.isChecked():
            # WiFi 優先模式下，BT 測試開始時更新狀態
            self.update_test_status_color(self.bt_status_label, "Testing")
        # BT 優先模式下，狀態已在 start_test 中設置
    
    def on_bt_completed(self, bt_result):
        """BT 測試完成處理"""
        self.update_test_status_color(self.bt_status_label, bt_result)
    
    def on_wifi_started(self):
        """WiFi 測試開始處理 (BT First 模式下)"""
        self.update_test_status_color(self.wifi_status_label, "Testing")
    
    def on_status_changed(self, status):
        """狀態改變處理"""
        self.update_status_color(status)
    
    def on_test_completed(self, wifi_result, bt_result, full_log, bt_mac):
        """測試完成處理"""
        # 停止測試計時器
        self.test_timer.stop()
        
        # 更新 BT 狀態
        if bt_result != "SKIP":
            self.update_test_status_color(self.bt_status_label, bt_result)
        else:
            self.update_test_status_color(self.bt_status_label, "IDLE")
        
        # 計算最終結果
        if wifi_result == "NOT_CONNECTED":
            final_result = "NOT_CONNECTED"
        elif bt_result == "SKIP":
            final_result = wifi_result
        else:
            final_result = "PASS" if wifi_result == "PASS" and bt_result == "PASS" else "FAIL"
        
        # 只有在設備連接成功的情況下才保存 Log
        if final_result != "NOT_CONNECTED":
            self.save_log(wifi_result, bt_result, full_log, bt_mac)
        
        # 恢復按鈕狀態
        self.start_btn.setEnabled(True)
        self.terminate_btn.setEnabled(False)
        
        # 顯示完成消息
        if final_result == "NOT_CONNECTED":
            self.log_display.append("\n" + "=" * 60)
            self.log_display.append("TEST FAILED - DEVICE NOT CONNECTED")
            self.log_display.append("Please check:")
            self.log_display.append("1. UART cable connection")
            self.log_display.append("2. Device is powered on")
            self.log_display.append("3. Correct COM port selected")
            self.log_display.append("=" * 60)
        else:
            self.log_display.append("\n" + "=" * 60)
            self.log_display.append("ALL TESTS COMPLETED")
            self.log_display.append(f"WiFi Result: {wifi_result}")
            if bt_result != "SKIP":
                self.log_display.append(f"BT Result: {bt_result}")
            self.log_display.append(f"Final Result: {final_result}")
            self.log_display.append("=" * 60)
    
    def save_log(self, wifi_result, bt_result, log_content, bt_mac):
        """保存Log文件"""
        # 創建wifilogs目錄 (包含日期)
        date_folder = datetime.now().strftime("%Y%m%d")
        log_dir = f"wifi_stress_log_{date_folder}"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 計算最終結果
        if bt_result == "SKIP":
            final_result = wifi_result
        else:
            final_result = "PASS" if wifi_result == "PASS" and bt_result == "PASS" else "FAIL"
        
        # 生成文件名: 日期_SN_MAC_Result.txt
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 處理 SN 和 MAC，只保留字母數字字元
        sn_clean = ''.join(c for c in self.current_sn if c.isalnum())
        mac_clean = ''.join(c for c in self.current_mac if c.isalnum())
        filename = f"{date_str}_{sn_clean}_{mac_clean}_{final_result}.txt"
        filepath = os.path.join(log_dir, filename)
        
        # 寫入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # 寫入測試標頭資訊
                f.write("=" * 60 + "\n")
                f.write("WiFi & Bluetooth Stress Test\n")
                f.write(f"Date: {self.test_start_time}\n")
                f.write(f"Port: {self.test_port}\n")
                f.write(f"SN: {self.current_sn}\n")
                f.write(f"WiFi MAC: {self.current_mac}\n")
                if bt_mac:
                    f.write(f"BT MAC: {bt_mac}\n")
                f.write("=" * 60 + "\n\n")
                # 寫入測試執行 log
                f.write(log_content)
                # 寫入測試結果
                f.write("\n" + "=" * 60 + "\n")
                f.write("Test Results Summary\n")
                f.write("=" * 60 + "\n")
                f.write(f"WiFi Test Result: {wifi_result}\n")
                if bt_result != "SKIP":
                    f.write(f"BT Test Result: {bt_result}\n")
                f.write(f"Final Result: {final_result}\n")
                f.write("=" * 60 + "\n")
            
            self.log_display.append(f"\nLog saved: {filepath}")
        except Exception as e:
            self.log_display.append(f"\nERROR saving log: {str(e)}")


def main():
    app = QApplication(sys.argv)
    
    # 設置應用樣式
    app.setStyle('Fusion')
    
    window = WiFiTestGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
