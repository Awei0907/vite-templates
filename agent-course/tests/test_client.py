"""Week 0 acceptance checks that do not need a real model key."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        mode = self.server.mode  # type: ignore[attr-defined]
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": "not found"})
            return
        if mode == "unauthorized":
            token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            self._send(401, {"error": f"rejected {token}"})
            return
        if mode == "slow":
            time.sleep(2)
        if mode == "broken":
            self._send_raw(200, b"not-json")
            return
        self._send(200, {"choices": [{"message": {"content": "我是一个测试回复。"}}]})

    def _send(self, status: int, payload: dict) -> None:
        self._send_raw(status, json.dumps(payload).encode("utf-8"))

    def _send_raw(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class Server:
    def __init__(self, mode: str) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.httpd.mode = mode  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        port = self.httpd.server_address[1]
        return f"http://127.0.0.1:{port}/v1"

    def __exit__(self, *_) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def run_client(args: list[str], env_updates: dict[str, str | None]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("MODEL_API_KEY", "MODEL_NAME", "MODEL_BASE_URL", "MODEL_TIMEOUT_SECONDS"):
        env.pop(key, None)
    for key, value in env_updates.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "src.client", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class ClientTests(unittest.TestCase):
    def test_help(self) -> None:
        result = run_client(["--help"], {})
        self.assertEqual(result.returncode, 0)
        self.assertIn("python -m src.client", result.stdout)

    def test_missing_key(self) -> None:
        result = run_client(["你好"], {})
        self.assertEqual(result.returncode, 1)
        self.assertIn("MODEL_API_KEY", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_success_against_local_server(self) -> None:
        with Server("ok") as base_url:
            result = run_client(
                ["用一句话介绍你自己"],
                {
                    "MODEL_API_KEY": "test-key-week0",
                    "MODEL_NAME": "fake-model",
                    "MODEL_BASE_URL": base_url,
                    "MODEL_TIMEOUT_SECONDS": "5",
                },
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "我是一个测试回复。")
        self.assertNotIn("test-key-week0", result.stdout + result.stderr)

    def test_rejected_key_is_redacted(self) -> None:
        secret = "test-key-week0"
        with Server("unauthorized") as base_url:
            result = run_client(
                ["你好"],
                {
                    "MODEL_API_KEY": secret,
                    "MODEL_BASE_URL": base_url,
                    "MODEL_TIMEOUT_SECONDS": "5",
                },
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP 401", result.stderr)
        self.assertNotIn(secret, result.stderr)
        self.assertNotIn(secret, result.stdout)

    def test_timeout(self) -> None:
        secret = "test-key-week0"
        with Server("slow") as base_url:
            result = run_client(
                ["你好"],
                {
                    "MODEL_API_KEY": secret,
                    "MODEL_BASE_URL": base_url,
                    "MODEL_TIMEOUT_SECONDS": "0.2",
                },
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("请求超时", result.stderr)
        self.assertNotIn(secret, result.stderr)

    def test_connection_error(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        result = run_client(
            ["你好"],
            {
                "MODEL_API_KEY": "test-key-week0",
                "MODEL_BASE_URL": f"http://127.0.0.1:{port}/v1",
                "MODEL_TIMEOUT_SECONDS": "1",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("无法连接模型服务", result.stderr)
        self.assertNotIn("test-key-week0", result.stderr)

    def test_unparseable_response(self) -> None:
        with Server("broken") as base_url:
            result = run_client(
                ["你好"],
                {
                    "MODEL_API_KEY": "test-key-week0",
                    "MODEL_BASE_URL": base_url,
                },
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("无法解析", result.stderr)

    def test_example_env_has_no_secret(self) -> None:
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("MODEL_API_KEY=", text)
        self.assertNotIn("sk-", text)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('python -m src.client "用一句话介绍你自己"', readme)


if __name__ == "__main__":
    unittest.main()
