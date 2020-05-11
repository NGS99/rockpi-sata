# ROCK Pi SATA

[Quad SATA HAT](<https://wiki.radxa.com/Dual_Quad_SATA_HAT>) for Raspberry Pi 4B+/3B+

![sata-hat](https://setq.me/static/img/quad-sata-hat.png)

Just mirroring this, incase it ever goes down/missing.

Seller:  https://shop.allnetchina.cn/collections/sata-hat/products/quad-sata-hat-case-for-raspberry-pi-4

script "get-rockpi-sata.sh" references raspbi-sata-0.12.deb which has been uploaded as well

Youtube guide: https://www.youtube.com/watch?v=Eix0PCB0byQ

original location of install script:  curl -sL https://rock.sh/get-rockpi-sata | sudo -E bash -



Due to a bug in OMV right now 5/9/2020, when you install OMV on a Pi4 4gb you lose access to Wireless, and when you get it back, it doesnt see 5ghz networks.  Best to use this script instead:  wget -O - https://raw.githubusercontent.com/OpenMediaVault-Plugin-Developers/installScript/96b465008666461f4220c3da8459f0d9aa0d2dcd/install | sudo bash


Wireless will continue to work with the above script, until you reboot.  Then its disabled on boot.  You can use the following commands to get it up and running again
sudo ifconfig wlan0 up
sudo omv-firstaid
then reconfigure wireless

Usually, only two HDDs will show in OMV, even though the Pi sees 4.  If you have more than 2 drives, you will need to do this fix if they do not show in OMV.

First, use lsusb and locate your the names of your hard drives.  In my case they are western digital.  So it shows as ID 1058:0a10 Western Digital.  We are going to call 1058 the idVendor and 0a10 the idProduct.  You will need to replace the 4 digit codes in the line below with what you just wrote down.  You can “fix” this by adding a rule to /lib/udev/rules.d/60-persistent-storage.rules after the entry for “Fall back usb_id for USB devices”:

>KERNEL=="sd*", ATTRS{idVendor}=="152d", ATTRS{idProduct}=="2338", SUBSYSTEMS=="usb", PROGRAM="/root/serial.sh %k", ENV{ID_SERIAL}="USB-%c", ENV{ID_SERIAL_SHORT}="%c"

You will also need to create sudo nano /root/serial.sh containing the following:

#!/bin/bash
/sbin/hdparm -I /dev/$1 | grep 'Serial Number' | awk '{print $3}'

save, then sudo chmod +x /root/serial.sh , then reboot

For some users, the SATA drives will show as USB.  If thats the case, then you cannot use native RAID Management within OMV.  As a result, you can use mdadm to build a software raid.  Personally, I prefer using RSYNC inside OMV and just having it copy all updated files every Monday, Weds, Friday.  This gives me the peace of mind knowing that if I accidently delete something important, I can still access the file on the backup.

Official OpenMediaVault install script:  wget -O - https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install | sudo bash



Misc. Possible issues and resolutions
https://forum.radxa.com/t/quad-sata-kit-and-openmediavault-5-raspberry-pi-4/3193



Software configuration
Just edit /etc/rockpi-sata.conf, take it effect by below command

sudo systemctl restart rockpi-sata.service
Below is the default /etc/rockpi-sata.conf, which you can modify according to the comments

[fan]
#### # When the temperature is above lv0 (35'C), the fan at 25% power,
#### # and lv1 at 50% power, lv2 at 75% power, lv3 at 100% power.
#### # When the temperature is below lv0, the fan is turned off.
#### # You can change these values if necessary.
lv0 = 35
lv1 = 40
lv2 = 45
lv3 = 50
 
[key]
#### # You can customize the function of the key, currently available functions are
#### # slider: oled display next page
#### # switch: fan turn on/off switch
#### # reboot, poweroff
#### # If you have any good suggestions for key functions, 
#### # please add an issue on https://rock.sh/rockpi-sata
click = slider
twice = switch
press = none
 
[time]
#### # twice: maximum time between double clicking (seconds)
#### # press: long press time (seconds)
twice = 0.7
press = 1.8
 
[slider]
#### # Whether the oled auto display next page and the time interval (seconds)
auto = true
time = 10
 
[oled]
#### # Whether rotate the text of oled 180 degrees, whether use Fahrenheit
rotate = false
f-temp = false
