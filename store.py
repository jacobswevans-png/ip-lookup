import collections
import threading

from config import LOG_LINES


class BotState:
    def __init__(self):
        self.proc = None
        self.status = "offline"
        self.message = ""
        self.entry = None
        self.env = {}
        self.seq = 0
        self.logs = collections.deque(maxlen=LOG_LINES)
        self.lock = threading.Lock()

    def write(self, text, stream="stdout"):
        with self.lock:
            self.seq += 1
            self.logs.append({"seq": self.seq, "stream": stream, "text": text})

    def since(self, cursor):
        with self.lock:
            return [line for line in self.logs if line["seq"] > cursor]


STATE = {}
GUARD = threading.Lock()


def state_for(bot_id):
    with GUARD:
        if bot_id not in STATE:
            STATE[bot_id] = BotState()
        return STATE[bot_id]
