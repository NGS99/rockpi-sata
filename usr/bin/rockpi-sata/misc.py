#!/usr/bin/env python3
import re
import os
import sys
import time
import json
import subprocess
import RPi.GPIO as GPIO
import multiprocessing as mp
from collections import defaultdict
from configparser import ConfigParser

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)

cmds = {
    'blk': "lsblk | awk '{print $1}'",
    #'up': "echo Uptime: `uptime | sed 's/.*up \\([^,]*\\), .*/\\1/'`",
    'up': "echo Up: $(uptime -p | sed 's/ years,/y/g;s/ year,/y/g;s/ months,/m/g;s/ month,/m/g;s/ weeks,/w/g;s/ week,/w/g;s/ days,/d/g;s/ day,/d/g;s/ hours,/h/g;s/ hour,/h/g;s/ minutes/m/g;s/ minute/m/g' | cut -d ' ' -f2-)",
    'temp': "cat /sys/class/thermal/thermal_zone0/temp",
    'ip': "hostname -I | awk '{printf \"IP %s\", $1}'",
    'cpu': "uptime | tr , . | awk '{printf \"CPU Load: %.2f%%\", $(NF-2)}'",
    'men': "free -m | awk 'NR==2{printf \"Mem: %s/%s MB\", $3,$2}'",
    'disk': "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%d GB %s\", $3,$2,$5}'"
}

lv2dc = {'lv3': 100, 'lv2': 75, 'lv1': 50, 'lv0': 25}


# pin37(bcm26) sata0, pin22(bcm25) sata1
def set_mode(pin, mode):
    try:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, mode)
    except Exception as ex:
        print(ex)


def disk_turn_on():
    #blk1 = get_blk()
    set_mode(26, GPIO.HIGH)
    time.sleep(0.5)
    set_mode(25, GPIO.HIGH)
    wait_blk(10)
    #blk2 = get_blk()
    #conf['disk'] = sorted(list(set(blk2) - set(blk1)))


def disk_turn_off():
    set_mode(26, GPIO.LOW)
    time.sleep(0.5)
    set_mode(25, GPIO.LOW)


def check_output(cmd):
    return subprocess.check_output(cmd, shell=True).decode().strip()


def check_call(cmd):
    return subprocess.check_call(cmd, shell=True)


def wait_blk(t1=10):
    t = 0
    while t <= t1:
        try:
            check_call('lsblk /dev/sda > /dev/null 2>&1')
            check_call('lsblk /dev/sdb > /dev/null 2>&1')
            check_call('lsblk /dev/sdc > /dev/null 2>&1')
            check_call('lsblk /dev/sdd > /dev/null 2>&1')
        except Exception:
            time.sleep(0.1)
            t += 0.1
            continue
        else:
            time.sleep(0.5)
            break


def get_blk():
    return check_output(cmds['blk']).strip().split('\n')


def get_info(s):
    return check_output(cmds[s])


def get_cpu_temp():
    t = float(get_info('temp')) / 1000
    if conf['oled']['f-temp']:
        temp = "CPU Temp: {:.0f}°F".format(t * 1.8 + 32)
    else:
        temp = "CPU Temp: {:.1f}°C".format(t)
    return temp


def read_conf():
    conf = defaultdict(dict)

    try:
        cfg = ConfigParser()
        cfg.read('/etc/rockpi-sata.conf')
        # fan
        conf['fan']['lv0'] = cfg.getfloat('fan', 'lv0')
        conf['fan']['lv1'] = cfg.getfloat('fan', 'lv1')
        conf['fan']['lv2'] = cfg.getfloat('fan', 'lv2')
        conf['fan']['lv3'] = cfg.getfloat('fan', 'lv3')
        # key
        conf['key']['click'] = cfg.get('key', 'click')
        conf['key']['twice'] = cfg.get('key', 'twice')
        conf['key']['press'] = cfg.get('key', 'press')
        # time
        conf['time']['twice'] = cfg.getfloat('time', 'twice')
        conf['time']['press'] = cfg.getfloat('time', 'press')
        # other
        conf['slider']['auto'] = cfg.getboolean('slider', 'auto')
        conf['slider']['time'] = cfg.getfloat('slider', 'time')
        conf['oled']['rotate'] = cfg.getboolean('oled', 'rotate')
        conf['oled']['f-temp'] = cfg.getboolean('oled', 'f-temp')
        # disk
        conf['disk']['space_usage_mnt_points'] = cfg.get('disk', 'space_usage_mnt_points').split('|')
        conf['disk']['io_usage_mnt_points'] = cfg.get('disk', 'io_usage_mnt_points').split('|')
        conf['disk']['disks_temp'] = cfg.getboolean('disk', 'disks_temp')
        #conf['disk']['disks'] = get_disk_list()
        # network
        conf['network']['interfaces'] = cfg.get('network', 'interfaces').split('|')
    except Exception:
        # fan
        conf['fan']['lv0'] = 35
        conf['fan']['lv1'] = 40
        conf['fan']['lv2'] = 45
        conf['fan']['lv3'] = 50
        # key
        conf['key']['click'] = 'slider'
        conf['key']['twice'] = 'switch'
        conf['key']['press'] = 'none'
        # time
        conf['time']['twice'] = 0.7  # second
        conf['time']['press'] = 1.8
        # other
        conf['slider']['auto'] = True
        conf['slider']['time'] = 10  # second
        conf['oled']['rotate'] = False
        conf['oled']['f-temp'] = False
        # disk
        conf['disk']['space_usage_mnt_points'] = []
        conf['disk']['io_usage_mnt_points'] = []
        conf['disk']['disks_temp'] = False
        #conf['disk']['disks'] = []
        # network
        conf['network']['interfaces'] = []

    return conf


def read_key(pattern, size):
    s = ''
    while True:
        s = s[-size:] + str(GPIO.input(17))
        for t, p in pattern.items():
            if p.match(s):
                return t
        time.sleep(0.1)


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


def get_interface_list():
    if len(conf['network']['interfaces']) == 1 and conf['network']['interfaces'][0] == '':
        return []

    if len(conf['network']['interfaces']) == 1 and conf['network']['interfaces'][0] == 'auto':
        interfaces = []
        cmd = "ip -o link show | awk '{print $2,$9}'"
        list = check_output(cmd).split('\n')
        for x in list:
            name_status = x.split(': ')
            if "UP" in name_status[1]:
                interfaces.append(name_status[0])

        interfaces.sort()

    else:
        interfaces = conf['network']['interfaces']

    return interfaces


def get_interface_rx_info(interface):
    cmd = "R1=$(cat /sys/class/net/" + interface + "/statistics/rx_bytes); sleep 1; R2=$(cat /sys/class/net/" + interface + "/statistics/rx_bytes); echo | awk -v r1=$R1 -v r2=$R2 '{printf \"rx: %.5f MB/s\", (r2 - r1) / 1024 / 1024}';"
    output = check_output(cmd)
    return output


def get_interface_tx_info(interface):
    cmd = "T1=$(cat /sys/class/net/" + interface + "/statistics/tx_bytes); sleep 1; T2=$(cat /sys/class/net/" + interface + "/statistics/tx_bytes); echo | awk -v t1=$T1 -v t2=$T2 '{printf \"tx: %.5f MB/s\", (t2 - t1) / 1024 / 1024}';"
    output = check_output(cmd)
    return output


def delete_disk_partition_number(disk):
    if "sd" in disk and disk[-1].isdigit():
        disk = disk[:-1]
    return disk


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


def get_disk_temp_info():
    if not conf['disk']['disks_temp']:
        return [(), ()]
    disks = list(check_output("ls /dev/sd* | grep -E \"[0-9]$\" | cut -f3 -d'/' | tr -d '0123456789'").split("\n"))
    disks_temp = {}
    for disk in disks:
        output = check_output(f"sudo smartctl -A /dev/{disk} -j")
        object = json.loads(output)
        disk_temp = object["temperature"]["current"]
        if conf['oled']['f-temp']:
            disk_temp = "{:.0f}°F".format(disk_temp * 1.8 + 32)
        else:
            disk_temp = "{}°C".format(disk_temp)
        disks_temp[disk] = disk_temp
    return list(zip(*disks_temp.items()))


def get_disk_io_read_info(disk):
    cmd = "R1=$(cat /sys/block/" + disk + "/stat | awk '{print $3}'); sleep 1; R2=$(cat /sys/block/" + disk + "/stat | awk '{print $3}'); echo | awk -v r1=$R1 -v r2=$R2 '{printf \"R: %.5f MB/s\", (r2 - r1) / 2 / 1024}';"
    output = check_output(cmd)
    return output


def get_disk_io_write_info(disk):
    cmd = "W1=$(cat /sys/block/" + disk + "/stat | awk '{print $7}'); sleep 1; W2=$(cat /sys/block/" + disk + "/stat | awk '{print $7}'); echo | awk -v w1=$W1 -v w2=$W2 '{printf \"W: %.5f MB/s\", (w2 - w1) / 2 / 1024}';"
    output = check_output(cmd)
    return output


def get_disk_info(cache={}):
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


def slider_next(pages):
    conf['idx'].value += 1
    return pages[conf['idx'].value % len(pages)]


def slider_sleep():
    time.sleep(conf['slider']['time'])


def fan_temp2dc(t):
    for lv, dc in lv2dc.items():
        if t >= conf['fan'][lv]:
            return dc
    return 0


def fan_switch():
    conf['run'].value = not(conf['run'].value)


def get_func(key):
    return conf['key'].get(key, 'none')


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


conf = {'disk': [], 'idx': mp.Value('d', -1), 'run': mp.Value('d', 1)}
conf.update(read_conf())


if __name__ == '__main__':
    if sys.argv[-1] == 'open_w1_i2c':
        open_w1_i2c()
