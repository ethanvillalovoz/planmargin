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


def test_launcher_defaults_to_offline_assistant() -> None:
    args = debugger_launcher._parse_args([])

    assert args.assistant_provider == "offline"
    assert not args.confirm_gemini_free_tier


def test_launcher_accepts_explicit_free_tier_gemini_configuration() -> None:
    args = debugger_launcher._parse_args(
        [
            "--assistant-provider",
            "gemini",
            "--confirm-gemini-free-tier",
            "--gemini-model",
            "gemini-3.1-flash-lite",
        ]
    )

    assert args.assistant_provider == "gemini"
    assert args.confirm_gemini_free_tier
    assert args.gemini_model == "gemini-3.1-flash-lite"
