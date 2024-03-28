This is the installation files for a solar weeding robot.
Learn more at the youtube link here: 

To set up your raspberry pi zero 2 w 
1. Improve ssh response times. They can be really slow: echo "IPQoS cs0 cs0" | sudo tee -a /etc/ssh/sshd_config
2. Install iptables persistent - it's interactive.  Answer yes to all questions: sudo apt-get -y install iptables-persistent
3. install git on your raspberry pi: sudo apt-get -y install git
4. clone this git repository to your pi home directory: git clone https://github.com/NathanBuildsDIY/weeder
5. Run initial setup: nohup sh weeder/initial-setup.sh &
  Note - you can watch the output with: tail -f nohup.out
6. Connect to the new wifi hostpot called weeder.  Visit http://weeder.local:5000/run to control your weeding robot.
  view logs of runs at http://weeder.local:5000

Sometimes the network changes fail to complete.  If that happens, log back in and manually execute:
nohup sh weeder/wifi-setup.sh &
