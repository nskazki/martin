A remake of https://github.com/Anodynous/stenogotchi for making any old keyboard wireless.

# Demo

https://github.com/user-attachments/assets/a12da5b0-083d-4dac-8ee8-fa671276df1d

# How to Cat

1. Power the device by toggling the ON/OFF switch on the left.
   1. If the switch is already in the ON position but the device is OFF,
      press the button on the right on the same board.
   2. If the blue light flashes once as you toggle the switch,
      charge the device by plugging a USB-C cable into the same board.
2. Use buttons A to D to control the cat once it's climbed the screen.

# How to Bluetooth

1. Press button E to switch the buttons layer.
   The green light on the front board lights on when in the alternative layer.
2. Press button D to make the device discoverable.
4. Connect to the "Martin" Bluetooth input device on a phone or computer and confirm pairing by pressing button D again.
5. Plug a keyboard into the device and enjoy the wireless but slightly delayed typing experience 🐈‍⬛ 

# How to Re-Bluetooth

1. Press button C to reconnect to the last device in the alternative layer.
2. Press button B to try the next paired device.
3. Press button A to power OFF safely.

# How to Tinker

1. The device will automatically connect to any open WiFi named Martin while it boots.
2. Check the router's dashboard to figure out the device's IP.
3. SSH to the device's IP using user `root` and password `Martin`. Assuming it's `192.168.1.2`, you'd do `ssh root@192.168.1.2`.
4. Once logged in, open the `bluetoothctl` REPL and use the `remove` command to remove unwanted paired devices. Type `remove` and press Tab to see the device list.
5. When back in the shell, run `screen -r` to connect to the detached session in which `mprocs` is running.
6. Once attached to the session, select the process using arrows and restart by pressing the `r` key.
7. Press Ctrl+a followed by Ctrl+d to detach the session. 
