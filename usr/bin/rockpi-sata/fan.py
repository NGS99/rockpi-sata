#!/usr/bin/env python3
import re
import time
import misc
import syslog
import pigpio  # pylint: disable=import-error
from pathlib import Path

pattern = re.compile(r't=(\d+)\n$')


class MockPigpio:
    @classmethod
    def pi(cls):
        try:
            host = misc.check_output("netstat -l | grep -o '\S*:8888' | tr -d ':8888'")
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


# t1: sensor_temp, t2: cpu_temp
def read_temp(cache={}):
    w1_slave = cache.get('w1_slave')
    if not w1_slave:
        try:
            w1_slave = next(Path('/sys/bus/w1/devices/').glob('28*/w1_slave'))
        except Exception:
            w1_slave = 'not exist'
        cache['w1_slave'] = w1_slave

    if w1_slave == 'not exist':
        t1 = 42
    else:
        with open(w1_slave) as f:
            t1 = int(pattern.search(f.read()).groups()[0]) / 1000.0

    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        t2 = int(f.read().strip()) / 1000.0

    return max(t1, t2)


def turn_off():
    misc.conf['run'].value = 0
    gpio.hardware_PWM(12, 0, 0)
    gpio.hardware_PWM(13, 0, 0)


def get_dc(cache={}):
    if not(misc.conf['run'].value):
        return 0

    if time.time() - cache.get('time', 0) > 60:
        cache['time'] = time.time()
        cache['dc'] = misc.fan_temp2dc(read_temp())

    return cache['dc']


def change_dc(dc, cache={}):
    if dc != cache.get('dc'):
        cache['dc'] = dc
        gpio.hardware_PWM(12, 25000, dc * 10000)
        gpio.hardware_PWM(13, 25000, dc * 10000)


def running():
    while True:
        change_dc(get_dc())
        time.sleep(0.1)
