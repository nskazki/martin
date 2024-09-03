def handle_yes:
    if not btcl:
        spawn_bctl()
        wait_pcode()
        if pcode:
            print(f"confirm? {pcode}")
        else:
            close_btcl()
    else:
        pair_pcode()

def handle_no:
    if pcode:
        btcl.sendline('no')
        btcl.sendline('no')
        pcode = None

    close_btcl(btcl)

def close_btcl(btcl):
    bctl.sendline('discoverable off')
    bctl.expect('Changing discoverable off succeeded')
    bctl.close()
    btcl = None

def spawn_bctl:
    bctl = pexpect.spawn('bluetoothctl')
    bctl.logfile = sys.stdout
    bctl.timeout = 10
    bctl.expect('#')

def wait_pcode:
    bctl.sendline('power on')
    bctl.expect('Changing power on succeeded')
    bctl.sendline('discoverable on')
    bctl.expect('Changing discoverable on succeeded')
    bctl.sendline('default-agent')
    bctl.expect(r'Confirm passkey (\d+)')
    pcode = bctl.match.group(1).decode('utf-8')
