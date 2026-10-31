"""Local control agent for the website's LIVE mode: starts the simulation in WSL and serves the site.

Run on the Windows machine that has the simulation installed:  python sim/tools/live_agent.py
Then open http://127.0.0.1:8765 (or the deployed site) and press LIVE.
  GET  /status            {ok, wsl, sim_ready, running, swarm_ready}
  POST /start             sync this checkout into WSL and open the camp (Gazebo + swarm + base)
  POST /trigger           the landslide            body: {"seed": 19}
  POST /damage            hit a drone              body: {"drone": "scout_1"}
  POST /stop              stop everything
"""
import json
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(SIM, 'dashboard')
DISTRO = 'Ubuntu-24.04'
PORT = 8765


def wsl_path(p):
    drive, rest = os.path.splitdrive(os.path.abspath(p))
    return '/mnt/%s%s' % (drive[0].lower(), rest.replace('\\', '/'))


def wsl(cmd, wait=True, timeout=20):
    args = ['wsl', '-d', DISTRO, '--', 'bash', '-lc', cmd]
    if not wait:
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''


def status():
    code, out = wsl('test -d ~/resqmesh/sim/ros2_ws/install/resqmesh_mission && echo installed; '
                    'pgrep -f "gz sim -" >/dev/null && echo running && test -f ~/resqmesh/run/ready && echo swarm', timeout=30)
    return {'ok': True, 'wsl': code == 0 or bool(out), 'sim_ready': 'installed' in out, 'running': 'running' in out,
            'swarm_ready': 'swarm' in out}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Private-Network', 'true')

    def reply(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split('?')[0] == '/status':
            return self.reply(status())
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            body = {}
        tools = '~/resqmesh/sim/tools'
        route = self.path.split('?')[0]
        if route == '/start':
            # WSL ends a session's background processes when its wsl.exe exits, so this one stays open while Gazebo runs
            wsl('bash %s/tools/sync.sh && bash %s/run_story.sh; while pgrep -f "gz sim -" >/dev/null; do sleep 5; done'
                % (wsl_path(SIM), tools), wait=False)
        elif route == '/trigger':
            wsl('bash %s/trigger.sh %d' % (tools, int(body.get('seed', 19))), wait=False)
        elif route == '/damage':
            drone = str(body.get('drone', 'scout_1'))
            if not drone.replace('_', '').isalnum():
                return self.reply({'ok': False, 'error': 'bad drone name'}, 400)
            wsl('bash %s/damage.sh %s' % (tools, drone), wait=False)
        elif route == '/stop':
            wsl('bash %s/kill_all.sh' % tools, wait=False)
        else:
            return self.reply({'ok': False, 'error': 'unknown command'}, 404)
        self.reply({'ok': True, 'command': route[1:]})

    def log_message(self, fmt, *args):
        sys.stderr.write('%s\n' % (fmt % args))


if __name__ == '__main__':
    print('ResQMesh live agent on http://127.0.0.1:%d  (site: %s)' % (PORT, SITE))
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
