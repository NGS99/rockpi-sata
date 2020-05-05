#!/bin/bash
AUTHOR='Akgnah <ka@vamrs.com>'
VERSION='0.12'
PI_MODEL=`tr -d '\0' < /proc/device-tree/model`
RPI_DEB="https://cos.setf.me/rockpi/deb/raspi-sata-${VERSION}.deb"

confirm() {
  printf "%s [Y/n] " "$1"
  read resp < /dev/tty
  if [ "$resp" == "Y" ] || [ "$resp" == "y" ] || [ "$resp" == "yes" ]; then
    return 0
  fi
  if [ "$2" == "abort" ]; then
    echo -e "Abort.\n"
    exit 0
  fi
  return 1
}

rpi_check() {
  packages="python3-rpi.gpio python3-pip python3-pil"
  need_packages=""

  idx=1
  for package in $packages; do
    if ! apt list --installed 2> /dev/null | grep "^$package/" > /dev/null; then
      pkg=$(echo "$packages" | cut -d " " -f $idx)
      need_packages="$need_packages $pkg"
    fi
    ((++idx))
  done

  if [ "$need_packages" != "" ]; then
    echo -e "\nPackage(s) $need_packages is required.\n"
    confirm "Would you like to apt-get install the packages?" "abort"
    apt-get update
    apt-get install --no-install-recommends $need_packages -y
  fi
}

rpi_install() {
  TEMP_DEB="$(mktemp)"
  curl -sL "$RPI_DEB" -o "$TEMP_DEB"
  dpkg -i "$TEMP_DEB"
  rm -f "$TEMP_DEB"
}

rpi_enable() {
  python3 /usr/bin/rockpi-sata/misc.py open_w1_i2c
}

pip_install() {
  pip3 install Adafruit-SSD1306
}

main() {
  if [[ "$PI_MODEL" =~ "Raspberry" ]]; then
    rpi_check
    rpi_install
    pip_install
    rpi_enable
  else
    echo 'nothing'
  fi
}

main
