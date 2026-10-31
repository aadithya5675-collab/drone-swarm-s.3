/* Drone roles and CAD part labels (no three.js here, so the briefing text loads without the 3D bundle). */
export type RoleName = 'scout' | 'mapper' | 'relay';

/** CAD part name (from the SDF visual) -> what it does and the part it is. */
export function partInfo(raw: string): { what: string; part: string } | null {
  const n = raw.replace(/_+$/, '').replace(/_\d+$/, '');
  const pretty = n.replace(/___/g, ' + ').replace(/__/g, ' (').replace(/_/g, ' ').replace(/ \(([^()]*)$/, ' ($1)').replace(/ 3 5/, ' 3.5').trim();
  const R: [RegExp, string][] = [
    [/Sensor_head/, 'Thermal + colour camera head'], [/Livox|lidar/i, '3D lidar (maps the debris)'], [/Jetson/, 'On-board computer: image processing / mapping'],
    [/Raspberry/, 'Companion computer: mesh routing'], [/RFD900/, 'Long-range radio link to the camp'], [/Wi_Fi_LoRa|mesh_node/, 'Mesh radio node'],
    [/GNSS/, 'GPS + compass'], [/SpeedyBee/, 'Flight controller (PX4)'], [/LiPo|battery/i, 'Battery'], [/Landing_gear/, 'Landing gear'],
    [/adapter_plate/, 'Payload adapter plate'], [/airframe/, 'Carbon airframe'], [/rotor/, 'Propeller'], [/led_motor/, 'Navigation light'], [/role_beacon/, 'Role beacon']
  ];
  const hit = R.find(([re]) => re.test(n));
  if (!hit) return { what: pretty, part: '' };
  return { what: hit[1], part: /rotor|led_motor|role_beacon|airframe|battery_under/.test(n) ? '' : pretty };
}

