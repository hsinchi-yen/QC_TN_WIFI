Here is the guide for build the QC for having wifi stress test feature

1. Target file path in QC : /home/qc
2. update the iperf revision from 2.0.4 to 2.1.5
	sudo cp iperf /usr/bin/iperf 
	iperf version check :
	================================================
	root@pico_qc:~# iperf -v
	iperf version 2.1.n (12 November 2021) pthreads
	root@pico_qc:~# 
	================================================

3. add the test scripts :
	3.1 wifi_test.sh 
	    sudo cp wifi_test.sh /home/qc/
	3.2 bt_ping.sh
	    sudo cp bt_ping.sh /home/qc/

4. wifi configuration files :
	path :
	ls -1  wifi_grp/*
	wifi_grp/solo_wifi24g.conf
	wifi_grp/solo_wifi5g.conf
	wifi_grp/sta_a_wifi24g.conf
	wifi_grp/sta_a_wifi5g.conf
	wifi_grp/sta_b_wifi24g.conf
	wifi_grp/sta_b_wifi5g.conf
	
	commands :
	cp -r wifi_grp /home/qc/"wifi_grp"
	
====command seq===========================================
lance@lance-virtual-machine:/mnt/hgfs/DriveVM/PD_Test/PD_ATE$ sudo cp *.sh /media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/
lance@lance-virtual-machine:/mnt/hgfs/DriveVM/PD_Test/PD_ATE$ sync
lance@lance-virtual-machine:/mnt/hgfs/DriveVM/PD_Test/PD_ATE$ sudo cp -r wifi_grp/ /media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/
lance@lance-virtual-machine:/mnt/hgfs/DriveVM/PD_Test/PD_ATE$ sudo cp -r -v wifi_grp/ /media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/
'wifi_grp/solo_wifi24g.conf' -> '/media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/wifi_grp/solo_wifi24g.conf'
'wifi_grp/solo_wifi5g.conf' -> '/media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/wifi_grp/solo_wifi5g.conf'
'wifi_grp/sta_a_wifi24g.conf' -> '/media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/wifi_grp/sta_a_wifi24g.conf'
'wifi_grp/sta_a_wifi5g.conf' -> '/media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/wifi_grp/sta_a_wifi5g.conf'
'wifi_grp/sta_b_wifi24g.conf' -> '/media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/wifi_grp/sta_b_wifi24g.conf'
'wifi_grp/sta_b_wifi5g.conf' -> '/media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/home/qc/wifi_grp/sta_b_wifi5g.conf'
lance@lance-virtual-machine:/mnt/hgfs/DriveVM/PD_Test/PD_ATE$ sudo cp -v iperf /media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/usr/bin/
'iperf' -> '/media/lance/b4960b55-a5c5-47a5-873b-0d47c3b42d3c/usr/bin/iperf
====command seq end===========================================
	
Related Settings for wifi settings
Folder Name : wifi_grp

solo :
SSID Name and config name

2.4G SSID : PD-RF-QC-2-4
CH: 1, 6 , 11 (not overlay with other station)
pwd : 12345678
config file : /wifi_grp/wifi24g.conf

5G SSID : PD-RF-QC-5
CH: 36/40/44/48
pwd : 12345678
config file : /wifi_grp/wifi5g.conf

-------------------------------------------


1st group:

SSID Name and config name

2.4G SSID : PD-RF-QC-2-4-STA-A
CH: 1, 6 , 11 (not overlay with other station)
pwd : 12345678
config file : /wifi_grp/sta_a_wifi24g.conf

5G SSID : PD-RF-QC-5-STA-A
CH: 36/40/44/4
pwd : 12345678
config file : /wifi_grp/sta_a_wifi5g.conf 


----------------------------------
2nd group:
2.4G SSID : PD-RF-QC-2-4-STA-B
CH: 1, 6 , 11 (not overlay with other station)
pwd : 12345678
config file : /wifi_grp/sta_b_wifi5g.conf 


5G SSID : PD-RF-QC-5-STA-B
CH: 36/40/44/4
pwd : 12345678
config file : /wifi_grp/sta_b_wifi5g.conf 




