echo "setup local wifi hotspot"
sudo nmcli device wifi hotspot ssid weeder password LetsWeed ifname wlan0
  #note - to disable, sudo nmcli device disconnect wlan0
  #After disabling the network, run the following command to reconnect to another Wi-Fi network: sudo nmcli device up wlan0
#once enabled, we need to make it priority so it always runs on startup
UUID=$(nmcli connection | grep Hotspot | tr -s ' ' | cut -d ' ' -f 2)
#nmcli connection show $UUID
sudo nmcli connection modify $UUID connection.autoconnect yes connection.autoconnect-priority 100

echo "setup complete - check over output, then doing a reboot"
sleep 200
sudo shutdown -r now

