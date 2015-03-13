#!/usr/bin/python

import time
import os
import sys
import json
import optparse
import socket

# see https://pythonhosted.org/watchdog
from watchdog.observers import Observer

from broker import Broker

#   General home IoT data
#

def iot_handler(broker, data):
    topic = "home"
    try:
        jdata = json.loads(data)
        if jdata.get("pir") == "1":
            topic = "home/pir"
    except:
        pass
    broker.send(topic, data)

#   River level monitor
#

def rivers_handler(broker, data):
    # 2015-03-12 20:46:18 tick
    # 2015-03-12 20:46:23 7267 'Kingston Bridge' 4.56

    parts = data.split()
    d = {}
    d["time"] = parts[0].replace("-", "/") + " " + parts[1]

    if parts[2] == "tick":
        d["id"] = "tick"
        topic = "rivers/tick"
    else:
        d["id"] = parts[2]
        name = " ".join(parts[3:-1])
        d["name"] = name[1:-1]
        d["level"] = float(parts[-1])
        topic = "rivers/level"

    broker.send(topic, json.dumps(d))

#   Smart meter : power usage
#

def power_handler(broker, data):
    # 230029 118.6
    hms, power = data.split()
    hms = ":".join([ hms[:2], hms[2:4], hms[4:] ])
    d = {
        "power" : float(power),
        "time" : hms,
    }
    broker.send("home/power", json.dumps(d))

#   Solar Power generation meter
#

def solar_handler(broker, data):
    # 16:53:42 9151773
    hms, power = data.split()
    d = {
        "power" : int(power, 10),
        "time" : hms,
    }
    broker.send("home/solar", json.dumps(d))

#
#   CPU / network monitoring for host

def monitor_handler(broker, data):
    # 07:27:02 0.14 0.14 0.09 772832 930861 35.0 31.0
    # hms load1, load2, load3 rx tx [ temp1 ... ]
    parts = data.split()
    d = {
        "time" : parts[0],
        # CPU load
        "load_0" : parts[1],
        "load_1" : parts[2],
        "load_2" : parts[3],
        # Network
        "rx" : parts[4],
        "tx" : parts[5],
    }
    for i, temp in enumerate(parts[6:]):
        d["temp_%d" % i] = temp 

    host = socket.gethostname()
    d["host"] = host

    broker.send("home/net/" + host, json.dumps(d))

#
#

iot_dir = "/usr/local/data/iot"
rivers_dir = "/usr/local/data/rivers"
power_dir = "/usr/local/data/power"
solar_dir = "/usr/local/data/solar"
monitor_dir = "/usr/local/data/monitor"

handlers = {
    iot_dir : iot_handler,
    rivers_dir : rivers_handler,
    power_dir : power_handler,
    solar_dir : solar_handler,
    monitor_dir : monitor_handler,
}

paths = handlers.keys()

#
#

class Handler:

    def __init__(self, broker, seek):
        self.broker = broker
        self.files = {}
        for path in paths:
            self.files[path] = None
        self.seek = seek

    def on_data(self, tree, data):
        print tree, str(data)
        handler = handlers[tree]
        handler(self.broker, data)

    def handle_file_change(self, path):
        tree = None
        for p in paths:
            if path.startswith(p):
                tree = p
                break

        f = self.files.get(tree)
        if not f is None:
            if f.name != path:
                self.files[tree] = None
                f = None

        newfile = False
        if f is None:
            newfile = True
            f = open(path, "r")
            self.files[tree] = f

        if newfile and self.seek:
            f.seek(0, os.SEEK_END)

        # read all the pending changes
        while True:
            data = f.readline()
            if not data:
                break
            self.on_data(tree, data.strip())

    def dispatch(self, event):
        try:
            if event.event_type == "modified":
                path = event.src_path
                if path.endswith(".log"):
                    self.handle_file_change(path)
        except Exception, ex:
            print "Exception", str(ex)
            sys.exit(0) # TODO : remove me

#
#

if __name__ == "__main__":

    p = optparse.OptionParser()
    p.add_option("-s", "--seek", dest="seek", action="store_true")
    opts, args = p.parse_args()    

    server = "mosquitto"
    print "connect to", server
    broker = Broker("watcher", server=server)
    broker.start()

    event_handler = Handler(broker, seek=opts.seek)

    observer = Observer()
    for path in paths:
        print "monitor", path
        observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        broker.stop()
        observer.stop()

    broker.join()
    observer.join()

# FIN
