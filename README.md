# ROCK Pi SATA

[Quad SATA HAT](<https://wiki.radxa.com/Dual_Quad_SATA_HAT>) for Raspberry Pi 4B+/3B+

![sata-hat](https://setq.me/static/img/quad-sata-hat.png)

Just mirroring this, incase it ever goes down/missing.

Seller:  https://shop.allnetchina.cn/collections/sata-hat/products/quad-sata-hat-case-for-raspberry-pi-4

script "get-rockpi-sata.sh" references raspbi-sata-0.12.deb which has been uploaded as well

Youtube guide: https://www.youtube.com/watch?v=Eix0PCB0byQ

original location of install script:  curl -sL https://rock.sh/get-rockpi-sata | sudo -E bash -

Due to a bug in OMV right now 5/9/2020, when you install OMV on a Pi you lose access to Wireless, and when you get it back, it doesnt see 5ghz networks.  Best to use this script instead:  wget -O - https://raw.githubusercontent.com/OpenMediaVault-Plugin-Developers/installScript/96b465008666461f4220c3da8459f0d9aa0d2dcd/install | sudo bash

OpenMediaVault install script:  wget -O - https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install | sudo bash



Misc. Possible issues and resolutions
https://forum.radxa.com/t/quad-sata-kit-and-openmediavault-5-raspberry-pi-4/3193



Software configuration
Just edit /etc/rockpi-sata.conf, take it effect by below command

sudo systemctl restart rockpi-sata.service
Below is the default /etc/rockpi-sata.conf, which you can modify according to the comments

[fan]
# When the temperature is above lv0 (35'C), the fan at 25% power,
# and lv1 at 50% power, lv2 at 75% power, lv3 at 100% power.
# When the temperature is below lv0, the fan is turned off.
# You can change these values if necessary.
lv0 = 35
lv1 = 40
lv2 = 45
lv3 = 50
 
[key]
# You can customize the function of the key, currently available functions are
# slider: oled display next page
# switch: fan turn on/off switch
# reboot, poweroff
# If you have any good suggestions for key functions, 
# please add an issue on https://rock.sh/rockpi-sata
click = slider
twice = switch
press = none
 
[time]
# twice: maximum time between double clicking (seconds)
# press: long press time (seconds)
twice = 0.7
press = 1.8
 
[slider]
# Whether the oled auto display next page and the time interval (seconds)
auto = true
time = 10
 
[oled]
# Whether rotate the text of oled 180 degrees, whether use Fahrenheit
rotate = false
f-temp = false
