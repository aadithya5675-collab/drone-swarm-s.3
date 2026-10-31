from glob import glob

from setuptools import setup

package_name = 'resqmesh_mission'
setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Team Apex',
    maintainer_email='arcclub@kpriet.ac.in',
    description='ResQMesh swarm mission software: planner, flight agents, detectors, mesh emulator',
    license='MIT',
    tests_require=['pytest'],
    entry_points={'console_scripts': [
        'trigger_landslide = resqmesh_mission.trigger_landslide:main',
        'radio_medium = resqmesh_mission.radio_medium:main',
        'mesh_agent = resqmesh_mission.mesh_agent:main',
        'brain = resqmesh_mission.brain:main',
        'base_station = resqmesh_mission.base_station:main',
        'drone_agent = resqmesh_mission.drone_agent:main',
        'story_detector = resqmesh_mission.story_detector:main',
        'lidar_mapper = resqmesh_mission.lidar_mapper:main',
        'damage_scout = resqmesh_mission.damage_scout:main',
    ]},
)
