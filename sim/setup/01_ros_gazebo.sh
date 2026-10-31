#!/usr/bin/env bash
# ROS 2 Jazzy, Gazebo Harmonic (ros_gz), rosbridge and build tools. Run as root in WSL Ubuntu 24.04:
#   wsl -d Ubuntu-24.04 -u root -- bash setup/01_ros_gazebo.sh [wsl_user]
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
U=${1:-$(ls /home | head -1)}

apt-get update
apt-get install -y locales software-properties-common curl gnupg lsb-release ca-certificates
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
add-apt-repository -y universe

ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F '"tag_name"' | awk -F'"' '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"
dpkg -i /tmp/ros2-apt-source.deb
apt-get update
apt-get upgrade -y

apt-get install -y \
  ros-jazzy-ros-base ros-jazzy-ros-gz ros-jazzy-rviz2 ros-jazzy-xacro \
  ros-jazzy-robot-state-publisher ros-jazzy-tf2-tools ros-jazzy-rosbridge-suite \
  ros-dev-tools python3-colcon-common-extensions python3-rosdep python3-vcstool \
  git build-essential cmake ninja-build python3-pip python3-venv unzip zip jq tmux mesa-utils

[ -f /etc/ros/rosdep/sources.list.d/20-default.list ] || rosdep init
grep -q '/opt/ros/jazzy/setup.bash' /home/$U/.bashrc || echo 'source /opt/ros/jazzy/setup.bash' >> /home/$U/.bashrc
echo "ROS+GZ DONE"
bash -c "source /opt/ros/jazzy/setup.bash && gz sim --versions" || true
