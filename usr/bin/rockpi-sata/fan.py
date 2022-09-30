#!/usr/bin/env python3
"""
Control the CPU fan and SATA HAT top fan according to the temperature of the 
Raspberry  Pi, SATA HAT and optionally the disks.

Fan PWN frequency is 25KHz, according to Noctua fan white paper
   : https://noctua.at/pub/media/wysiwyg/Noctua_PWM_specifications_white_paper.pdf

"""
import re
import time
import misc
import syslog
import pigpio  # pylint: disable=import-error
from pathlib import Path
import multiprocessing as mp

pattern = re.compile(r't=(\d+)\n$')
tb_fan_pwm = 13     # GPIO 13, pin 33
cpu_fan_pwm = 12    # GPIO_12, pin 32

manager = mp.Manager()
cache = manager.dict()
class MockPigpio:
    @classmethod
    def pi(cls):
        try:
            #  Host is localhost. If we netstat to IPV6 we may fail
            # may require ExecStart in /lib/systemd/system/pigpiod.service to be:
            # ExecStart=/usr/bin/pigpiod -n 127.0.0.1
#            host = misc.check_output("netstat -l | grep -o '\S*:8888' | tr -d ':8888'")
            host = "127.0.0.1"
            gpio = pigpio.pi(host=host)
        except Exception:
            gpio = cls()
        return gpio

    def __init__(self):
        syslog.syslog('PWM of pigpio is not available. Use on/off to control the fan.')
        syslog.syslog('If you use pre-release kernel, please go back to stable release.')

    def hardware_PWM(self, pin, _, dc):
        misc.set_mode(pin, bool(dc))


gpio = MockPigpio.pi()


"""
    Read the CPU temperature and include disks if we want
    to use their temperature as well. This means that we
    have to be capturing disk temperatures (auto display).

    t1: sensor_temp, t2: cpu_temp
"""
def read_temp():
    w1_slave = cache.get('w1_slave')
    if not w1_slave:
        try:
            w1_slave = next(Path('/sys/bus/w1/devices/').glob('28*/w1_slave'))
        except Exception as ex:
            w1_slave = 'not exist'
        cache['w1_slave'] = w1_slave

    if w1_slave == 'not exist':
        t_sensor = 0 # 42 we can't get hat sensor through w1
    else:
        with open(w1_slave) as f:
            t_sensor = int(pattern.search(f.read()).groups()[0]) / 1000.0

    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        t_cpu = int(f.read().strip()) / 1000.0

    t_sys = max(t_cpu, t_sensor)
    if misc.is_temp_farenheit():
        t_sys = t_sys * 1.8 + 32
    
    if misc.is_fan_cpu_and_disk():
        if (misc.get_last_disk_temp_poll() + misc.get_fan_poll_delay()) < time.time():    # poll disk temps
            misc.get_disk_temp_info()
        t_disk = misc.get_disk_temp_average()
    else:
        t_disk = t_sys  #default disk to cpu temp
    return (t_sys, t_disk)

def turn_off():
    misc.conf['run'].value = 0
    gpio.hardware_PWM(cpu_fan_pwm, 0, 0)
    gpio.hardware_PWM(tb_fan_pwm, 0, 0)

"""
    Return the percentage settings for the cpu and disk fans.
"""
def get_fan_speeds():
    if not(misc.conf['run'].value):
        return 'off'
    return (cache['cpu'], cache['disk'])


"""
    Main loop updating the fan's speed according to the
    desired temperature thresholds.
"""
def running():
    while True:
        cpu_temp, disk_temp = read_temp()
        cpu_dc = misc.fan_temp2dc(cpu_temp, 'c')
        fan_dc = misc.fan_temp2dc(disk_temp, 'f')
        cache['cpu'] = cpu_dc
        cache['disk'] = fan_dc
        # print ('cache[dc] set:{:5.2f}'.format(cache['cpu']), 
        #        'cpu_temp: {:5.2f}'.format (cpu_temp), 
        #        'cpu_dc:{:5.2f}'.format (cpu_dc), 
        #        'disk_temp:{:5.2f}'.format (disk_temp), 
        #        'fan_dc:{:5.2f}'.format (fan_dc))
        gpio.hardware_PWM(cpu_fan_pwm, 25000, int (cpu_dc * 10000))
        gpio.hardware_PWM(tb_fan_pwm, 25000, int (fan_dc * 10000))
        time.sleep(1)
