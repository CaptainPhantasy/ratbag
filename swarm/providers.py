"""Provider settings and bounded text completions, using only the standard library.

Keys stay in process memory or the environment. The settings file contains only
the explicitly allowed public fields. Provider errors deliberately omit response
bodies, request bodies, URLs supplied by a server, and authorization headers.
"""

from __future__ import annotations

import asyncio
import copy
import errno
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ZAI_CODING_BASE = "https://api.z.ai/api/coding/paas/v4"
DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 2 * 1024 * 1024
_CONFIG_FIELDS = frozenset(
    {"model_id", "protocol", "base_url", "api_key_env", "effort", "max_tokens", "timeout_seconds", "enabled"}
)
_MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/~+\[\]-]{0,199}\Z")
_ENV_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})


class ProviderError(RuntimeError):
    """A safe, owner-visible provider failure. Never contains raw provider text."""

    def __init__(self, message: str, *, code: str = "provider_error", http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class ConfigurationError(ProviderError):
    """A configuration problem detected before making a provider request."""


@dataclass(frozen=True)
class LLMReply:
    text: str
    usage: dict[str, Any]
    elapsed_ms: float
    model: str


def _defaults() -> dict[str, dict[str, Any]]:
    entries = {
        "architect": ("glm-5.3", ZAI_CODING_BASE, "GLM_API_KEY", "max", 8192),
        "lead": ("deepseek-flash", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "high", 16384),
        "scout": ("MiniMax-M3.1-Flash", "https://api.minimax.io/v1", "MINIMAX_API_KEY", "low", 4096),
        "auditor": ("glm-5.3-flash", ZAI_CODING_BASE, "GLM_API_KEY", "high", 4096),
        "router": ("z-ai/glm-5.3-flash", "https://openrouter.ai/api/v1", "ROUTER_API_KEY", "low", 1024),
    }
    return {
        role: {
            "model_id": model,
            "protocol": "openai",
            "base_url": base,
            "api_key_env": env,
            "effort": effort,
            "max_tokens": tokens,
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "enabled": role != "router",
        }
        for role, (model, base, env, effort, tokens) in entries.items()
    }


def model_catalog() -> dict[str, Any]:
    """The bundled, documented model choices; this is not a live availability claim."""
    names = {"architect": "GLM 5.3", "lead": "DeepSeek Flash", "scout": "MiniMax M3.1 Flash",
             "auditor": "GLM 5.3 Flash", "router": "GLM 5.3 Flash · OpenRouter"}
    return {"models": [{"id": role, "label": names[role], "model_id": cfg["model_id"],
                         "provider": _family(cfg), "base_url": cfg["base_url"], "protocol": cfg["protocol"],
                         "roles": [role], "efforts": ["low", "high", "max"] if role in {"architect", "auditor"}
                         else ["low", "medium", "high", "xhigh", "max"], "effort": cfg["effort"],
                         "max_tokens": cfg["max_tokens"], "api_key_env": cfg["api_key_env"]}
                        for role, cfg in _defaults().items()],
            "custom_allowed": True, "source": "Bundled provider models; use Check connection to verify access."}


def account_id(config: dict[str, Any]) -> str | None:
    """Only a known provider host can receive a key entered for that provider."""
    host = urllib.parse.urlsplit(config["base_url"]).hostname or ""
    return {"api.z.ai": "glm", "api.deepseek.com": "deepseek", "api.minimax.io": "minimax",
            "openrouter.ai": "router"}.get(host)


def normalize_base_url(value: str, protocol: str) -> str:
    """Validate a base (or complete endpoint) without silently changing hosts."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ConfigurationError("Enter a valid provider base URL.")
    if any(ord(char) <= 32 or ord(char) == 127 for char in value):
        raise ConfigurationError("The provider URL cannot contain spaces or control characters.")
    try:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ConfigurationError("The provider URL is malformed.") from None
    if parsed.scheme not in {"https", "http"} or not host:
        raise ConfigurationError("Use an HTTPS provider URL, or HTTP for a loopback service.")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ConfigurationError("Keep credentials, query parameters, and fragments out of the provider URL.")
    if parsed.scheme == "http":
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host.lower() == "localhost"
        if not local:
            raise ConfigurationError("HTTP is allowed only for a local loopback model or test service.")
    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError("The provider URL has an invalid port.")
    path = parsed.path.rstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9/_.~-]*", path) or any(p in {".", ".."} for p in path.split("/")):
        raise ConfigurationError("The provider URL has an unsupported path.")
    if protocol == "openai" and path.endswith("/messages"):
        raise ConfigurationError("This is an Anthropic endpoint. Select its matching protocol.")
    if protocol == "anthropic" and path.endswith("/chat/completions"):
        raise ConfigurationError("This is an OpenAI endpoint. Select its matching protocol.")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def endpoint_url(config: dict[str, Any]) -> str:
    base = normalize_base_url(config["base_url"], config["protocol"])
    if config["protocol"] == "openai":
        return base if base.endswith("/chat/completions") else base + "/chat/completions"
    if config["protocol"] == "anthropic":
        if base.endswith("/messages"):
            return base
        return base + ("/messages" if base.endswith("/v1") else "/v1/messages")
    raise ConfigurationError("Choose the openai or anthropic protocol.")


def _family(config: dict[str, Any]) -> str:
    host = urllib.parse.urlsplit(config["base_url"]).hostname or ""
    model = config["model_id"].lower()
    if host == "openrouter.ai" or host.endswith(".openrouter.ai"):
        return "openrouter"
    if model.startswith("glm-") or host in {"api.z.ai", "open.bigmodel.cn"}:
        return "glm"
    if model.startswith("deepseek-") or host == "api.deepseek.com":
        return "deepseek"
    if model.startswith("minimax-") or host in {"api.minimax.io", "api.minimax.chat"}:
        return "minimax"
    return "custom"


def _native_glm(config: dict[str, Any]) -> bool:
    host = urllib.parse.urlsplit(config["base_url"]).hostname or ""
    return config["model_id"].lower().startswith("glm-") or host in {"api.z.ai", "open.bigmodel.cn"}


def _validate_config(config: dict[str, Any]) -> dict[str, Any]:
    if set(config) != _CONFIG_FIELDS:
        raise ConfigurationError("Provider settings contain unsupported fields.")
    model = config["model_id"]
    if not isinstance(model, str) or not _MODEL_RE.fullmatch(model) or re.match(r"(?i)sk[-_]|[a-f0-9]{32}\.[A-Za-z0-9_-]{8,}", model):
        raise ConfigurationError("Enter a model ID using letters, numbers, and provider model punctuation.")
    if not isinstance(config["protocol"], str) or config["protocol"] not in {"openai", "anthropic"}:
        raise ConfigurationError("Choose the openai or anthropic protocol.")
    config["base_url"] = normalize_base_url(config["base_url"], config["protocol"])
    env = config["api_key_env"]
    if not isinstance(env, str) or not _ENV_RE.fullmatch(env):
        raise ConfigurationError("Enter an environment variable name, not an API key.")
    if not isinstance(config["effort"], str) or config["effort"] not in _EFFORTS:
        raise ConfigurationError("Choose low, medium, high, xhigh, or max reasoning effort.")
    if isinstance(config["max_tokens"], bool) or not isinstance(config["max_tokens"], int) or not 64 <= config["max_tokens"] <= 131072:
        raise ConfigurationError("The maximum output must be an integer between 64 and 131072 tokens.")
    timeout = config["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 1 <= timeout <= 600:
        raise ConfigurationError("The provider timeout must be between 1 and 600 seconds.")
    if not isinstance(config["enabled"], bool):
        raise ConfigurationError("The provider enabled setting must be true or false.")
    if _native_glm(config):
        if config["base_url"] != ZAI_CODING_BASE or config["protocol"] != "openai":
            raise ConfigurationError("Native GLM is locked to the USA Coding endpoint and OpenAI protocol: " + ZAI_CODING_BASE)
        if config["effort"] not in {"low", "high", "max"}:
            raise ConfigurationError("Native GLM supports low, high, or max reasoning effort.")
    return config


def _validate_key(key: str) -> str:
    if not isinstance(key, str):
        raise ConfigurationError("The session API key must be text.")
    value = key.strip()
    if len(value) > 16384 or any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise ConfigurationError("The session API key has invalid characters or length.")
    if value.lower() in {"sk-placeholder-key", "your-api-key", "your-glm-key", "your-deepseek-key", "your-minimax-key"}:
        raise ConfigurationError("Replace the example API key with your own session key.")
    return value


class ProviderRegistry:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.data_dir / "providers.json"
        self._lock = threading.RLock()
        self._configs = _defaults()
        self._keys: dict[str, str] = {}
        self._account_keys: dict[str, str] = {}
        self._last_checks: dict[str, dict[str, Any]] = {}
        if self._path.exists():
            try:
                if self._path.stat().st_size > 65536:
                    raise ValueError
                saved = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(saved, dict) or set(saved) - set(self._configs):
                    raise ValueError
                for role, fields in saved.items():
                    if not isinstance(fields, dict) or set(fields) - _CONFIG_FIELDS:
                        raise ValueError
                    self._configs[role] = _validate_config({**self._configs[role], **fields})
            except (OSError, ValueError, TypeError, ProviderError):
                raise ConfigurationError("Saved provider settings are invalid. Review providers.json; no provider request was made.") from None

    def _role(self, role: str) -> None:
        if not isinstance(role, str) or role not in self._configs:
            raise ConfigurationError("Unknown provider role.")

    def _key_source(self, role: str) -> tuple[str, str]:
        if role in self._keys:
            return self._keys[role], "session"
        account = account_id(self._configs[role])
        if account in self._account_keys:
            return self._account_keys[account], "session"
        value = os.environ.get(self._configs[role]["api_key_env"], "")
        try:
            value = _validate_key(value)
        except ConfigurationError:
            return "", "missing"
        return (value, "environment") if value else ("", "missing")

    def _public(self, role: str) -> dict[str, Any]:
        key, source = self._key_source(role)
        return {
            **copy.deepcopy(self._configs[role]),
            "role": role,
            "provider": _family(self._configs[role]),
            "optional": role == "router",
            "endpoint_locked": _native_glm(self._configs[role]),
            "key_present": bool(key),
            "key_source": source,
            "last_check": copy.deepcopy(self._last_checks.get(role)),
        }

    def public_configs(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {role: self._public(role) for role in self._configs}

    def get_config(self, role: str) -> dict[str, Any]:
        with self._lock:
            self._role(role)
            return copy.deepcopy(self._configs[role])

    def configure(self, role: str, values: dict[str, Any]) -> dict[str, Any]:
        return self.configure_many({role: values})[role]

    def update(self, role: str, values: dict[str, Any], key: str | None = None) -> dict[str, Any]:
        with self._lock:
            validated_key = _validate_key(key) if key is not None else None
            self.configure(role, values)
            if validated_key is not None:
                self.set_key(role, validated_key)
            return self._public(role)

    def configure_many(self, entries: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Validate every role before saving a preset, so a bad role cannot half-apply."""
        with self._lock:
            if not isinstance(entries, dict):
                raise ConfigurationError("Expected model settings for each role.")
            all_configs = copy.deepcopy(self._configs)
            for role, values in entries.items():
                self._role(role)
                if not isinstance(values, dict) or set(values) - _CONFIG_FIELDS:
                    raise ConfigurationError("Only public provider settings can be saved; set session keys separately.")
                all_configs[role] = _validate_config({**self._configs[role], **values})
            serialized = json.dumps(all_configs, allow_nan=False)
            if self.redact(serialized) != serialized:
                raise ConfigurationError("Public provider settings cannot contain a configured API key.")
            previous = self._configs
            self._save(all_configs)
            self._configs = all_configs
            for role in entries:
                if any(previous[role][field] != all_configs[role][field] for field in ("base_url", "protocol", "api_key_env")):
                    self._keys.pop(role, None)
                if previous[role] != all_configs[role]:
                    self._last_checks.pop(role, None)
            return self.public_configs()

    def recommended_configs(self) -> dict[str, dict[str, Any]]:
        return {role: cfg for role, cfg in _defaults().items() if role != "router"}

    def key_available_for(self, config: dict[str, Any], role: str) -> bool:
        """Preview whether a configuration can use a known account without exposing it."""
        with self._lock:
            account = account_id(config)
            if account in self._account_keys:
                return True
            current = self._configs[role]
            if all(current[field] == config[field] for field in ("base_url", "protocol", "api_key_env")):
                return bool(self._key_source(role)[0])
            try:
                return bool(_validate_key(os.environ.get(config["api_key_env"], "")))
            except ConfigurationError:
                return False

    def set_account_keys(self, entries: dict[str, str]) -> None:
        with self._lock:
            if not isinstance(entries, dict) or set(entries) - {"glm", "deepseek", "minimax", "router"}:
                raise ConfigurationError("Choose GLM, DeepSeek, MiniMax, or Router account fields.")
            # Empty guided fields mean leave the current account alone; per-role
            # Advanced settings retain their explicit clear-key operation.
            values = {account: _validate_key(key) for account, key in entries.items()}
            for account, key in values.items():
                if not key:
                    continue
                self._account_keys[account] = key
                for role, config in self._configs.items():
                    if account_id(config) == account:
                        self._keys.pop(role, None)
                        self._last_checks.pop(role, None)

    def _save(self, values: dict[str, Any]) -> None:
        pending = self.data_dir / ("providers." + uuid.uuid4().hex + ".pending")
        try:
            fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(values, handle, indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(pending, self._path)
        except OSError:
            raise ConfigurationError("Could not save provider settings; the previous settings remain active.") from None

    def set_key(self, role: str, key: str) -> None:
        with self._lock:
            self._role(role)
            value = _validate_key(key)
            if value:
                self._keys[role] = value
            else:
                self._keys.pop(role, None)
            self._last_checks.pop(role, None)

    def resolve_key(self, role: str) -> str:
        with self._lock:
            self._role(role)
            key, _ = self._key_source(role)
            if not key:
                raise ConfigurationError("Add a session API key or set " + self._configs[role]["api_key_env"] + " for " + role + ".")
            return key

    def request_settings(self, role: str) -> tuple[dict[str, Any], str]:
        """Take one consistent settings/key snapshot for a request."""
        with self._lock:
            return self.get_config(role), self.resolve_key(role)

    def redact(self, text: str) -> str:
        with self._lock:
            secrets = ({key for role in self._configs for key, _ in [self._key_source(role)] if key}
                       | set(self._account_keys.values()) | set(self._keys.values())) - {""}
        for secret in sorted(secrets, key=len, reverse=True):
            text = text.replace(secret, "[redacted]")
        return text

    def record_check(self, role: str, ok: bool, model: str | None = None, elapsed_ms: float | None = None, message: str | None = None) -> None:
        """Record only an explicit connection check, separately from key presence."""
        with self._lock:
            self._role(role)
            safe_model = model if isinstance(model, str) and _MODEL_RE.fullmatch(model) else self._configs[role]["model_id"]
            safe_time = elapsed_ms if isinstance(elapsed_ms, (int, float)) and not isinstance(elapsed_ms, bool) and math.isfinite(elapsed_ms) and elapsed_ms >= 0 else None
            self._last_checks[role] = {
                "ok": bool(ok),
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "model": self.redact(safe_model),
                "elapsed_ms": safe_time,
                "message": "Connection verified." if ok else "Connection check failed. Review the supplied settings and key.",
            }


def _build_payload(config: dict[str, Any], system: str, prompt: str) -> dict[str, Any]:
    family = _family(config)
    effort = config["effort"]
    if family == "deepseek":
        effort = {"medium": "high", "xhigh": "high"}.get(effort, effort)
    base: dict[str, Any] = {"model": config["model_id"], "max_tokens": config["max_tokens"], "stream": False}
    if config["protocol"] == "openai":
        base["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        if family == "openrouter":
            base["reasoning"] = {"effort": effort, "exclude": True}
        else:
            base["reasoning_effort"] = effort
        if family in {"glm", "deepseek"}:
            base["thinking"] = {"type": "enabled"}
    else:
        base.update(system=system, messages=[{"role": "user", "content": prompt}], output_config={"effort": effort})
        if family in {"minimax", "custom"}:
            base["thinking"] = {"type": "adaptive"}
        elif family in {"glm", "deepseek"}:
            base["thinking"] = {"type": "enabled"}
    return base


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("The provider returned a redirect. Update the configured endpoint explicitly; the key was not forwarded.")


def _make_opener():
    # Keep the runtime's managed outbound route and NO_PROXY exclusions. A direct
    # connection can fail even though a configured proxy can reach the provider.
    # SSL's normal trusted-certificate settings are retained as well.
    return urllib.request.build_opener(urllib.request.ProxyHandler(), _NoRedirect())


def _network_error(reason: Any) -> ProviderError:
    """Classify transport failures without exposing addresses or proxy details."""
    if isinstance(reason, socket.gaierror):
        return ProviderError(
            "The provider connection could not resolve a network address. Review DNS and the configured proxy; no automatic retry was made.",
            code="dns_error",
        )
    if isinstance(reason, ssl.SSLCertVerificationError):
        return ProviderError(
            "The provider certificate could not be verified. Review the trusted certificates and configured proxy; no automatic retry was made.",
            code="tls_certificate_error",
        )
    if isinstance(reason, ssl.SSLError):
        return ProviderError(
            "The secure provider connection failed during TLS negotiation. Review the network and proxy configuration; no automatic retry was made.",
            code="tls_error",
        )
    if isinstance(reason, (TimeoutError, socket.timeout)) or getattr(reason, "errno", None) == errno.ETIMEDOUT:
        return ProviderError("The provider request timed out. No automatic retry was made.", code="timeout")
    if isinstance(reason, str) and "Tunnel connection failed:" in reason:
        if "407" in reason:
            return ProviderError(
                "The configured network proxy requires authentication. Review its configuration; no automatic retry was made.",
                code="proxy_auth_error",
            )
        return ProviderError(
            "The configured network proxy could not open the provider connection. Review proxy access; no automatic retry was made.",
            code="proxy_error",
        )
    return ProviderError(
        "The provider connection could not be established. Review the endpoint, network, and configured proxy; no automatic retry was made.",
        code="connect_error",
    )


def _usage(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    allowed = {
        "prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens",
    }
    result = {key: value for key, value in raw.items() if key in allowed and isinstance(value, int) and not isinstance(value, bool) and value >= 0}
    for field in ("prompt_tokens_details", "completion_tokens_details", "input_tokens_details", "output_tokens_details"):
        details = raw.get(field)
        if isinstance(details, dict):
            clean = {k: v for k, v in details.items() if k in {"cached_tokens", "reasoning_tokens", "audio_tokens", "accepted_prediction_tokens", "rejected_prediction_tokens"} and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
            if clean:
                result[field] = clean
    return result


def _final_text(data: dict[str, Any], protocol: str) -> str:
    if data.get("error"):
        raise ProviderError("The provider rejected the completion. Review its model access and request settings.")
    if protocol == "openai":
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ProviderError("The provider returned an invalid completion format.")
        choice = choices[0]
        if choice.get("finish_reason") != "stop":
            if choice.get("finish_reason") == "length":
                raise ProviderError("The provider reached the output limit. Increase the output allowance or reduce the task size; this response was not accepted.")
            raise ProviderError("The provider did not return a completed text answer.")
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("tool_calls") or message.get("refusal"):
            raise ProviderError("The provider returned an unsupported tool request or declined the answer.")
        content = message.get("content")
    else:
        if data.get("stop_reason") not in {"end_turn", "stop_sequence"}:
            if data.get("stop_reason") == "max_tokens":
                raise ProviderError("The provider reached the output limit. Increase the output allowance or reduce the task size; this response was not accepted.")
            raise ProviderError("The provider did not return a completed text answer.")
        content = data.get("content")
    if isinstance(content, list):
        if any(isinstance(block, dict) and block.get("type") in {"tool_use", "server_tool_use"} for block in content):
            raise ProviderError("The provider requested a tool instead of returning the required text answer.")
        text = "\n".join(block["text"] for block in content if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str))
    elif isinstance(content, str):
        text = content
    else:
        raise ProviderError("The provider returned no usable text answer.")
    # Some compatible services still put a leading reasoning section in text.
    while re.match(r"\s*<(think|thinking)>", text, re.IGNORECASE):
        match = re.match(r"\s*<(think|thinking)>.*?</\1>\s*", text, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ProviderError("The provider returned reasoning without a final answer.")
        text = text[match.end():]
    if not text.strip():
        raise ProviderError("The provider returned an empty final answer.")
    return text


class LLMClient:
    def __init__(self, registry: ProviderRegistry, *, max_response_bytes: int = MAX_RESPONSE_BYTES):
        self.registry = registry
        if isinstance(max_response_bytes, bool) or not isinstance(max_response_bytes, int) or not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ConfigurationError("Invalid maximum provider response size.")
        self.max_response_bytes = max_response_bytes

    async def complete(self, role: str, system: str, prompt: str) -> LLMReply:
        config, key = self.registry.request_settings(role)
        if not config["enabled"]:
            raise ConfigurationError("Enable the optional provider connection before using it.")
        if not isinstance(system, str) or not isinstance(prompt, str) or not prompt.strip():
            raise ConfigurationError("Provide text instructions and a non-empty provider prompt.")
        body = json.dumps(_build_payload(config, system, prompt), ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise ConfigurationError("The provider request is too large. Reduce the source or evidence included.")
        started = time.perf_counter()
        try:
            data = await asyncio.wait_for(asyncio.to_thread(self._post, config, key, body), timeout=config["timeout_seconds"] + 1)
        except (TimeoutError, socket.timeout):
            raise _network_error(TimeoutError()) from None
        text = _final_text(data, config["protocol"])
        # Redact both the request snapshot key and any current session/env keys.
        text = self.registry.redact(text.replace(key, "[redacted]"))
        model = data.get("model")
        if not isinstance(model, str) or not _MODEL_RE.fullmatch(model):
            model = config["model_id"]
        model = self.registry.redact(model.replace(key, "[redacted]"))
        return LLMReply(text=text, usage=_usage(data.get("usage")), elapsed_ms=(time.perf_counter() - started) * 1000, model=model)

    def _post(self, config: dict[str, Any], key: str, body: bytes) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Swarm-Control/1.0"}
        if config["protocol"] == "anthropic":
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        else:
            headers["Authorization"] = "Bearer " + key
        request = urllib.request.Request(endpoint_url(config), data=body, headers=headers, method="POST")
        deadline = time.monotonic() + config["timeout_seconds"]
        try:
            with _make_opener().open(request, timeout=config["timeout_seconds"]) as response:
                length = response.headers.get("Content-Length")
                if length and (not length.isdigit() or int(length) > self.max_response_bytes):
                    raise ProviderError("The provider response exceeded the permitted size.")
                chunks: list[bytes] = []
                count = 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    # Bound every read by the remaining total deadline, including
                    # a server that continually drips a few bytes at a time.
                    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                    if sock is not None:
                        sock.settimeout(remaining)
                    chunk = response.read1(min(65536, self.max_response_bytes + 1 - count))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    count += len(chunk)
                    if count > self.max_response_bytes:
                        raise ProviderError("The provider response exceeded the permitted size.")
                raw = b"".join(chunks)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in {401, 403}:
                message = "The provider rejected the key or model access. Check the key, account, and selected endpoint."
            elif code == 429:
                message = "The provider reported a rate or quota limit. No automatic retry was made."
            elif code == 404:
                message = "The provider could not find the endpoint or model. Review the connection settings."
            elif code in {400, 422}:
                message = "The provider rejected the request settings. Check the model, protocol, effort, and output allowance."
            elif 300 <= code < 400:
                message = "The provider returned a redirect. Update the endpoint explicitly; the key was not forwarded."
            else:
                message = "The provider returned HTTP " + str(code) + ". No automatic retry was made."
            raise ProviderError(message, code="http_error", http_status=code) from None
        except urllib.error.URLError as exc:
            raise _network_error(exc.reason) from None
        except (TimeoutError, socket.timeout):
            raise _network_error(TimeoutError()) from None
        except OSError as exc:
            raise _network_error(exc) from None
        except http.client.HTTPException:
            raise ProviderError("The provider returned an incomplete HTTP response. No automatic retry was made.") from None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise ProviderError("The provider returned an invalid JSON response.") from None
        if not isinstance(data, dict):
            raise ProviderError("The provider returned an invalid response object.")
        return data

    async def close(self) -> None:
        """Requests close their own connections; kept for the engine lifecycle."""
