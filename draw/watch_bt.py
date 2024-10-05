import re
import dbus
import traceback
from spawn import spawn
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

DEVICE_INTERFACE = 'org.bluez.Device1'
DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'

sole_callback = None

def watch_bt(callback):
    global sole_callback

    if sole_callback:
        raise Exception("already watching!")

    sole_callback = callback

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    bus.add_signal_receiver(
        on_change,
        dbus_interface=DBUS_PROP_IFACE,
        signal_name='PropertiesChanged',
        arg0=DEVICE_INTERFACE,
        path_keyword='path'
    )

    mainloop = GLib.MainLoop()
    return mainloop

def on_change(interface, changed, invalidated, path):
    if 'Connected' in changed:
        address = parse_address(path)
        connected = changed['Connected']
        sole_callback(connected, address)

def parse_address(path):
    return re.search(r"([A-F0-9]{2}[_:]){5}[A-F0-9]{2}", path).group().replace("_", ":")
