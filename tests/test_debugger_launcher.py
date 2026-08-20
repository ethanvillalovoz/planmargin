from __future__ import annotations

import socket

from planmargin import debugger_launcher


def test_port_available_detects_bound_loopback_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        assert not debugger_launcher._port_available("127.0.0.1", port)
    assert debugger_launcher._port_available("127.0.0.1", port)


def test_workbench_url_carries_token_only_in_fragment() -> None:
    url = debugger_launcher._workbench_url("local token/+value")

    assert url.startswith("http://127.0.0.1:4200/#")
    assert "token=local+token%2F%2Bvalue" in url
    assert "?" not in url
