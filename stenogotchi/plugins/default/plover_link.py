
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
import logging
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

    @dbus.service.method('org.bluez.Agent1',
                    in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        logging.info(f"[plover_link] Successfully paired device: {device} using Secure Simple Pairing (SSP)")
        return

    @dbus.service.method('org.bluez.Agent1',
                         in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        logging.info(f"[plover_link] Accepted RequestAuthorization from {device}")
        return

    @dbus.service.method('org.bluez.Agent1',
                         in_signature='', out_signature='')
    def Cancel(self):
        logging.info("[plover_link] Cancel request received from BT client")
        raise(BluezErrorCanceled)

    @dbus.service.method('org.bluez.Agent1',
                in_signature='', out_signature='')
    def Release(self):
        self.logging("[plover_link] Connection released due to BT client request")
        mainloop.quit()


class HumanInterfaceDeviceProfile(dbus.service.Object):
    """
    BlueZ D-Bus Profile for HID
    """
    fd = -1

    @dbus.service.method('org.bluez.Profile1',
                         in_signature='', out_signature='')
    def Release(self):
            logging.info('[plover_link] PloverLink: Release')
            mainloop.quit()

    @dbus.service.method('org.bluez.Profile1',
                         in_signature='oha{sv}', out_signature='')
    def NewConnection(self, path, fd, properties):
            self.fd = fd.take()
            logging.info('[plover_link] NewConnection({}, {})'.format(path, self.fd))
            for key in properties.keys():
                    if key == 'Version' or key == 'Features':
                            logging.info('[plover_link] {} = 0x{:04x}'.format(key,
                                                           properties[key]))
                    else:
                            logging.info('[plover_link] {} = {}'.format(key, properties[key]))

    @dbus.service.method('org.bluez.Profile1',
                         in_signature='o', out_signature='')
    def RequestDisconnection(self, path):
            logging.info('[plover_link] RequestDisconnection {}'.format(path))

            if self.fd > 0:
                    os.close(self.fd)
                    self.fd = -1


class BTKbDevice:
    """
    Create a bluetooth device to emulate a HID keyboard
    """
    # Service control port - must match port configured in SDP record
    P_CTRL = 17
    # Service interrupt port - must match port configured in SDP record
    P_INTR = 19
    # BlueZ dbus
    PROFILE_DBUS_PATH = '/bluez/yaptb/btkb_profile'
    AGENT_DBUS_PATH = '/org/bluez'
    ADAPTER_IFACE = 'org.bluez.Adapter1'
    DEVICE_INTERFACE = 'org.bluez.Device1'
    DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'
    DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'

    # file path of the sdp record to laod
    install_dir  = os.path.dirname(os.path.realpath(__file__))
    SDP_RECORD_PATH = os.path.join(install_dir,
                                   'plover_link_btserver_sdp_record.xml')
    # UUID for HID service (1124)
    # https://www.bluetooth.com/specifications/assigned-numbers/service-discovery
    UUID = '00001124-0000-1000-8000-00805f9b34fb'

    def __init__(self, hci=0):
        self.bt_autoconnect_list = ['F8:4D:89:63:2C:CE']
        self.bt_last_conn = None
        self.autoconnect_in_progress = False
        self.bt_agent_running = False
        self.scontrol = None
        self.ccontrol = None  # Socket object for control
        self.sinterrupt = None
        self.cinterrupt = None  # Socket object for interrupt
        self.dev_path = '/org/bluez/hci{}'.format(hci)
        logging.info('[plover_link] Setting up BT device')
        self.bus = dbus.SystemBus()

        self.adapter_methods = dbus.Interface(self.bus.get_object('org.bluez',
                                            self.dev_path), self.ADAPTER_IFACE)
        self.adapter_property = dbus.Interface(self.bus.get_object('org.bluez',
                                            self.dev_path), self.DBUS_PROP_IFACE)

        self.bus.add_signal_receiver(self.interfaces_added,
                                     dbus_interface=self.DBUS_OM_IFACE,
                                     signal_name='InterfacesAdded')

        self.bus.add_signal_receiver(self._properties_changed,
                                     dbus_interface=self.DBUS_PROP_IFACE,
                                     signal_name='PropertiesChanged',
                                     arg0=self.DEVICE_INTERFACE,
                                     path_keyword='path')

        self.register_hid_profile()

        self.alias = 'Stenogotchi'
        self.discoverabletimeout = 0
        self.discoverable = True
        self.bthost_mac = None
        self.bthost_name = ""

        logging.info('[plover_link] Configured BT device with name {}'.format(self.alias))

    def interfaces_added(self, path, device_info):
        pass

    def _properties_changed(self, interface, changed, invalidated, path):
        if self.on_disconnect is not None:
            if 'Connected' in changed:
                if not changed['Connected']:
                    self.on_disconnect()

    def on_disconnect(self):
        if self.autoconnect_in_progress:
            return

        logging.info('[plover_link] The client has been disconnected')
        self.bthost_mac = None
        self.bthost_name = ""
        # Attempt to auto_connect once, then go back to listening mode
        connected = self.auto_connect()
        if not connected:
            if not self.bt_agent_running:
                self.register_bt_pairing_agent()
            if not self.scontrol:
                self.listen()


    @property
    def address(self):
        """ Return the adapter MAC address. """
        return self.adapter_property.Get(self.ADAPTER_IFACE,
                                         'Address')

    @property
    def powered(self):
        """ Power state of the Adapter. """
        return self.adapter_property.Get(self.ADAPTER_IFACE, 'Powered')

    @powered.setter
    def powered(self, new_state):
        self.adapter_property.Set(self.ADAPTER_IFACE, 'Powered', new_state)

    @property
    def alias(self):
        return self.adapter_property.Get(self.ADAPTER_IFACE,
                                         'Alias')

    @alias.setter
    def alias(self, new_alias):
        self.adapter_property.Set(self.ADAPTER_IFACE,
                                  'Alias',
                                  new_alias)

    @property
    def discoverabletimeout(self):
        """ Discoverable timeout of the Adapter. """
        return self.adapter_props.Get(self.ADAPTER_IFACE,
                                      'DiscoverableTimeout')

    @discoverabletimeout.setter
    def discoverabletimeout(self, new_timeout):
        self.adapter_property.Set(self.ADAPTER_IFACE,
                                  'DiscoverableTimeout',
                                  dbus.UInt32(new_timeout))

    @property
    def discoverable(self):
        """ Discoverable state of the Adapter. """
        return self.adapter_props.Get(
            self.ADAPTER_INTERFACE, 'Discoverable')

    @discoverable.setter
    def discoverable(self, new_state):
        self.adapter_property.Set(self.ADAPTER_IFACE,
                                  'Discoverable',
                                  new_state)

    def register_hid_profile(self):
        """
        Setup and register HID Profile
        """

        logging.debug('[plover_link] Configuring Bluez Profile')
        service_record = self.read_sdp_service_record()

        opts = {
            'Role': 'server',
            'RequireAuthentication': True,
            'RequireAuthorization': True,
            'AutoConnect': True,
            'ServiceRecord': service_record,
        }

        manager = dbus.Interface(self.bus.get_object('org.bluez',
                                                     '/org/bluez'),
                                 'org.bluez.ProfileManager1')

        HumanInterfaceDeviceProfile(self.bus,
                                    BTKbDevice.PROFILE_DBUS_PATH)

        manager.RegisterProfile(BTKbDevice.PROFILE_DBUS_PATH,
                                BTKbDevice.UUID,
                                opts)

        logging.debug('[plover_link] Profile registered ')

    def register_bt_pairing_agent(self):
        """
        Setup and register BT paring agent
        """
        capability = 'NoInputNoOutput'
        manager = dbus.Interface(self.bus.get_object('org.bluez',
                                                     '/org/bluez'),
                                 'org.bluez.AgentManager1')
        Agent(self.bus, BTKbDevice.AGENT_DBUS_PATH)

        manager.RegisterAgent(BTKbDevice.AGENT_DBUS_PATH, capability)
        #manager.UnregisterAgent(BTKbDevice.AGENT_DBUS_PATH, capability)
        manager.RequestDefaultAgent(BTKbDevice.AGENT_DBUS_PATH)
        self.bt_agent_running = True
        logging.debug(f'[plover_link] Registered secure Bluez pairing agent with capability: {capability}')

    @staticmethod
    def read_sdp_service_record():
        """
        Read and return SDP record from a file
        :return: (string) SDP record
        """
        logging.debug('[plover_link] Reading service record')
        try:
            fh = open(BTKbDevice.SDP_RECORD_PATH, 'r')
        except OSError:
            sys.exit('Could not open the sdp record. Exiting...')

        return fh.read()

    def create_ssockets(self):
        """ Create passive listening sockets and close possibly exising ones """
        logging.debug("[plover_link] Creating BT listening ssockets")

        if self.scontrol:
            self.scontrol.close()
        if self.sinterrupt:
            self.sinterrupt.close()

        self.scontrol = socket.socket(socket.AF_BLUETOOTH,
                                socket.SOCK_SEQPACKET,
                                socket.BTPROTO_L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt = socket.socket(socket.AF_BLUETOOTH,
                                        socket.SOCK_SEQPACKET,
                                        socket.BTPROTO_L2CAP)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def listen(self):
        """
        Listen for connections coming from HID client
        """
        if not self.scontrol or not self.sinterrupt:
             self.create_ssockets()

        try:
            # Bind address/port to existing sockets
            self.scontrol.bind((self.address, self.P_CTRL))
            self.sinterrupt.bind((self.address, self.P_INTR))

            # Start listening on the server sockets with limit of 1 connection per socket
            self.scontrol.listen(1)
            self.sinterrupt.listen(1)

            logging.info('[plover_link] Waiting for connections')

            self.ccontrol, cinfo = self.scontrol.accept()
            logging.debug('[plover_link] {} connected on the ccontrol socket'.format(cinfo[0]))

            self.cinterrupt, cinfo = self.sinterrupt.accept()
            logging.debug('[plover_link] {} connected on the cinterrupt channel'.format(cinfo[0]))

            self.bthost_mac = cinfo[0]
            self.bthost_name = self.get_connected_device_name()

            self.bt_last_conn = self.bthost_mac

        except OSError as ex:
            logging.error(f"[plover_link] Failed to enter listening mode: {ex}")
            logging.info(f"[plover_link] If issue persists, check that your '/lib/systemd/system/bluetooth.service' file still contains 'ExecStart=/usr/lib/bluetooth/bluetoothd -P input'")

    def auto_connect(self):
        """ Automatically connects to preferred BT devices in listed order. Also handles reconnect attempts at lost connection. """

        # Check if we should make a reconnect attempt to previous BT device
        if self.bt_last_conn:
            reconnect = True
        else:
            reconnect = False

        if not self.bt_autoconnect_list and not reconnect:
            logging.info('[plover_link] No bt_autoconnect_mac set in config. Listening for incoming connections instead...')
            return False
        else:
            self.autoconnect_in_progress = True

            if reconnect:
                if not self.bt_last_conn:
                    return False
                logging.info('[plover_link] Waiting 5 seconds before attempting to reconnect to lost BT device...')
                sleep(5) # Sleep 5 seconds before attempting a reconnect to lost BT device
                autoconnect_list = [self.bt_last_conn]
            else:
                logging.info('[plover_link] Trying to auto connect to preferred BT host(s)...')
                autoconnect_list = self.bt_autoconnect_list.copy()

            for i in autoconnect_list:
                logging.info(f'[plover_link] Trying to auto connect to {i}')
                try:
                    self.ccontrol = socket.socket(socket.AF_BLUETOOTH,
                                    socket.SOCK_SEQPACKET,
                                    socket.BTPROTO_L2CAP)

                    self.cinterrupt = socket.socket(socket.AF_BLUETOOTH,
                                    socket.SOCK_SEQPACKET,
                                    socket.BTPROTO_L2CAP)

                    self.ccontrol.connect((i, self.P_CTRL))
                    self.cinterrupt.connect((i, self.P_INTR))

                    # On successful connection
                    self.autoconnect_in_progress = False
                    self.bthost_mac = i
                    self.bt_last_conn = i
                    self.bthost_name = self.get_connected_device_name()
                    return True # stop trying to auto connect upon success


                except Exception as e:
                    if e.__class__.__name__ == "OSError" and str(e) == "[Errno 52] Invalid exchange":
                            self.unpair_device(i)
                            logging.info(f'[plover_link] Invalid handshake exchange with {i}. Unpaired device. Please re-initiate pairing from remote device.')
                    elif (e.__class__.__name__ == "PermissionError" and str(e) == "[Errno 13] Permission denied"):
                        logging.info(f'[plover_link] Permission to connect to {i} denied. Ensure device has been paired.')
                    elif (e.__class__.__name__ == "ConnectionRefusedError" and str(e) == "[Errno 111] Connection refused"):
                        logging.info(f'[plover_link] Connection to {i} refused. Ensure device has been paired and is available.')
                    elif e.__class__.__name__ == "OSError" and str(e) == "[Errno 112] Host is down":
                        logging.info(f'[plover_link] Host {i} is down.')
                    else:
                        logging.info(f'[plover_link] Failed to connect to {i} due to "{e.__class__.__name__}" : "{e}"')
                    if self.bt_autoconnect_list and not reconnect:
                        if i in self.bt_autoconnect_list:
                            self.bt_autoconnect_list.remove(i)

                    # If all addresses attempted without success
                    if not self.bt_autoconnect_list or reconnect:
                        logging.info('[plover_link] Unsuccessful auto connect attempt. Listening for incoming connections instead...')
                        self.autoconnect_in_progress = False
                        self.bt_last_conn = None
                        return False

                    sleep(2)

    def unpair_device(self, address):
        """ Removes remote device including pairing information """

        proxy_object = self.bus.get_object("org.bluez","/")
        manager = dbus.Interface(proxy_object, "org.freedesktop.DBus.ObjectManager")
        managed_objects = manager.GetManagedObjects()
        for path in managed_objects:
            adr = managed_objects[path].get('org.bluez.Device1', {}).get('Address', False)
            if adr == address:
                self.adapter_methods.RemoveDevice(path)



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
                logging.info(f'[plover_link] Device {alias} [{addr}] is connected')

                sleep(1)
                self.send([0xA1, 1, 0, 0, 30, 0, 0, 0, 0, 0])
                sleep(0.01)
                self.send([0xA1, 1, 0, 0,  0, 0, 0, 0, 0, 0])
                sleep(0.01)

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
        logging.info('[plover_link] Setting up Stenogotchi D-Bus service')
        bus_name = dbus.service.BusName('com.github.stenogotchi', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/com/github/stenogotchi')

        self.device = BTKbDevice()  # create and setup our BTKbDevice

    def auto_connect(self):
        """ Connect to preferred bt_mac(s). If unspecified or unavailable fall back to await new and trusted incoming connections """
        connected = self.device.auto_connect()
        if not connected:
            self.device.register_bt_pairing_agent() # Handler for new pairing attempts
            self.device.listen() # Handler for incoming trusted connections

    @dbus.service.method('com.github.stenogotchi', in_signature='aay')   # array of bytearrays
    def send_keys(self, key_list):
        for key in key_list:
            self.device.send(key)

if __name__ == '__main__':
    # The sockets require root permission
    if not os.geteuid() == 0:
        sys.exit('Only root can run this script')

    logging.basicConfig(
        level=logging.DEBUG,  # Set the logging level to INFO
        format='%(asctime)s - %(levelname)s - %(message)s',  # Format for log messages
        handlers=[
            logging.StreamHandler(sys.stdout)  # Output log messages to stdout
        ]
    )

    DBusGMainLoop(set_as_default=True)
    stenogotchiservice = StenogotchiService()
    stenogotchiservice.auto_connect()
    mainloop = GLib.MainLoop()
    mainloop.run()
