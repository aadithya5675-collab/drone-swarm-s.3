SIM=$HOME/resqmesh/sim; PX4=$HOME/PX4-Autopilot; LOG=$HOME/resqmesh/logs/story; RUN=$HOME/resqmesh/run
mkdir -p "$LOG" "$RUN"
source /opt/ros/jazzy/setup.bash
source "$SIM/ros2_ws/install/setup.bash"
source "$PX4/build/px4_sitl_default/gz_env.sh"
export GZ_SIM_SERVER_CONFIG_PATH=$SIM/config/gz_server.config
export GZ_SIM_RESOURCE_PATH=$SIM/models:$GZ_SIM_RESOURCE_PATH GZ_IP=127.0.0.1
WORLD=resqmesh_wayanad
# render on the NVIDIA GPU through WSL's D3D12 bridge (the default is llvmpipe, CPU rendering)
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-} GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
CFG=$SIM/config
fleet_get() {
  python3 -c "import yaml,sys; d={x['name']:x for x in yaml.safe_load(open('$CFG/fleet_story.yaml'))['drones']}[sys.argv[1]]; v=d.get(sys.argv[2],''); print(' '.join(map(str,v)) if isinstance(v,list) else v)" "$1" "$2"
}
