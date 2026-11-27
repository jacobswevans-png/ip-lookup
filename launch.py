import os
import resource
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: launch.py <entry>")
    memory = int(os.environ.get("PT_MEMORY_BYTES", "268435456"))
    pids = int(os.environ.get("PT_PIDS", "128"))
    uid = int(os.environ.get("PT_UID", "65534"))

    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_NPROC, (pids, pids))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    if os.geteuid() == 0:
        os.setgid(uid)
        os.setuid(uid)

    entry = sys.argv[1]
    os.execv(sys.executable, [sys.executable, "-u", entry])


if __name__ == "__main__":
    main()
