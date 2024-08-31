local proc = vt.start("bluetoothctl", { width = 120, height = 20 })

proc:send_str("power on")
proc:send_key("<Enter>")
vt.sleep(300)

proc:send_str("discoverable on")
proc:send_key("<Enter>")
vt.sleep(300)

proc:send_str("default-agent")
proc:send_key("<Enter>")
vt.sleep(300)


while true do
  proc:wait_text("yes/no", timeout: 2147483647)
  proc:send_str("yes")
  proc:send_key("<Enter>")
  print("yes!")
  vt.sleep(300)
end
