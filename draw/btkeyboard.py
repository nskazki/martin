import os
import dbus
import socket
import traceback
from time import sleep
from dbus.mainloop.glib import DBusGMainLoop

class BtKeyboard:
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
        record = self.read_sdp_record()
        options = { "Role": "server", "AutoConnect": True, "ServiceRecord": record, "RequireAuthorization": True, "RequireAuthentication": True }
        manager = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        manager.RegisterProfile(self.PROFILE_DBUS_PATH, self.UUID, options)

    def read_sdp_record(self):
        with open(self.SDP_RECORD_PATH, "r") as file:
            content = file.read()
        return content

    @property
    def devices(self):
        proxy_object = self.bus.get_object("org.bluez", "/")
        managed_objects = dbus.Interface(proxy_object, "org.freedesktop.DBus.ObjectManager").GetManagedObjects()
        connected_devices = []
        for path in managed_objects:
            device = managed_objects[path].get("org.bluez.Device1", {})
            alias = device.get("Alias")
            address = device.get("Address")
            paired = device.get("Paired", False)
            connected = device.get("Connected", False)
            if address and alias and (paired or connected):
                connected_devices.append({ "address": address, "alias": alias, "paired": paired, "connected": connected })
        return connected_devices

    def connect(self, target):
        try:
            self.disconnect()
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
            print("Going to disconnect!")
            self.disconnect()

    def disconnect(self):
        if self.ccontrol:
            try:
                self.ccontrol.close()
            except Exception as e:
                print(f"Couldn't close ccontrol due to {e}")
            finally:
                self.ccontrol = None

        if self.cinterrupt:
            try:
                self.cinterrupt.close()
            except Exception as e:
                print(f"Couldn't close cinterrupt due to {e}")
            finally:
                self.cinterrupt = None

    @property
    def is_connected(self):
        if not self.ccontrol or not self.cinterrupt:
            return False

        for device in self.devices:
            if device["address"] == self.target and device["connected"]:
                return True

    def send(self, msg):
        try:
            if self.is_connected:
                self.cinterrupt.send(bytes(bytearray(msg)))
            else:
                print(f"Couldn't send to {self.target} due to the lack of connection!")
        except Exception as e:
            print(f"Couldn't send to {self.target} due to {e}")
            print("Going to disconnect!")
            self.disconnect()

    def test(self):
        self.send([0xA1, 1, 0, 0, 30, 0, 0, 0, 0, 0])
        sleep(0.1)
        self.send([0xA1, 1, 0, 0,  0, 0, 0, 0, 0, 0])
