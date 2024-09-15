import re
import os
import dbus
import socket
import signal
import dbus.service
from time import sleep
from dbus.mainloop.glib import DBusGMainLoop

class BTKbDevice:
    P_CTRL = 17 # Service control port - must match port configured in SDP record
    P_INTR = 19 # Service interrupt port - must match port configured in SDP record

    # BlueZ dbus
    PROFILE_DBUS_PATH = "/bluez/yaptb/btkb_profile"
    ADAPTER_IFACE = "org.bluez.Adapter1"
    DEVICE_INTERFACE = "org.bluez.Device1"
    DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

    SDP_RECORD_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "plover_link_btserver_sdp_record.xml")

    # UUID for HID service (1124)
    # https://www.bluetooth.com/specifications/assigned-numbers/service-discovery
    UUID = "00001124-0000-1000-8000-00805f9b34fb"

    def __init__(self, hci=0):
        self.bthost_mac = None
        self.bthost_name = ""

        self.scontrol = None
        self.ccontrol = None  # Socket object for control
        self.sinterrupt = None
        self.cinterrupt = None  # Socket object for interrupt

        self.bus = dbus.SystemBus()
        self.bus.add_signal_receiver(self.on_change, dbus_interface=self.DBUS_PROP_IFACE, signal_name="PropertiesChanged", arg0=self.DEVICE_INTERFACE, path_keyword="path")

        self.dev_path = f"/org/bluez/hci{hci}"
        self.adapter_methods = dbus.Interface(self.bus.get_object('org.bluez', self.dev_path), self.ADAPTER_IFACE)
        self.adapter_property = dbus.Interface(self.bus.get_object('org.bluez', self.dev_path), self.DBUS_PROP_IFACE)

        self.register_hid_profile()

    def on_change(self, interface, changed, invalidated, path):
        if 'Connected' in changed:
            address = re.search(r"(\w{2}_){5}\w{2}$", path).group().replace("_", ":")
            if changed['Connected']:
                self.on_connected(address)
            else:
                self.on_disconnect(address)

    def on_connected(self, address):
        print(f"Connected {address}")
        sleep(3)
        self.send([0xA1, 1, 0, 0, 30, 0, 0, 0, 0, 0])
        sleep(0.01)
        self.send([0xA1, 1, 0, 0,  0, 0, 0, 0, 0, 0])
        sleep(0.01)

    def on_disconnect(self, address):
        print(f"Disconnected {address}")
        self.bthost_mac = None
        self.bthost_name = ""

    @property
    def address(self):
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'Address')

    def register_hid_profile(self):
        print("Configuring Bluez Profile")
        service_record = self.read_sdp_service_record()

        opts = {
            "Role": "server",
            "AutoConnect": True,
            "ServiceRecord": service_record,
            "RequireAuthorization": True,
            "RequireAuthentication": True,
        }

        manager = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        manager.RegisterProfile(BTKbDevice.PROFILE_DBUS_PATH, BTKbDevice.UUID, opts)

    @staticmethod
    def read_sdp_service_record():
        fh = open(BTKbDevice.SDP_RECORD_PATH, "r")
        return fh.read()

    def create_ssockets(self):
        print("Creating BT listening ssockets")

        if self.scontrol:
            self.scontrol.close()
        if self.sinterrupt:
            self.sinterrupt.close()

        self.scontrol = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def listen(self):
        if not self.scontrol or not self.sinterrupt:
             self.create_ssockets()

        # Bind address/port to existing sockets
        self.scontrol.bind((self.address, self.P_CTRL))
        self.sinterrupt.bind((self.address, self.P_INTR))

        # Start listening on the server sockets with limit of 1 connection per socket
        self.scontrol.listen(1)
        self.sinterrupt.listen(1)

        print("Waiting for connections")

        self.ccontrol, cinfo = self.scontrol.accept()
        print(f"{cinfo[0]} connected on the ccontrol socket")

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print(f"{cinfo[0]} connected on the cinterrupt channel")

        self.bthost_mac = cinfo[0]
        self.bthost_name = self.get_connected_device_name()

    def get_connected_device_name(self):
        proxy_object = self.bus.get_object("org.bluez", "/")
        manager = dbus.Interface(proxy_object, "org.freedesktop.DBus.ObjectManager")
        managed_objects = manager.GetManagedObjects()
        for path in managed_objects:
            con_state = managed_objects[path].get("org.bluez.Device1", {}).get("Connected", False)
            if con_state:
                addr = managed_objects[path].get("org.bluez.Device1", {}).get("Address")
                alias = managed_objects[path].get("org.bluez.Device1", {}).get("Alias")
                print(f"Device {alias} [{addr}] is connected")
                return alias

    def send(self, msg):
        self.cinterrupt.send(bytes(bytearray(msg)))

if __name__ == '__main__':
    DBusGMainLoop(set_as_default=True)
    device = BTKbDevice()
    device.listen()
    signal.pause()
