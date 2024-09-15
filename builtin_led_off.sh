#! /bin/env bash

for dir in /sys/class/leds/*/; do
  echo none > ${dir}trigger
  echo 0 > ${dir}brightness
done
