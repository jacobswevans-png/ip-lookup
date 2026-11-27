import hmac
import threading

from fastapi import FastAPI, Header, HTTPException, Query

import config
import sandbox
import store
from models import DeployRequest

app = FastAPI(title="Pocket Terminal runner", version="1.0.0")


def guard(authorization: str = Header(default="")):
    expected = "Bearer " + config.RUNNER_API_KEY
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def bot(bot_id: str):
    try:
        sandbox.check_bot_id(bot_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return store.state_for(bot_id)


def _start(bot_id, state):
    if state.proc and state.proc.poll() is None:
        return state.status
    if not state.entry:
        raise HTTPException(status_code=400, detail="deploy the bot before starting it")
    state.write("starting", "system")
    try:
        proc = sandbox.start(bot_id, state.entry, state.env)
    except (RuntimeError, OSError) as error:
        state.status = "error"
        state.message = str(error)
        raise HTTPException(status_code=400, detail=str(error))
    state.proc = proc
    state.status = "online"
    state.message = ""
    threading.Thread(target=sandbox.pump, args=(state, proc), daemon=True).start()
    return state.status


@app.get("/health")
def health():
    return {"ok": True, "sandbox": config.sandbox_mode()}


@app.put("/bots/{bot_id}")
def deploy(bot_id: str, body: DeployRequest, authorization: str = Header(default="")):
    guard(authorization)
    state = bot(bot_id)
    if len(body.files) > config.MAX_FILES:
        raise HTTPException(status_code=400, detail="at most " + str(config.MAX_FILES) + " files")
    size = sum(len(value.encode("utf-8")) for value in body.files.values())
    if size > config.MAX_BYTES:
        raise HTTPException(status_code=400, detail="upload is too large")

    sandbox.stop(bot_id, state)
    try:
        directory = sandbox.write_files(bot_id, body.files, body.entry)
        installed = sandbox.install(directory, body.requirements)
    except (ValueError, RuntimeError) as error:
        state.status = "error"
        state.message = str(error)
        raise HTTPException(status_code=400, detail=str(error))

    state.entry = body.entry
    state.env = dict(body.env)
    state.status = "offline"
    state.message = ""
    state.write(
        "deployed " + str(len(body.files)) + " files, entry " + body.entry,
        "system",
    )
    return {"status": state.status, "installed": installed, "message": ""}


@app.post("/bots/{bot_id}/start")
def start(bot_id: str, authorization: str = Header(default="")):
    guard(authorization)
    state = bot(bot_id)
    return {"status": _start(bot_id, state)}


@app.post("/bots/{bot_id}/stop")
def stop(bot_id: str, authorization: str = Header(default="")):
    guard(authorization)
    state = bot(bot_id)
    sandbox.stop(bot_id, state)
    state.write("stopped", "system")
    return {"status": state.status}


@app.post("/bots/{bot_id}/restart")
def restart(bot_id: str, authorization: str = Header(default="")):
    guard(authorization)
    state = bot(bot_id)
    sandbox.stop(bot_id, state)
    state.write("restarting", "system")
    return {"status": _start(bot_id, state)}


@app.get("/bots/{bot_id}")
def status(bot_id: str, authorization: str = Header(default="")):
    guard(authorization)
    state = bot(bot_id)
    return {"status": state.status, "message": state.message}


@app.get("/bots/{bot_id}/logs")
def logs(
    bot_id: str,
    cursor: int = Query(default=0, ge=0),
    authorization: str = Header(default=""),
):
    guard(authorization)
    state = bot(bot_id)
    return {"status": state.status, "cursor": state.seq, "lines": state.since(cursor)}


@app.delete("/bots/{bot_id}")
def remove(bot_id: str, authorization: str = Header(default="")):
    guard(authorization)
    state = bot(bot_id)
    sandbox.remove(bot_id, state)
    return {"status": "offline"}
