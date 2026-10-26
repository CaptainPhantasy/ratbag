"""Plain-language setup state and deterministic, inspectable model assignments."""
from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

from .providers import ProviderRegistry, account_id
from .store import utc_now


CORE_ROLES = ("architect", "lead", "scout", "auditor")
ROLE_LABELS = {"architect": "Architect", "lead": "Builder", "scout": "Search workers", "auditor": "Auditor"}
ROLE_REASONS = {
    "architect": "GLM 5.3 reviews the plan and final changes at maximum reasoning on the locked Coding endpoint.",
    "lead": "DeepSeek Flash builds and repairs the changes with high reasoning.",
    "scout": "MiniMax M3.1 Flash handles both source-search jobs with low reasoning.",
    "auditor": "GLM 5.3 Flash reviews test evidence with high reasoning on the locked Coding endpoint.",
}


class WorkbenchSetup:
    def __init__(self, data_dir: Path, registry: ProviderRegistry):
        self.registry = registry
        self.path = Path(data_dir).resolve() / "setup.json"
        current = registry.public_configs()
        recommended = registry.recommended_configs()
        default_mode = "smart" if all(all(current[role][key] == value for key, value in config.items())
                                       for role, config in recommended.items()) else "manual"
        self.saved = {"completed": False, "completed_at": None, "routing_mode": default_mode}
        if self.path.is_file():
            if self.path.stat().st_size > 8192:
                raise ValueError("Saved setup is too large. Retain setup.json and review it before restarting.")
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if (not isinstance(value, dict) or set(value) != set(self.saved) or
                        not isinstance(value["completed"], bool) or value["routing_mode"] not in {"smart", "manual"} or
                        value["completed_at"] is not None and not isinstance(value["completed_at"], str)):
                    raise ValueError
                self.saved = value
            except (OSError, ValueError, TypeError):
                raise ValueError("Saved setup is invalid. Retain setup.json and review it before restarting.") from None

    def save(self, **values):
        updated = {**self.saved, **values}
        temporary = self.path.with_name("setup." + uuid.uuid4().hex + ".pending")
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(updated, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        self.saved = updated

    def routing(self, mode: str | None = None) -> dict:
        mode = mode or self.saved["routing_mode"]
        if mode not in {"smart", "manual"}:
            raise ValueError("Choose Smart or Manual routing.")
        public = self.registry.public_configs()
        configs = self.registry.recommended_configs() if mode == "smart" else {
            role: self.registry.get_config(role) for role in CORE_ROLES}
        assignments, missing = [], []
        for role in CORE_ROLES:
            config = configs[role]
            key_present = self.registry.key_available_for(config, role)
            if not config["enabled"] or not key_present:
                missing.append(role)
            check = public[role].get("last_check")
            same = all(public[role][field] == value for field, value in config.items())
            assignments.append({"role": role, "label": ROLE_LABELS[role], "model_id": config["model_id"],
                                "provider": account_id(config) or "custom", "effort": config["effort"],
                                "enabled": config["enabled"], "key_present": key_present,
                                "reason": ROLE_REASONS[role] if mode == "smart" else "Uses the model and settings you selected for this role.",
                                "check": check if same else None})
        failures = [item["role"] for item in assignments if item["check"] and not item["check"]["ok"]]
        return {"mode": mode, "ready": not missing and not failures, "assignments": assignments,
                "missing_roles": missing, "failed_roles": failures,
                "explanation": "Smart assigns the bundled models to their intended jobs using your accounts. It makes no model request and never switches providers after an error."
                if mode == "smart" else "Manual keeps your chosen model settings for each job. It makes no model request."}

    def apply_routing(self, mode: str) -> dict:
        self.routing(mode)  # Validate before saving or changing models.
        if mode == "smart":
            self.registry.configure_many(self.registry.recommended_configs())
        self.save(routing_mode=mode)
        return self.routing(mode)

    def status(self, *, project_count: int = 0, can_change_settings: bool = True) -> dict:
        configs = self.registry.public_configs()
        missing = [role for role in CORE_ROLES if not configs[role]["enabled"] or not configs[role]["key_present"]]
        failed = [role for role in CORE_ROLES if configs[role]["last_check"] and not configs[role]["last_check"]["ok"]]
        accounts = []
        for account, label in (("glm", "GLM Coding"), ("deepseek", "DeepSeek"), ("minimax", "MiniMax"), ("router", "Optional router")):
            roles = [role for role, cfg in configs.items() if account_id(cfg) == account]
            enabled = [role for role in roles if configs[role]["enabled"]]
            key_present = bool(roles) and all(configs[role]["key_present"] for role in roles)
            checked = bool(enabled) and all(configs[role]["last_check"] for role in enabled)
            passing = checked and all(configs[role]["last_check"]["ok"] for role in enabled)
            has_error = any(configs[role]["last_check"] and not configs[role]["last_check"]["ok"] for role in enabled)
            status = "disabled" if not enabled else "missing" if not key_present else "error" if has_error else "ready" if passing else "unchecked"
            messages = {"disabled": "Optional account is off." if account == "router" else "No enabled roles use this account.",
                        "missing": "Add this account key to connect its models.", "error": "A connection check failed. Review the account and check again.",
                        "ready": "Every enabled model for this account passed its connection check.",
                        "unchecked": "Key supplied. Use Check connections to verify access."}
            accounts.append({"id": account, "label": label, "roles": roles, "optional": account == "router",
                             "key_present": key_present, "checked": checked, "status": status, "message": messages[status]})
        verified = all(configs[role]["last_check"] and configs[role]["last_check"]["ok"] for role in CORE_ROLES)
        return {**self.saved, "ready": not missing and not failed, "verified": bool(verified), "accounts": accounts,
                "missing_roles": missing, "failed_roles": failed, "project_count": project_count,
                "can_change_settings": can_change_settings,
                "message": "Models are ready. Choose a project and describe the change." if not missing and not failed else
                "Finish the model settings shown below before starting a task."}

    def complete(self):
        status = self.status()
        if not status["ready"]:
            roles = status["missing_roles"] + status["failed_roles"]
            raise ValueError("Finish these model connections first: " + ", ".join(ROLE_LABELS[role] for role in roles) + ".")
        self.save(completed=True, completed_at=utc_now())
