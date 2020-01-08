#!/usr/bin/env python3
import re
import time
import syslog
import misc
import RPi.GPIO as GPIO  # pylint: disable=import-error
from pathlib import Path


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(13, GPIO.OUT, initial=GPIO.LOW)
pin13 = GPIO.PWM(13, 75)
p1 = re.compile(r't=(\d+)\n$')


# t1: sensor_temp, t2: cpu_temp
def read_temp(cache={}):
    w1_slave = cache.get('w1_slave')
    if not w1_slave:
        try:
            w1_slave = next(Path('/sys/bus/w1/devices/').glob('28*/w1_slave'))
        except Exception:
            w1_slave = 'not exist'
            syslog.syslog('The sensor will take effect after reboot.')
        cache['w1_slave'] = w1_slave

    if w1_slave == 'not exist':
        t1 = 42
    else:
        with open(w1_slave) as f:
            t1 = int(p1.search(f.read()).groups()[0]) / 1000.0

    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        t2 = int(f.read().strip()) / 1000.0

    return max(t1, t2)


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
        pin13.ChangeDutyCycle(dc)


def running():
    pin13.start(100)

    while True:
        change_dc(get_dc())
        time.sleep(0.1)
