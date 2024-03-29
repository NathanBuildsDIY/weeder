This is the installation files for a solar weeding robot.
Learn more at the youtube link here: 

To set up your raspberry pi zero 2 w 
1. If you log in via ssh and it hangs, improve ssh response times with this command and then reboot: echo "IPQoS cs0 cs0" | sudo tee -a /etc/ssh/sshd_config  
2. install git on your raspberry pi: sudo apt-get -y install git
3. clone this git repository to your pi home directory: git clone https://github.com/NathanBuildsDIY/weeder
4. Run initial setup: nohup sh weeder/initial-setup.sh &
  Note - you can watch the output with: tail -f nohup.out
6. Connect to the new wifi hostpot called weeder.  Visit http://weeder.local/run to control your weeding robot.
  view logs of runs at http://weeder.local/
  You can still ssh to the weeder (while connected to the weeder wifi) via ssh or putty
