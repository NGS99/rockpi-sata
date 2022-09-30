#!/usr/bin/env python3
"""
    Manage the information about the Quad SATA HAT hardware,
    and provide information as requested by the other parts
    of the SATA HAT service.
"""
from distutils.version import LooseVersion
import re
import os
import sys
import time
#import json
import syslog
import subprocess
import RPi.GPIO as GPIO
import multiprocessing as mp
from collections import defaultdict
from configparser import ConfigParser
from collections import defaultdict, OrderedDict

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)

cmds = {
    'blk': "lsblk | awk '{print $1}'",
    'up': "echo Up: $(uptime -p | sed 's/ years,/y/g;s/ year,/y/g;s/ months,/m/g;s/ month,/m/g;s/ weeks,/w/g;s/ week,/w/g;s/ days,/d/g;s/ day,/d/g;s/ hours,/h/g;s/ hour,/h/g;s/ minutes/m/g;s/ minute/m/g' | cut -d ' ' -f2-)",
    'temp': "cat /sys/class/thermal/thermal_zone0/temp",
    'ip': "hostname -I | awk '{printf \"IP %s\", $1}'",
    'cpu': "uptime | tr , . | awk '{printf \"CPU Load: %.2f%%\", $(NF-2)}'",
    'mem': "free -m | awk 'NR==2{printf \"Mem: %s/%s MB\", $3,$2}'",
    'disk': "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%d GB %s\", $3,$2,$5}'"
}

""" Fan percent correspondence to temperature levels. """
lv2dc = OrderedDict({'lv3': 100, 'lv2': 75, 'lv1': 50, 'lv0': 25})

# we hold raw data for MB count and second of sample time
raw_interface_io = defaultdict(dict)
raw_disk_io = defaultdict(dict)

# we hold the calculated transfer rates in MB/s
interface_io_rate = defaultdict(dict)
disk_io_rate = defaultdict(dict)

# we hold the drive sector size since linux reports in sectors transferred
disk_sector_sizes = defaultdict(dict)

manager = mp.Manager()
last_fan_poll_time = manager.list()
last_fan_poll_time += [0.0]

fan_poll_delay = manager.list()
fan_poll_delay += [10.0]

"""
    Set a value on a GPIO pin, forcing the pin to being
    an Output Pin. 
    
    If the pin cannot be written, print the exception to
    the log and continue.

    pin37(bcm26) sata0, pin22(bcm25) sata1
"""
def set_mode(pin, mode):
    try:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, mode)
    except Exception as ex:
        syslog.syslog(ex)


def disk_turn_on():
    #blk1 = get_blk()
    set_mode(26, GPIO.HIGH)
    time.sleep(0.5)
    set_mode(25, GPIO.HIGH)
#    wait_blk(10)
    #blk2 = get_blk()
    #conf['disk'] = sorted(list(set(blk2) - set(blk1)))


def disk_turn_off():
    set_mode(26, GPIO.LOW)
    time.sleep(0.5)
    set_mode(25, GPIO.LOW)


"""
    Call the Linux shell for this user with the supplied
    command string and return the command output string 
    with leading and trailing white space removed.
"""
def check_output(cmd):
    return subprocess.check_output(cmd, shell=True).decode().strip()


"""
    Call the Linux shell for this user with the supplied
    command string and ignore any possible command outut.
"""
def check_call(cmd):
    return subprocess.check_call(cmd, shell=True)


"""
    Call the Linux shell for this user with the specified
    command from the cmd table and return the whitespace trimmed
    result.
"""
def get_info(s):
    return check_output(cmds[s])


"""
    Read the Configuration file and build a dictionary of
    the values specified in it, providing defaults if a
    configuration file does not exist or has missing
    keys/values.
"""
def read_conf():
    global fan_poll_delay
    conf = defaultdict(dict)

    try:
        cfg = ConfigParser()
        cfg.read('/etc/rockpi-sata.conf')
        # fan common settings
        conf['fan']['lv0'] = cfg.getfloat('fan', 'lv0', fallback=35)
        conf['fan']['lv1'] = cfg.getfloat('fan', 'lv1', fallback=40)
        conf['fan']['lv2'] = cfg.getfloat('fan', 'lv2', fallback=45)
        conf['fan']['lv3'] = cfg.getfloat('fan', 'lv3', fallback=50)
        # fan for CPU - must be after common settings
        conf['fan']['lv0c'] = cfg.getfloat('fan', 'lv0', fallback=conf['fan']['lv0'])
        conf['fan']['lv1c'] = cfg.getfloat('fan', 'lv1', fallback=conf['fan']['lv1'])
        conf['fan']['lv2c'] = cfg.getfloat('fan', 'lv2', fallback=conf['fan']['lv2'])
        conf['fan']['lv3c'] = cfg.getfloat('fan', 'lv3', fallback=conf['fan']['lv3'])
        # fan for Disks - must be after common settings
        conf['fan']['lv0f'] = cfg.getfloat('fan', 'lv0', fallback=conf['fan']['lv0'])
        conf['fan']['lv1f'] = cfg.getfloat('fan', 'lv1', fallback=conf['fan']['lv1'])
        conf['fan']['lv2f'] = cfg.getfloat('fan', 'lv2', fallback=conf['fan']['lv2'])
        conf['fan']['lv3f'] = cfg.getfloat('fan', 'lv3', fallback=conf['fan']['lv3'])
        # fan modes
        conf['fan']['linear'] = cfg.getboolean('fan', 'linear', fallback=False)
        conf['fan']['temp_disks'] = cfg.getboolean('fan', 'temp_disks', fallback=False)
        # key
        conf['key']['click'] = cfg.get('key', 'click', fallback='slider')
        conf['key']['twice'] = cfg.get('key', 'twice', fallback='switch')
        conf['key']['press'] = cfg.get('key', 'press', fallback='none')
        # time
        conf['time']['twice'] = cfg.getfloat('time', 'twice', fallback=0.7)
        conf['time']['press'] = cfg.getfloat('time', 'press', fallback=1.8)
        # slider
        conf['slider']['auto'] = cfg.getboolean('slider', 'auto', fallback=True)
        conf['slider']['time'] = cfg.getfloat('slider', 'time', fallback=10.0)
        refresh_string = cfg.get('slider', 'refresh', fallback='0.0')
        conf['slider']['refresh'] = 0.0 if not len(refresh_string) else float(refresh_string)
        # oled
        conf['oled']['rotate'] = cfg.getboolean('oled', 'rotate', fallback=False)
        conf['oled']['f-temp'] = cfg.getboolean('oled', 'f-temp', fallback=False)
        # disk
        words = cfg.get('disk', 'space_usage_mnt_points', fallback='').split('|')
        conf['disk']['space_usage_mnt_points'] = [x.strip() for x in words]
        words = cfg.get('disk', 'io_usage_mnt_points', fallback='').split('|')
        conf['disk']['io_usage_mnt_points'] = [x.strip() for x in words]
        conf['disk']['disks_temp'] = cfg.getboolean('disk', 'disks_temp', fallback=False)
        if conf['disk']['disks_temp']:
            fan_poll_delay[0] = conf['slider']['time'] * 16     # allow for a lot of panels
        conf['disk']['disable_drives_on_exit'] = cfg.getboolean('disk', 'disable_drives_on_exit', fallback=False)
        # network
        words = cfg.get('network', 'interfaces', fallback='').split('|')
        conf['network']['interfaces'] = [x.strip() for x in words]
    except Exception as config_exception:
        syslog.syslog ("Config error:", repr(config_exception))
        # fan
        conf['fan']['lv0'] = 35
        conf['fan']['lv0c'] = 35
        conf['fan']['lv0f'] = 35

        conf['fan']['lv1'] = 40
        conf['fan']['lv1c'] = 40
        conf['fan']['lv1f'] = 40

        conf['fan']['lv2'] = 45
        conf['fan']['lv2c'] = 45
        conf['fan']['lv2f'] = 45

        conf['fan']['lv3'] = 50
        conf['fan']['lv3c'] = 50
        conf['fan']['lv3f'] = 50

        conf['fan']['linear'] = False
        conf['fan']['temp_disks'] = False
        # key
        conf['key']['click'] = 'slider'
        conf['key']['twice'] = 'switch'
        conf['key']['press'] = 'none'
        # time
        conf['time']['twice'] = 0.7  # second
        conf['time']['press'] = 1.8
        # slider
        conf['slider']['auto'] = True
        conf['slider']['time'] = 10.0  # second
        conf['slider']['refresh'] = 0.0
        # oled
        conf['oled']['rotate'] = False
        conf['oled']['f-temp'] = False
        # disk
        conf['disk']['space_usage_mnt_points'] = []
        conf['disk']['io_usage_mnt_points'] = []
        conf['disk']['disks_temp'] = False
        conf['disk']['disable_drives_on_exit'] = False
        # network
        conf['network']['interfaces'] = []

    return conf


"""
    Read the timed/pattern of input from a top-board pushbutton
    as a GPIO input, according to the supplied pattern.
    If a pattern is matched, return the pattern key.
"""
def read_key(pattern, size):
    s = ''
    while True:
        s = s[-size:] + str(GPIO.input(17))
        for t, p in pattern.items():
            if p.match(s):
                return t
        time.sleep(0.1)

"""
    Process any user input on the top-board button,
    queuing the pattern key when a pattern is detected.
"""
def watch_key(q=None):
    size = int(conf['time']['press'] * 10)
    wait = int(conf['time']['twice'] * 10)
    pattern = {
        'click': re.compile(r'1+0+1{%d,}' % wait),
        'twice': re.compile(r'1+0+1+0+1{3,}'),
        'press': re.compile(r'1+0{%d,}' % size),
    }

    while True:
        q.put(read_key(pattern, size))


"""
    Return the list of interfaces we should monitor for I/O.
"""
def get_interface_list():
    if len(conf['network']['interfaces']) == 1 and conf['network']['interfaces'][0] == '':
        return []

    if len(conf['network']['interfaces']) == 1 and conf['network']['interfaces'][0] == 'auto':
        interfaces = []
        cmd = "ip -o link show | awk '{print $2,$3}'"
        list = check_output(cmd).split('\n')
        for x in list:
            name_status = x.split(': ')
            if "UP" in name_status[1]:
                interfaces.append(name_status[0])

        interfaces.sort()

    else:
        interfaces = conf['network']['interfaces']

    return interfaces


"""
    Remove all parition number digits from the supplied disk name, 
    which must have "sd" in it.
"""
def delete_disk_partition_number(disk):
    while "sd" in disk and disk[-1].isdigit():
        disk = disk[:-1]
    return disk


"""
    Return a list of conf file specified disk types limited to only 
    mounted drives, sorted by drive paritition name.
"""
def get_disk_list(type):
    if len(conf['disk'][type]) == 1 and conf['disk'][type][0] == '':
        return []

    disks = []
    for x in conf['disk'][type]:
        cmd = "df -Bg | awk '$6==\"{}\" {{printf \"%s\", $1}}'".format(x)
        output = check_output(cmd).split('/')[-1]
        if output != '':
            disks.append(output)

    disks.sort()
    return disks


"""
    Return a list of all the sd* drives and their smartctl temperatures,
    sorted by drive name. Drives do not need to be mounted.
"""
def get_disk_temp_info():
    global last_fan_poll_time

    disk_temp_average = 0.0
    disks = sorted(check_output("lsblk -d | egrep ^sd | awk '{print $1}'").split("\n"))
    disks_temp = {}
    for disk in disks:
        if disk:
            cmd = "smartctl -A /dev/" + disk + " | egrep ^194 | awk '{print $10}'"
            cmd_output = check_output(cmd)
            try:
                disk_temp = float(cmd_output)
                if is_temp_farenheit():
                    disk_temp = disk_temp * 1.8 + 32
                    disk_temp_formatted = "{:.0f}°F".format(disk_temp)
                else:
                    disk_temp_formatted = "{:.0f}°C".format(disk_temp)
                disk_temp_average += disk_temp
                disks_temp[disk] = disk_temp_formatted
            except:
                disks_temp[disk] = '----'   # cannot read a temperature
        else:
            disks_temp[''] = ''     # no sd drives on the system
    disk_temp_average /= len(disks_temp)
    conf['disk_temp_average'].value = disk_temp_average
    last_fan_poll_time[0] = time.time()
    return list(zip(*disks_temp.items()))


""" Return true if temperatures are stated in Farenheit. """
def is_temp_farenheit():
    return conf['oled']['f-temp']

""" Return true if we should disable drive controllers when the service exits. """
def is_disable_drives_on_exit():
    return conf['disk']['disable_drives_on_exit']

def get_disk_io_read_info(disk):
    cmd = "R1=$(cat /sys/block/" + disk + "/stat | awk '{print $3}'); sleep 1; R2=$(cat /sys/block/" + disk + "/stat | awk '{print $3}'); echo | awk -v r1=$R1 -v r2=$R2 '{printf \"R: %.5f MB/s\", (r2 - r1) / 2 / 1024}';"
    output = check_output(cmd)
    return output

"""
    Return the time the last disk temperature poll was done.
"""
def get_last_disk_temp_poll():
    global last_fan_poll_time
    
    return last_fan_poll_time[0]


"""
    Return a list of disk partition's %used for all /dev mounted systems.
"""
def get_disk_used_info(cache={}):
    if not cache.get('time') or time.time() - cache['time'] > 30:
        info = {}
        cmd = "df -h | awk '$NF==\"/\"{printf \"%s\", $5}'"
        info['root'] = check_output(cmd)
        conf['disk']['disks'] = get_disk_list('space_usage_mnt_points')
        for x in conf['disk']['disks']:
            delete_disk_partition_number(x)
            cmd = "df -Bg | awk '$1==\"/dev/{}\" {{printf \"%s\", $5}}'".format(x)
            info[x] = check_output(cmd)
        cache['info'] = list(zip(*info.items()))
        cache['time'] = time.time()

    return cache['info']


"""
    Fill in disk_secotr_sizes for the drive we will poll.
    Needed to accurately calculate byte rates from sector rates.
"""
def get_sector_size(disk):
    cmd = "cat /sys/block/" + disk + "/queue/hw_sector_size"
    disk_sector_sizes[disk] = int(check_output(cmd))

""" 
    Get the raw network interface transfer count sample and the time of sampling. 
    Raw network transfer values are in bytes.
"""
def get_interface_io(interface):
    cmd = "cat /sys/class/net/" + interface + "/statistics/rx_bytes"
    rx = int(check_output(cmd))
    cmd = "cat /sys/class/net/" + interface + "/statistics/tx_bytes"
    tx = int(check_output(cmd))
    return {"rx": rx, "tx": tx, "time": time.time()}

""" 
    Get the raw disk transfer count sample and the time of sampling. 
    Raw disk transfer values are in sectors for that drive.
"""
def get_disk_io(disk):
    cmd = "cat  /sys/block/" + disk + "/stat"
    output = check_output(cmd)
    columns = output.split()
    return {"rx": int(columns[2]), "tx": int(columns[6]), "time": time.time()}

""" 
    Sample the specified network interfaces and disks and calculate the rates against
    the last raw samples for these devices.
    
    Rates are returned in fractional MB/Second.
"""
def get_interface_io_rates():
    interfaces = get_interface_list()
    for interface in interfaces:
        get_interface_io_rate(interface)

""" Update the dict holding I/O rates for all interfaces. """
def get_interface_io_rate(interface):
        raw = get_interface_io(interface)
        # network raw data is in bytes transferred since the last boot
        if interface in raw_interface_io:
            duration = raw["time"] - raw_interface_io[interface]["time"]
            interface_io_rate[interface]["rx"] = ((raw["rx"] - raw_interface_io[interface]["rx"]) / duration) / 1024 / 1024
            interface_io_rate[interface]["tx"] = ((raw["tx"] - raw_interface_io[interface]["tx"]) / duration) / 1024 / 1024
        else:
            interface_io_rate[interface]["rx"] = 0
            interface_io_rate[interface]["tx"] = 0
        raw_interface_io[interface] = raw
        return interface_io_rate[interface]

""" Get updated rates for all the disks. """
def get_disk_io_rates():
    # disk raw data is in per-device sectors transferred since the last boot
    disks = get_disk_list('io_usage_mnt_points')
    for disk in disks:
        get_disk_io_rate(disk)

""" Get the I/O rate for a specific disk. """
def get_disk_io_rate(disk):
        disk = delete_disk_partition_number(disk)
        if not disk in disk_sector_sizes:        # initial sampling if we have no sector byte size for a disk
            get_sector_size(disk)

        raw = get_disk_io(disk)
        if disk in raw_disk_io:
            duration = raw["time"] - raw_disk_io[disk]["time"]
            disk_io_rate[disk]["rx"] = ((raw["rx"] - raw_disk_io[disk]["rx"]) / duration) / (1024 / disk_sector_sizes[disk]) / 1024
            disk_io_rate[disk]["tx"] = ((raw["tx"] - raw_disk_io[disk]["tx"]) / duration) / (1024 / disk_sector_sizes[disk]) / 1024
        else:
            disk_io_rate[disk]["rx"] = 0
            disk_io_rate[disk]["tx"] = 0
        raw_disk_io[disk] = raw
        return disk_io_rate[disk]


""" Return the IO rates for the specified interface. """
def get_interface_rates(interface):
    return interface_io_rate[interface]

""" return the IO rates for the specified disk. """
def get_disk_rates(disk):
    return disk_io_rate[disk]

def get_slider_sleep_duration():
    return conf['slider']['time']

"""
    Convert the temperature to a percentage for a fan PWM.
    We could have any number of different fans, they are
    represented by a key of '', 'c' or 'f'.
    
    We will convert either as a quanta, as set by the temperature
    for each of the levels, or as a linear percent, dependant upon
    the temperature within the range and the percent top and bottom
    for the bucket the temperature is found in.
"""
def fan_temp2dc(temp, key):
    top_lvl_percent = 0
    top_lvl_temp = 0
    for lvl, percent in lv2dc.items():
        lvl_temp = conf['fan'][lvl+key]
        if temp > lvl_temp: # too hot, found bucket
            if top_lvl_percent == 0:
                return 100.0
            if conf['fan']['linear']:
                percent_range = top_lvl_percent - percent
                temp_delta = top_lvl_temp - lvl_temp
                percent_slope = percent_range / temp_delta
                new_percent = (temp - lvl_temp) * percent_slope + percent
                return new_percent
            else:
                return top_lvl_percent
         
        top_lvl_percent = percent
        top_lvl_temp = lvl_temp
 
    return top_lvl_percent


"""
    Toggle the configuration dictionary setting for
    whether the fan should run or not.
"""

def fan_switch():
    conf['run'].value = not(conf['run'].value)

"""
    Return True if the fan is supposed to be running.
"""
def fan_running():
    return conf['run'].value

def get_func(key):
    return conf['key'].get(key, 'none')

"""
    Return true if we want to include disk temperatures
    with the fan.
"""
def is_fan_cpu_and_disk():
    return conf['fan']['temp_disks']

"""
    The poll delay is large if we normally poll, or
    reasonable if we are not polling.
"""
def get_fan_poll_delay():
    global fan_poll_delay
    
    return fan_poll_delay[0]


"""
    Return the last calculated average diskk temperatures.
"""
def get_disk_temp_average():
    return conf['disk_temp_average'].value

"""
    Return the refresh period configured.
"""
def get_refresh_period():
    return conf['slider']['refresh']

def open_w1_i2c():
    with open('/boot/config.txt', 'r') as f:
        content = f.read()

    if 'dtoverlay=w1-gpio' not in content:
        with open('/boot/config.txt', 'w') as f:
            f.write(content.strip() + '\ndtoverlay=w1-gpio')

    if 'dtparam=i2c1=on' not in content:
        with open('/boot/config.txt', 'w') as f:
            f.write(content.strip() + '\ndtparam=i2c1=on')

    os.system('/sbin/modprobe w1-gpio')
    os.system('/sbin/modprobe w1-therm')
    os.system('/sbin/modprobe i2c-dev')


"""
    Initialze internal variables maintained in the conf dictionary and
    read the system's conf file's conf dictionay settings.
"""
conf = {'disk': [], 'run': mp.Value('i', 1), 'disk_temp_average': mp.Value('f', 0.0),}
conf.update(read_conf())


if __name__ == '__main__':
    if sys.argv[-1] == 'open_w1_i2c':
        open_w1_i2c()
