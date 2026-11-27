Pocket Terminal runner
======================

A small FastAPI service that gives Pocket Terminal a real place to host Python
bots: deploy files, pip install, start / stop / restart, live logs, one isolated
environment per bot, and processes that keep running when your browser closes.

What runs where
---------------
Pocket Terminal keeps the buttons, the bot list and the console. This runner
does the work: it writes your files, installs requirements.txt, starts the
process, keeps it alive, and streams stdout and stderr back.

Bot tokens never enter the app's browser code. The app stores them on its server
and hands them to this runner only at deploy time. The runner keeps them in
memory and passes them to the bot process; they are never written to disk.

Files
-----
main.py             FastAPI app and every endpoint
config.py           environment and limits
sandbox.py          file writing, pip install, container / process control
launch.py           applies limits, drops privileges, execs the bot
store.py            per-bot state and log buffers
models.py           request schema
requirements.txt    runner dependencies
Dockerfile          runner image
docker-compose.yml  VPS deployment with one container per bot
Caddyfile           optional HTTPS
.env.example        copy to .env

Getting the files on an iPhone
------------------------------
Tap the download button on the Bot hosting page: it saves a .zip. Open Files,
tap the zip once, and iOS unpacks it into a folder called
pocket-terminal-runner.

Path A - Railway (no server to look after, process isolation)
-------------------------------------------------------------
1. github.com in Safari -> + -> New repository -> name it
   pocket-terminal-runner -> Create repository.
2. In the new repo: Add file -> Upload files -> pick every file from the
   unzipped folder -> Commit changes. Files starting with a dot stay hidden in
   Files; skip .env.example, you set variables in Railway instead.
3. railway.app -> New project -> Deploy from GitHub repo -> choose the repo.
   Railway builds the Dockerfile on its own.
4. Open the service -> Variables -> add:
       RUNNER_API_KEY = a long random string (40+ characters)
       SANDBOX       = process
       BOT_ROOT      = /data/bots
5. Add a Volume and mount it at /data so bots survive redeploys.
6. Settings -> Networking -> Generate Domain. If it asks for a port, use 8000.
   Copy the https://... address.
7. Open that address followed by /health in Safari. You should see
   {"ok":true,"sandbox":"process"}.

Railway keeps the service running. Render's free plan sleeps when idle, which
stops your bots - use a paid instance there.

Path B - your own server with Docker (container isolation)
----------------------------------------------------------
Use a small Linux server with Docker, for example a Hetzner CX22 or a
DigitalOcean droplet with the Docker image (around 4 pounds a month). You only
need the provider's browser console; no SSH app.

1. Open the provider's web console for the server.
2. Paste these lines:

    curl -L -o runner.zip https://pocket-terminal.base44.app/api/runner-project
    unzip -o runner.zip
    cd pocket-terminal-runner
    cp .env.example .env
    sed -i "s|^RUNNER_API_KEY=.*|RUNNER_API_KEY=$(openssl rand -hex 32)|" .env
    docker compose up -d --build
    curl -s localhost:8000/health

3. Allow the port if a firewall is on:

    ufw allow 8000

4. RUNNER_URL is http://YOUR_SERVER_IP:8000
5. For HTTPS (recommended, the key travels in a header): point a domain at the
   server, add RUNNER_DOMAIN to .env, and add this service under services: in
   docker-compose.yml, then run docker compose up -d again.

    caddy:
      image: caddy:2
      restart: unless-stopped
      ports:
        - "80:80"
        - "443:443"
      env_file:
        - .env
      volumes:
        - ./Caddyfile:/etc/caddy/Caddyfile
        - caddy_data:/data
        - caddy_config:/config

  Add this at the end of the file:

    volumes:
      caddy_data:
      caddy_config:

  Then RUNNER_URL is https://your-domain.

Where RUNNER_URL and RUNNER_API_KEY come from
---------------------------------------------
RUNNER_URL      The public address of this service, no trailing slash:
                https://something.up.railway.app (Path A)
                http://YOUR_SERVER_IP:8000 (Path B, without the caddy step)
                https://your-domain (Path B with caddy)

RUNNER_API_KEY  The exact value you put in Railway's Variables, or the value
                in .env on the server. You choose it; the service never
                invents one. Generate it with openssl rand -hex 32 and keep a
                copy - the app needs the same string.

Test both before leaving the browser:

    curl -s -H "Authorization: Bearer YOUR_KEY" https://YOUR_URL/bots/test
    # {"status":"offline","message":""}

    curl -s -H "Authorization: Bearer WRONG" https://YOUR_URL/bots/test
    # {"detail":"Unauthorized"} with status 401

Connect it to the app
---------------------
In Pocket Terminal open the dashboard's Secrets page and add:
    RUNNER_URL
    RUNNER_API_KEY

Then open Bot hosting. The pill switches from "no runner" to "runner". Create a
bot, tap deploy (this writes the files and installs requirements.txt), then
start. The console streams stdout and stderr.

Resource limits
---------------
BOT_CPUS        0.5      CPU share per bot
BOT_MEMORY      256m     memory cap per bot
BOT_MEMORY_BYTES 268435456  same cap for process mode, in bytes
BOT_PIDS        128      process / thread cap
MAX_FILES       60       files per deploy
MAX_BYTES       2097152  bytes per deploy
LOG_LINES       1000     lines kept per bot in memory

Docker mode applies the caps with --cpus, --memory, --pids-limit, --cap-drop
ALL and no-new-privileges, and copies the files into the container so it needs
no bind mounts. Process mode applies them with rlimits, a minimal environment
and an unprivileged user (uid 65534), and strips the runner's own environment
so a bot cannot read RUNNER_API_KEY.

Troubleshooting
---------------
401 on every call        The key in the app does not match the runner. Re-copy
                         both sides.
412 in the app           RUNNER_URL or RUNNER_API_KEY is missing in Secrets.
"deploy the bot first"   Tap deploy before start.
"entry was not included" The entry file name does not match a file in the
                         drive. Create it in the terminal first.
pip fails on deploy      Read the message on the card: a missing version or a
                         package without a wheel for linux/amd64.
Bot exits immediately     Open the console - the traceback is there.
Process mode, 0 bots     Render free tier sleeps. Use a paid instance.
