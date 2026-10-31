"""Camp-side and swarm-wide nodes for the Wayanad story (drones themselves come from tools/launch_drone.sh)."""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def build(context):
    sim = os.path.expanduser(LaunchConfiguration('sim_dir').perform(context))
    cfg = os.path.join(sim, 'config')
    p = {'fleet': os.path.join(cfg, 'fleet_story.yaml'), 'layout': os.path.join(cfg, 'wayanad.json'),
         'prior': os.path.join(cfg, 'dem_prior.npz')}
    return [
        Node(package='resqmesh_mission', executable='radio_medium', name='radio_medium',
             parameters=[{'layout': p['layout'], 'prior': p['prior']}], output='screen'),
        Node(package='resqmesh_mission', executable='mesh_agent', name='mesh_tower',
             parameters=[{'node': 'tower', 'services': 'base'}], output='screen'),
        Node(package='resqmesh_mission', executable='brain', name='brain',
             parameters=[dict(p, host='mapper_1', standby='mapper_2')], output='screen'),
        Node(package='resqmesh_mission', executable='base_station', name='base_station',
             parameters=[{'fleet': p['fleet'], 'layout': p['layout'], 'sim_dir': sim}], output='screen'),
        Node(package='rosbridge_server', executable='rosbridge_websocket', name='rosbridge', parameters=[{'port': 9090}]),
        ExecuteProcess(cmd=['python3', '-m', 'http.server', '8080', '--directory', os.path.join(sim, 'dashboard')], output='log'),
    ]


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('sim_dir', default_value='~/resqmesh/sim'), OpaqueFunction(function=build)])
