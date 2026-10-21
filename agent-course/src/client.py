"""Send one prompt to an OpenAI-compatible chat model.

Week 0 only proves that a key, a timeout, and an error can be handled.
The agent loop starts in Week 1.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HELP = """\
用法：
  python -m src.client "用一句话介绍你自己"

从环境变量或当前目录的 .env 读取：
  MODEL_API_KEY          必填
  MODEL_NAME             默认 gpt-4o-mini
  MODEL_BASE_URL         默认 https://api.openai.com/v1
  MODEL_TIMEOUT_SECONDS  默认 30

标准输出只有模型回复。错误写到标准错误，退出码为 1。
"""


class ModelError(Exception):
    """A readable failure that is safe to show on a terminal."""


@dataclass(frozen=True)
class Config:
    api_key: str
    model: str
    base_url: str
    timeout: float


def scrub(text: str, secret: str) -> str:
    """Remove the API key if a server or exception echoes it back."""
    if not text:
        return ""
    redacted = text
    if secret:
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def load_dotenv(path: Path | None = None) -> None:
    """Fill empty environment variables from a .env file.

    Existing environment variables stay as they are. The current working
    directory is checked before the project root.
    """
    if path is not None:
        _apply_dotenv(path)
        return
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"]
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        _apply_dotenv(resolved)


def _apply_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def load_config() -> Config:
    api_key = os.environ.get("MODEL_API_KEY", "").strip()
    if not api_key:
        raise ModelError("缺少 MODEL_API_KEY。请复制 .env.example 为 .env 并填入密钥。")
    model = os.environ.get("MODEL_NAME", "").strip() or "gpt-4o-mini"
    base_url = os.environ.get("MODEL_BASE_URL", "").strip() or "https://api.openai.com/v1"
    timeout_raw = os.environ.get("MODEL_TIMEOUT_SECONDS", "").strip() or "30"
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise ModelError("MODEL_TIMEOUT_SECONDS 必须是数字，例如 30。") from exc
    if timeout <= 0:
        raise ModelError("MODEL_TIMEOUT_SECONDS 必须大于 0。")
    return Config(api_key=api_key, model=model, base_url=base_url, timeout=timeout)


def call_model(prompt: str, config: Config) -> str:
    url = config.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 256,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ModelError(_http_error(exc.code, body, config.api_key)) from None
    except (TimeoutError, socket.timeout):
        raise ModelError(_timeout_message(config)) from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ModelError(_timeout_message(config)) from None
        raise ModelError(
            scrub("无法连接模型服务。请检查 MODEL_BASE_URL 和网络。", config.api_key)
        ) from None

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ModelError("模型返回了无法解析的内容。") from exc
    if not isinstance(content, str) or not content.strip():
        raise ModelError("模型没有返回文本。")
    return content.strip()


def _timeout_message(config: Config) -> str:
    seconds = int(config.timeout) if config.timeout.is_integer() else config.timeout
    return scrub(
        f"请求超时（{seconds} 秒）。请检查网络，或增大 MODEL_TIMEOUT_SECONDS。",
        config.api_key,
    )


def _http_error(status: int, body: str, secret: str) -> str:
    if status in {401, 403}:
        message = f"模型服务拒绝了密钥（HTTP {status}）。请检查 MODEL_API_KEY。"
    else:
        excerpt = " ".join(body.split())[:180]
        message = f"模型服务返回 HTTP {status}。"
        if excerpt:
            message = f"{message} {excerpt}"
    return scrub(message, secret)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("需要 Python 3.11 或更高版本。", file=sys.stderr)
        return 1
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help"}:
        print(HELP, end="")
        return 0
    prompt = " ".join(args).strip() or "用一句话介绍你自己"
    try:
        load_dotenv()
        text = call_model(prompt, load_config())
    except ModelError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
