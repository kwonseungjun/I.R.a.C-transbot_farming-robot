#!/usr/bin/env bash
PKG=manipulator_position_controller
DST=~/transbot_ws/src
echo "Copying package to $DST ..."
mkdir -p "$DST"
cp -r "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" "$DST/"
cd ~/transbot_ws || exit 1
if command -v catkin_make_isolated >/dev/null 2>&1; then
  catkin_make_isolated
  echo "Source with: source ~/transbot_ws/devel_isolated/setup.bash"
else
  catkin_make
  echo "Source with: source ~/transbot_ws/devel/setup.bash"
fi
