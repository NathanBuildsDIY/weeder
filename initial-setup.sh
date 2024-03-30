echo "get up to date packages with apt-get"
sudo apt-get update
sudo apt-get -y upgrade

echo "install new packages - various stuff to run weeder script"
sudo apt-get -y install pip
sudo apt-get -y install python3-pyqt5 #only on 64 0 2, camera failed
sudo apt-get -y install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev wget
sudo apt-get -y install libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev
sudo apt-get -y remove vim-tiny
sudo apt-get -y install vim

echo "use pip to install packages into python"
pip3 install opencv-python
pip3 install --upgrade tflite-support==0.4.2
pip3 install --upgrade tflite-runtime==2.11.0
pip3 install imutils

echo "get pigpio daemon running so we have better servo control"
sudo apt-get -y install pigpio python-pigpio python3-pigpio
sudo apt-get -y install pigpiod
pip3 install pigpio
sudo systemctl enable pigpiod #makes it run at startup (after reboot - sudo shutdown -r now. Check with pigs t)

echo "set up dnsmask to do dns resolution on our wifi hotspot"
sudo apt-get -y install dnsmasq
sudo apt-get -y install dnsutils
#NOTE: I thought dnsmask woudl work like this:
#sudo vi /etc/dnsmasq.conf  Add domain-needed; bogus-priv; expand-hosts; domain=connect.local; address=/#/10.42.0.1; 
#but once wifi hotspot is actually set up we instead config in this file below
echo 'address=/.local/10.42.0.1' | sudo tee -a /etc/NetworkManager/dnsmasq-shared.d/hosts.conf

echo "create entry in crontab to always run weeder app on startup"
line="@reboot python3 -m flask --app ~/weeder/WeedKiller_v6.py run --host=0.0.0.0 >> ~/weeder/log/log.out"
(crontab -u $(whoami) -l; echo "$line" ) | crontab -u $(whoami) -

echo "Install flask and associated forms packages"
pip3 install -U Flask 
pip3 install WTForms
pip3 install Flask-WTF
pip3 install flask_autoindex
pip3 install psutil

echo "set up iptables and rules"
line="@reboot /usr/bin/sh /home/$(whoami)/weeder/iptables.rules"
sudo sh -c "(crontab -l; echo $line) | sort - | uniq | crontab -"

echo "setup local wifi hotspot"
sudo systemctl stop dhcpcd
sudo systemctl disable dhcpcd
sudo systemctl enable NetworkManager 
sudo service NetworkManager start
sleep 20
sudo nmcli device wifi hotspot ssid weeder password LetsWeed ifname wlan0
UUID=$(nmcli connection | grep Hotspot | tr -s ' ' | cut -d ' ' -f 2)
sudo nmcli connection modify $UUID connection.autoconnect yes connection.autoconnect-priority 100

echo "restarting for changes to take effect. Still must run wifi setup"
sudo shutdown -r now
