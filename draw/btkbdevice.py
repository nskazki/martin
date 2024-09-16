import os
import dbus
import socket
import traceback
from time import sleep
from dbus.mainloop.glib import DBusGMainLoop

class BTKbDevice:
    UUID = "00001124-0000-1000-8000-00805f9b34fb"
    P_CTRL = 17
    P_INTR = 19
    SDP_RECORD_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "btkbdevice.xml")
    PROFILE_DBUS_PATH = "/bluez/yaptb/btkb_profile"

    def __init__(self, hci=0):
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.target = None
        self.ccontrol = None
        self.cinterrupt = None
        self.register_hid_profile()

    def register_hid_profile(self):
        record = open(BTKbDevice.SDP_RECORD_PATH, "r").read()
        options = { "Role": "server", "AutoConnect": True, "ServiceRecord": record, "RequireAuthorization": True, "RequireAuthentication": True }
        manager = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        manager.RegisterProfile(BTKbDevice.PROFILE_DBUS_PATH, BTKbDevice.UUID, options)

    @property
    def devices(self):
        proxy_object = self.bus.get_object("org.bluez", "/")
        managed_objects = dbus.Interface(proxy_object, "org.freedesktop.DBus.ObjectManager").GetManagedObjects()
        connected_devices = []
        for path in managed_objects:
            device = managed_objects[path].get("org.bluez.Device1", {})
            addr = device.get("Address")
            alias = device.get("Alias")
            paired = device.get("Paired", False)
            connected = device.get("Connected", False)
            if addr and alias and (paired or connected):
                connected_devices.append({ "addr": addr, "alias": alias, "paired": paired, "connected": connected })
        return connected_devices

    def connect(self, target):
        try:
            self.target = target
            self.ccontrol = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
            self.ccontrol.connect((self.target, self.P_CTRL))
            self.cinterrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
            self.cinterrupt.connect((self.target, self.P_INTR))
            if not self.is_connected:
                raise Exception("It says it's connected but it's not!")

            return True
        except Exception as e:
            print(f"Couldn't connect to {self.target} due to {e}")
            traceback.print_exc()

    @property
    def is_connected(self):
        for device in self.devices:
            if device["addr"] == self.target and device["connected"]:
                return True

    def send(self, msg):
        try:
            if self.cinterrupt:
                self.cinterrupt.send(bytes(bytearray(msg)))
        except Exception as e:
            print(f"Couldn't send to {self.target} due to {e}")
            traceback.print_exc()

    def test(self):
        self.send([0xA1, 1, 0, 0, 30, 0, 0, 0, 0, 0])
        sleep(0.1)
        self.send([0xA1, 1, 0, 0,  0, 0, 0, 0, 0, 0])
