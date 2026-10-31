"""Write config/gui_story.config: the gz-sim GUI with a dark theme, camera on the camp."""
import os
import re
import sys

src = '/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/gui/gui.config'
out = sys.argv[1]
s = open(src).read()
s = s.replace('<dialog name="quick_start" show_again="true"/>', '<dialog name="quick_start" show_again="false"/>')
s = re.sub(r'<width>\d+</width>\s*<height>\d+</height>', '<width>1600</width>\n  <height>950</height>', s, count=1)
s = s.replace('material_theme="Light"', 'material_theme="Dark"').replace('material_primary="DeepOrange"', 'material_primary="Cyan"')
s = s.replace('<ambient_light>0.4 0.4 0.4</ambient_light>', '<ambient_light>0.45 0.48 0.52</ambient_light>')
s = s.replace('<background_color>0.8 0.8 0.8</background_color>', '<background_color>0.62 0.74 0.86</background_color>\n  <sky></sky>\n  <camera_clip><near>0.25</near><far>6000</far></camera_clip>')
s = s.replace('<camera_pose>-6 0 6 0 0.5 0</camera_pose>', '<camera_pose>35 75 55 0 0.32 -1.75</camera_pose>')
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w').write(s)
print('wrote', out)
