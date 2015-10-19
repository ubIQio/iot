
import struct 

from system.core import log
from system.jeenet import JeeNodeDev, message_info

#
#

# Flash Commands
FLASH_INFO_REQ = 1
FLASH_INFO = 2
FLASH_CLEAR = 3
FLASH_CLEARED = 4
FLASH_WRITE = 5
FLASH_WRITTEN = 6
FLASH_CRC_REQ = 7
FLASH_CRC = 8
FLASH_READ_REQ = 9
FLASH_READ = 10
FLASH_REBOOT = 11

#
#

class FlashInterface:

    def __init__(self, *args, **kwargs):
        self.api = RelayDev.api + self.flash_api

    def cmd_info(self, mid, data):
        info = {
            "mid" : mid,
            "test" : "hello",
        }
        return info

    def flash_to_info(self, data):
        hsize = struct.calcsize(self.fmt_header)
        hdr, payload = data[:hsize], data[hsize:]
        mid, dst, flags = struct.unpack(self.fmt_header, hdr)
        if not (flags & self.flash_flag):
            return None

        cmd, = struct.unpack("<B", payload[:1])
        log("flash_cmd", cmd)

        handlers = {
            FLASH_INFO  :   self.cmd_info,
        }

        def nowt(mid, data):
            return { "mid" : mid }

        fn = handlers.get(cmd, nowt)
        return fn(mid, data)

    def flash_req_info(self):
        log("flashreq_info")
        fields = [ (self.flash_flag, "<B", FLASH_INFO_REQ), ]
        msg_id, raw = self.make_raw(self.ack_flag, fields)
        #log(`raw`)
        self.tx_message(msg_id, raw, "flash_req_info", True)

    flash_api = [ "flash_req_info" ]

#
#

class RelayDev(JeeNodeDev,FlashInterface):

    def __init__(self, *args, **kwargs):
        JeeNodeDev.__init__(self, *args, **kwargs)
        FlashInterface.__init__(self, *args, **kwargs)
        self.is_sleepy = True # not really

    def to_info(self, data):
        rx_fields = [ 
            (1<<1, "temp", "<H"),
            (1<<2, "relay", "<B"), 
            (1<<3, "vcc", "<H"),
            (self.text_flag, "text", "p"),
        ]

        msg_id, flags, info = message_info(data, self.fmt_header, rx_fields)

        if not info.get("temp") is None:
            info["temp"] /= 100.0
        if not info.get("vcc") is None:
            info["vcc"] /= 1000.0

        return info

    def set_relay(self, state):
        assert state in [ 0, 1, ]
        fields = [ (1<<2, "<B", state), ]
        msg_id, raw = self.make_raw(self.ack_flag, fields)
        self.tx_message(msg_id, raw, "set_state", True)

    def get_poll_period(self):
        return 60

    api = JeeNodeDev.api + [ "set_relay" ]

# FIN
