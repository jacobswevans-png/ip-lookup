import os
import re
import shlex
import shutil
import subprocess
import sys
import time

import config

NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def check_bot_id(bot_id):
    if not ID_RE.match(bot_id or ""):
        raise ValueError("invalid bot id")


def bot_dir(bot_id):
    check_bot_id(bot_id)
    path = (config.BOT_ROOT / bot_id).resolve()
    if path.parent != config.BOT_ROOT:
        raise ValueError("invalid bot id")
    return path


def write_files(bot_id, files, entry):
    if entry not in files:
        raise ValueError(entry + " was not included in the upload")
    directory = bot_dir(bot_id)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        if not NAME_RE.match(name):
            raise ValueError("invalid file name: " + name)
        (directory / name).write_text(content, encoding="utf-8")
    return directory


def own(path):
    if os.geteuid() != 0:
        return
    for root, _dirs, files in os.walk(path):
        for target in [root] + [os.path.join(root, name) for name in files]:
            try:
                os.chown(target, config.BOT_USER_ID, config.BOT_USER_ID)
            except OSError:
                pass


def _docker_install(directory, deps):
    name = "pt-install-" + str(os.getpid()) + "-" + str(int(time.time()))
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    created = subprocess.run(
        [
            "docker", "create", "--name", name, "--network", "bridge",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", config.BOT_MEMORY, "--cpus", config.BOT_CPUS,
            config.BOT_IMAGE, "pip", "install", "--no-cache-dir",
            "--disable-pip-version-check", "--target", "/deps", "-r", "/req.txt",
        ],
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        raise RuntimeError(created.stderr.strip()[-1200:])
    try:
        copied = subprocess.run(
            ["docker", "cp", str(directory / "requirements.txt"), name + ":/req.txt"],
            capture_output=True,
            text=True,
        )
        if copied.returncode != 0:
            raise RuntimeError(copied.stderr.strip()[-1200:])
        run = subprocess.run(
            ["docker", "start", "-a", name], capture_output=True, text=True, timeout=900
        )
        code = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.ExitCode}}", name],
            capture_output=True,
            text=True,
        )
        if (code.stdout or "").strip() != "0":
            raise RuntimeError((run.stdout or run.stderr).strip()[-1200:])
        subprocess.run(
            ["docker", "cp", name + ":/deps/.", str(deps)], capture_output=True, text=True
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def install(directory, requirements):
    if not requirements.strip():
        return []
    (directory / "requirements.txt").write_text(requirements, encoding="utf-8")
    deps = directory / ".deps"
    deps.mkdir(exist_ok=True)
    if config.sandbox_mode() == "docker":
        _docker_install(directory, deps)
    else:
        own(directory)
        command = [
            sys.executable, "-m", "pip", "install", "--no-cache-dir",
            "--disable-pip-version-check", "--target", str(deps),
            "-r", str(directory / "requirements.txt"),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout).strip()[-1200:])
    own(directory)
    return [
        re.split(r"[=<>!~ ]", line.strip(), 1)[0]
        for line in requirements.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def start(bot_id, entry, env):
    directory = bot_dir(bot_id)

    if config.sandbox_mode() == "docker":
        name = "pt-" + bot_id
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        args = [
            "docker", "create", "--name", name,
            "--cpus", config.BOT_CPUS,
            "--memory", config.BOT_MEMORY,
            "--pids-limit", str(config.BOT_PIDS),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--network", "bridge",
        ]
        for key, value in env.items():
            args += ["-e", key + "=" + value]
        args += [
            config.BOT_IMAGE, "sh", "-c",
            "PYTHONPATH=/app/.deps exec python -u " + shlex.quote(entry),
        ]
        created = subprocess.run(args, capture_output=True, text=True)
        if created.returncode != 0:
            raise RuntimeError(created.stderr.strip()[-1200:])
        copied = subprocess.run(
            ["docker", "cp", str(directory) + "/.", name + ":/app"],
            capture_output=True,
            text=True,
        )
        if copied.returncode != 0:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            raise RuntimeError(copied.stderr.strip()[-1200:])
        return subprocess.Popen(
            ["docker", "start", "-a", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    clean = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(directory),
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(directory / ".deps"),
        "PT_MEMORY_BYTES": str(config.BOT_MEMORY_BYTES),
        "PT_PIDS": str(config.BOT_PIDS),
        "PT_UID": str(config.BOT_USER_ID),
    }
    clean.update(env)
    launcher = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch.py")
    return subprocess.Popen(
        [sys.executable, launcher, entry],
        cwd=str(directory),
        env=clean,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def pump(state, proc):
    try:
        for line in iter(proc.stdout.readline, ""):
            state.write(line.rstrip("\n"))
    finally:
        code = proc.wait()
        if state.status != "offline":
            state.status = "offline" if code == 0 else "error"
            state.message = "" if code == 0 else "process exited with code " + str(code)
            state.write(state.message or "process exited", "system")
        state.proc = None


def stop(bot_id, state):
    if config.sandbox_mode() == "docker":
        subprocess.run(["docker", "rm", "-f", "pt-" + bot_id], capture_output=True)
    proc = state.proc
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    state.proc = None
    state.status = "offline"
    state.message = ""


def remove(bot_id, state):
    stop(bot_id, state)
    shutil.rmtree(bot_dir(bot_id), ignore_errors=True)
