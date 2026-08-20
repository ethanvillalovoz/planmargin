"""Launch the local evidence API and Angular debugger as one supervised process."""

from __future__ import annotations

import argparse
import secrets
import signal
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from planmargin.evidence_api import create_app

API_PORT = 8765
WEB_PORT = 4200


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = args.root.resolve()
    debugger = root / "web" / "debugger"
    if (
        not (root / "pyproject.toml").is_file()
        or not (debugger / "package.json").is_file()
    ):
        raise SystemExit("--root must identify the PlanMargin repository")
    for port in (API_PORT, WEB_PORT):
        if not _port_available("127.0.0.1", port):
            raise SystemExit(f"127.0.0.1:{port} is already in use")
    if not (debugger / "node_modules").is_dir():
        raise SystemExit(
            "Frontend dependencies are missing; run npm ci in web/debugger"
        )

    token = secrets.token_urlsafe(32)
    app = create_app(root=root, token=token)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=API_PORT, log_level="warning")
    )
    api_thread = threading.Thread(target=server.run, name="planmargin-api", daemon=True)
    api_thread.start()
    deadline = time.monotonic() + 30.0
    while not server.started and api_thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise SystemExit("The local evidence API did not become ready")

    command = [
        "npm",
        "start",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(WEB_PORT),
    ]
    web = subprocess.Popen(command, cwd=debugger)
    url = f"http://127.0.0.1:{WEB_PORT}/"
    print("\nPlanMargin workbench")
    print(f"URL: {url}")
    print(f"Ephemeral local token: {token}")
    print(
        "Paste the token into Connect real evidence. Press Ctrl-C to stop both services.\n"
    )
    opener: threading.Timer | None = None
    if not args.no_browser:
        opener = threading.Timer(2.0, webbrowser.open, args=(url,))
        opener.start()

    def stop(_: int, __: object) -> None:
        server.should_exit = True
        if web.poll() is None:
            web.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        return_code = web.wait()
        if return_code != 0 and not server.should_exit:
            raise SystemExit(return_code)
    finally:
        if opener is not None:
            opener.cancel()
        server.should_exit = True
        if web.poll() is None:
            web.terminate()
        api_thread.join(timeout=5.0)


if __name__ == "__main__":
    main()
