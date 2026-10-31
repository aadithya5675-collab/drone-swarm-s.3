export const REPO_URL = 'https://github.com/<user>/<repo>';
export const AGENT_URL = 'http://127.0.0.1:8765';
export const BEST_REPLAY = 'mission_demo.jsonl';
export const FALLBACK_REPLAY = 'mission_demo.jsonl';
export const LOCAL_SITE = 'http://localhost:8080/story.html';

export const VIDEOS: { file: string; title: string; caption: string }[] = [
  { file: '01_environment.mp4', title: 'The valley', caption: 'The Mundakkai–Chooralmala valley on its real elevation data, with the rescue camp and the swarm on its pads.' },
  { file: '02_disaster.mp4', title: 'The landslide', caption: 'The debris flow runs down the river, sweeping away houses, forest and the Chooralmala bridge.' },
  { file: '03_takeoff.mp4', title: 'Take-off', caption: 'The alert floods the mesh and the swarm launches itself, no pilot involved.' },
  { file: '04_swarm.mp4', title: 'Flying as a swarm', caption: 'Mappers, Scouts and the Relay-Anchor head out, each on its own altitude layer.' },
  { file: '05_scout_detection.mp4', title: 'Scouts find people', caption: 'On-board image processing on the RGB and thermal cameras finds a person and pins them.' },
  { file: '06_alive_vs_deceased.mp4', title: 'Alive or deceased', caption: 'Body heat decides: 30 °C and above is alive, a person-sized blob near air temperature means check first.' },
  { file: '07_mapper_mapping.mp4', title: 'Mapping the new ground', caption: 'The Mappers’ lidar builds a live 3D map of debris no map has seen.' },
  { file: '08_scout_damaged.mp4', title: 'A Scout is hit', caption: 'A Scout loses a motor and goes down. The swarm notices on its own and re-plans its work.' },
  { file: '09_reserve_arrives.mp4', title: 'The reserve arrives', caption: 'The camp launches a reserve Scout from its pad; it joins the search where the lost one stopped.' },
  { file: '10_mapper_damaged.mp4', title: 'A Mapper is hit', caption: 'The Mapper running the planner is lost mid-mission.' },
  { file: '11_brain_failover.mp4', title: 'The other Mapper takes over', caption: 'The standby Mapper takes over the plan within seconds and the mission completes.' },
  { file: '12_relay_anchor.mp4', title: 'The Relay-Anchor', caption: 'The Relay-Anchor holds over the swarm and keeps every drone connected to the camp tower.' },
  { file: '13_return_to_camp.mp4', title: 'Everyone comes home', caption: 'The whole search area checked; every drone flies back to its pad at the camp.' }
];
