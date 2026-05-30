from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from balatro_agent.model import ActionProposal


DEFAULT_BASE_URL = "http://127.0.0.1:12346"


class BalatroBotError(RuntimeError):
    def __init__(
        self,
        code: int,
        message: str,
        name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.name = name or ""
        self.data = data or {}
        super().__init__(f"{self.name or code}: {message}")


Transport = Callable[[Dict[str, Any], str, float], Dict[str, Any]]


def http_transport(payload: Dict[str, Any], base_url: str, timeout: float) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise ConnectionError(f"无法连接到 {base_url} 上的 BalatroBot：{exc}") from exc
    return json.loads(response_body)


@dataclass
class BalatroBotClient:
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 10.0
    transport: Optional[Transport] = None

    def __post_init__(self) -> None:
        self._next_id = 1
        if self.transport is None:
            self.transport = http_transport

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": dict(params or {}),
            "id": self._next_id,
        }
        self._next_id += 1
        assert self.transport is not None
        response = self.transport(payload, self.base_url, self.timeout)
        error = response.get("error")
        if error:
            data = error.get("data") if isinstance(error.get("data"), dict) else {}
            raise BalatroBotError(
                int(error.get("code", -32000)),
                str(error.get("message", "BalatroBot 错误")),
                str(data.get("name", "")) if data else None,
                data,
            )
        return response.get("result")

    def execute(self, action: ActionProposal) -> Any:
        return self.call(action.method, action.params)

    def gamestate(self) -> Any:
        return self.call("gamestate")

    def health(self) -> Any:
        return self.call("health")

    def start(self, deck: str = "RED", stake: str = "WHITE", seed: Optional[str] = None) -> Any:
        params: Dict[str, Any] = {"deck": deck, "stake": stake}
        if seed:
            params["seed"] = seed
        return self.call("start", params)
