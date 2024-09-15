
"""
Stenogotchi and Bluetooth HID keyboard emulator D-BUS Service

Based on: https://gist.github.com/ukBaz/a47e71e7b87fbc851b27cde7d1c0fcf0#file-readme-md
Which in turn takes the original idea from: http://yetanotherpointlesstechblog.blogspot.com/2016/04/emulating-bluetooth-keyboard-with.html

Tested on:
    Python 3.7-3.9
    BlueZ 5.5
"""
import os
import sys
from types import MethodDescriptorType
import dbus
import dbus.service
import socket

from time import sleep
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

class BluezErrorCanceled(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Canceled"

class Agent(dbus.service.Object):
    """
    BT Pairing agent
    API: https://git.kernel.org/pub/scm/bluetooth/bluez.git/plain/doc/agent-api.txt
    examples: https://github.com/elsampsa/btdemo/blob/master/bt_studio.py
    """

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        print(f"[plover_link] Successfully paired device: {device} using Secure Simple Pairing (SSP)")
        return

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        print(f"[plover_link] Accepted RequestAuthorization from {device}")
        return

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Cancel(self):
        print("[plover_link] Cancel request received from BT client")
        raise(BluezErrorCanceled)

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Release(self):
        self.logging("[plover_link] Connection released due to BT client request")


class HumanInterfaceDeviceProfile(dbus.service.Object):
    """
    BlueZ D-Bus Profile for HID
    """
    fd = -1

    @dbus.service.method('org.bluez.Profile1', in_signature='', out_signature='')
    def Release(self):
        print('[plover_link] PloverLink: Release')

    @dbus.service.method('org.bluez.Profile1', in_signature='oha{sv}', out_signature='')
    def NewConnection(self, path, fd, properties):
        self.fd = fd.take()
        print('[plover_link] NewConnection({}, {})'.format(path, self.fd))
        for key in properties.keys():
            if key == 'Version' or key == 'Features':
                print('[plover_link] {} = 0x{:04x}'.format(key,
                    properties[key]))
            else:
                print('[plover_link] {} = {}'.format(key, properties[key]))

    @dbus.service.method('org.bluez.Profile1', in_signature='o', out_signature='')
    def RequestDisconnection(self, path):
        print('[plover_link] RequestDisconnection {}'.format(path))

        if self.fd > 0:
            os.close(self.fd)
            self.fd = -1

class BTKbDevice:
    """
    Create a bluetooth device to emulate a HID keyboard
    """
    P_CTRL = 17 # Service control port - must match port configured in SDP record
    P_INTR = 19 # Service interrupt port - must match port configured in SDP record

    # BlueZ dbus
    PROFILE_DBUS_PATH = '/bluez/yaptb/btkb_profile'
    AGENT_DBUS_PATH = '/org/bluez'
    ADAPTER_IFACE = 'org.bluez.Adapter1'
    DEVICE_INTERFACE = 'org.bluez.Device1'
    DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'
    DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'

    SDP_RECORD_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'plover_link_btserver_sdp_record.xml')

    # UUID for HID service (1124)
    # https://www.bluetooth.com/specifications/assigned-numbers/service-discovery
    UUID = '00001124-0000-1000-8000-00805f9b34fb'

    def __init__(self, hci=0):
        print('[plover_link] Setting up BT device')

        self.scontrol = None
        self.ccontrol = None  # Socket object for control
        self.sinterrupt = None
        self.cinterrupt = None  # Socket object for interrupt
        self.dev_path = '/org/bluez/hci{}'.format(hci)
        self.bus = dbus.SystemBus()

        self.adapter_methods = dbus.Interface(self.bus.get_object('org.bluez', self.dev_path), self.ADAPTER_IFACE)
        self.adapter_property = dbus.Interface(self.bus.get_object('org.bluez', self.dev_path), self.DBUS_PROP_IFACE)

        self.bus.add_signal_receiver(self.interfaces_added, dbus_interface=self.DBUS_OM_IFACE, signal_name='InterfacesAdded')
        self.bus.add_signal_receiver(self._properties_changed, dbus_interface=self.DBUS_PROP_IFACE, signal_name='PropertiesChanged', arg0=self.DEVICE_INTERFACE, path_keyword='path')

        self.register_hid_profile()

        self.bthost_mac = None
        self.bthost_name = ""

    def interfaces_added(self, path, device_info):
        print(f'[plover_link] Intervase Added {path} {device_info}')

    def _properties_changed(self, interface, changed, invalidated, path):
        print(interface)
        print(changed)
        print(invalidated)
        print(path)
        if 'Connected' in changed:
            if not changed['Connected']:
                self.on_disconnect()

    def on_disconnect(self):
        print('[plover_link] The client has been disconnected')
        self.bthost_mac = None
        self.bthost_name = ""

    @property
    def address(self):
        """ Return the adapter MAC address. """
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'Address')

    def register_hid_profile(self):
        """
        Setup and register HID Profile
        """

        print('[plover_link] Configuring Bluez Profile')
        service_record = self.read_sdp_service_record()

        opts = {
            'Role': 'server',
            'RequireAuthentication': True,
            'RequireAuthorization': True,
            'AutoConnect': True,
            'ServiceRecord': service_record,
        }

        manager = dbus.Interface(self.bus.get_object('org.bluez', '/org/bluez'), 'org.bluez.ProfileManager1')
        HumanInterfaceDeviceProfile(self.bus, BTKbDevice.PROFILE_DBUS_PATH)
        manager.RegisterProfile(BTKbDevice.PROFILE_DBUS_PATH, BTKbDevice.UUID, opts)
        print('[plover_link] Profile registered ')

    @staticmethod
    def read_sdp_service_record():
        fh = open(BTKbDevice.SDP_RECORD_PATH, 'r')
        return fh.read()

    def create_ssockets(self):
        """ Create passive listening sockets and close possibly exising ones """
        print("[plover_link] Creating BT listening ssockets")

        if self.scontrol:
            self.scontrol.close()
        if self.sinterrupt:
            self.sinterrupt.close()

        self.scontrol = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def listen(self):
        """
        Listen for connections coming from HID client
        """
        if not self.scontrol or not self.sinterrupt:
             self.create_ssockets()

        # Bind address/port to existing sockets
        self.scontrol.bind((self.address, self.P_CTRL))
        self.sinterrupt.bind((self.address, self.P_INTR))

        # Start listening on the server sockets with limit of 1 connection per socket
        self.scontrol.listen(1)
        self.sinterrupt.listen(1)

        print('[plover_link] Waiting for connections')

        self.ccontrol, cinfo = self.scontrol.accept()
        print('[plover_link] {} connected on the ccontrol socket'.format(cinfo[0]))

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print('[plover_link] {} connected on the cinterrupt channel'.format(cinfo[0]))

        self.bthost_mac = cinfo[0]
        self.bthost_name = self.get_connected_device_name()

    def get_connected_device_name(self):
        """ Returns name (Alias) of connected BT device """

        proxy_object = self.bus.get_object("org.bluez","/")
        manager = dbus.Interface(proxy_object, "org.freedesktop.DBus.ObjectManager")
        managed_objects = manager.GetManagedObjects()
        for path in managed_objects:
            con_state = managed_objects[path].get('org.bluez.Device1', {}).get('Connected', False)
            if con_state:
                addr = managed_objects[path].get('org.bluez.Device1', {}).get('Address')
                alias = managed_objects[path].get('org.bluez.Device1', {}).get('Alias')
                print(f'[plover_link] Device {alias} [{addr}] is connected')

        return alias

    def send(self, msg):
        """
        Send HID message
        :param msg: (bytes) HID packet to send
        """
        self.cinterrupt.send(bytes(bytearray(msg)))

class StenogotchiService(dbus.service.Object):
    """
    Setup of a D-Bus service to receive:
    Status updates and HID messages from Plover plugin.
    HID messages from Stenogotchi evdevkb plugin
    """

    def __init__(self):
        print('[plover_link] Setting up Stenogotchi D-Bus service')
        bus_name = dbus.service.BusName('com.github.stenogotchi', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/com/github/stenogotchi')
        self.device = BTKbDevice()

    def listen(self):
        self.device.listen()

    @dbus.service.method('com.github.stenogotchi', in_signature='aay')   # array of bytearrays
    def send_keys(self, key_list):
        for key in key_list:
            self.device.send(key)

if __name__ == '__main__':
    DBusGMainLoop(set_as_default=True)
    stenogotchiservice = StenogotchiService()
    stenogotchiservice.listen()
    mainloop = GLib.MainLoop()
    mainloop.run()
