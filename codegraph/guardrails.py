"""
Security Harness and Guardrails Engine for CodeGraph.
Protects the knowledge graph against:
1. Malicious Ingestion: Path traversal, Local File Inclusion (LFI), and sensitive file exfiltration (.env, .git, .ssh).
2. Prompt Injection & Poisoning: Detects adversarial injection patterns attempting to subvert agent reasoning.
3. Payload Denial-of-Service: Enforces strict file size limits and AST parsing ceilings.
4. Unauthorized Mutations: Enforces IAM role and permission checks across all ingestion endpoints.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from .config import settings
from .iam import iam, Permission


# Security constraints
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_DIRECTORY_FILES = 1000

BLOCKED_FILE_NAMES: Set[str] = {
    ".env",
    ".env.local",
    ".env.production",
    ".git",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
    "passwd",
    "shadow",
    "credentials",
    ".netrc",
}

BLOCKED_EXTENSIONS: Set[str] = {
    ".key",
    ".pem",
    ".pfx",
    ".p12",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
}

PROMPT_INJECTION_REGEXES: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer|admin|god|jailbreak)\s+mode", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(safety|security|prior)\s+guardrails", re.IGNORECASE),
    re.compile(r"bypass\s+all\s+(checks|safeguards|rules)", re.IGNORECASE),
    re.compile(r"<script[\s>]", re.IGNORECASE),
]


class IngestionGuardrailError(Exception):
    """Raised when an ingestion request violates security guardrails."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def validate_safe_path(target_path: str, allowed_base: Optional[Path] = None) -> Path:
    """
    Validates that target_path:
    1. Does not escape the allowed project root (prevents path traversal / LFI).
    2. Does not reference sensitive secrets (.env, credentials, SSH keys, certificates).
    3. Exists on disk and does not exceed file size limits.
    """
    base = (allowed_base or settings.base_dir).resolve()
    raw_path = Path(target_path)
    
    # Resolve absolute canonical path
    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (base / raw_path).resolve()

    # 1. Blocked Sensitive Filenames & Directories
    for part in resolved.parts:
        if part in BLOCKED_FILE_NAMES or part.startswith(".env"):
            raise IngestionGuardrailError(
                code="SENSITIVE_FILE_ACCESS_BLOCKED",
                message=f"Access Denied: Ingestion of sensitive configuration file '{part}' is strictly forbidden."
            )

    # 2. Blocked File Extensions
    if resolved.suffix.lower() in BLOCKED_EXTENSIONS:
        raise IngestionGuardrailError(
            code="UNSAFE_EXTENSION_BLOCKED",
            message=f"Access Denied: Binary or cryptographic key extension '{resolved.suffix}' cannot be ingested."
        )

    # 3. Directory Traversal / Workspace Boundary Check
    try:
        resolved.relative_to(base)
    except ValueError:
        # Check if it's within current working directory
        cwd = Path.cwd().resolve()
        try:
            resolved.relative_to(cwd)
        except ValueError:
            raise IngestionGuardrailError(
                code="PATH_TRAVERSAL_DETECTED",
                message=f"Access Denied: Path '{target_path}' escapes allowed workspace boundary."
            )

    # 4. File Size Limits (Anti-DoS)
    if resolved.is_file():
        file_size = resolved.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise IngestionGuardrailError(
                code="PAYLOAD_TOO_LARGE",
                message=f"Payload rejected: File size ({file_size} bytes) exceeds maximum allowable limit of {MAX_FILE_SIZE_BYTES} bytes."
            )

    return resolved


def scan_for_prompt_injection(content: str) -> List[str]:
    """
    Scans untrusted ingested text for adversarial prompt injection signatures.
    Returns a list of matched injection pattern names.
    """
    matched = []
    for pattern in PROMPT_INJECTION_REGEXES:
        if pattern.search(content):
            matched.append(pattern.pattern)
    return matched


def sanitize_untrusted_text(text: str, max_length: int = 50000) -> str:
    """
    Sanitizes untrusted content before storing in graph to neutralize prompt injections
    and enforce maximum text length ceilings.
    """
    if not text:
        return ""
    truncated = text[:max_length]
    # Neutralize script tags
    sanitized = re.sub(r"<\s*script[^>]*>(.*?)<\s*/\s*script\s*>", r"[REMOVED_SCRIPT: \1]", truncated, flags=re.IGNORECASE)
    # Neutralize injection trigger phrases by escaping
    for pattern in PROMPT_INJECTION_REGEXES:
        sanitized = pattern.sub(r"[FLAGGED_INJECTION_SUPPRESSED]", sanitized)
    return sanitized


def enforce_ingestion_harness(
    target_path: str,
    actor: Optional[str] = None,
    required_permission: Optional[Permission] = None,
    action_name: str = "ingest_data"
) -> Optional[Dict[str, Any]]:
    """
    Unified security harness for all ingestion operations:
    1. Enforces IAM Role and Permission.
    2. Validates path containment and blocks sensitive files.
    3. Enforces payload size limits.
    Returns None if safe; returns a structured error dict if blocked.
    """
    # 1. IAM Permission Gate
    if required_permission:
        denial = iam.enforce_permission(actor, required_permission, action_name)
        if denial:
            return denial

    # 2. Path Sandboxing & Sensitive File Defense
    try:
        validate_safe_path(target_path)
    except IngestionGuardrailError as e:
        return {
            "status": "GUARDRAIL_BLOCKED",
            "error_code": e.code,
            "target_path": target_path,
            "actor": actor or "Anonymous",
            "action": action_name,
            "message": e.message
        }
    except Exception as ex:
        return {
            "status": "GUARDRAIL_BLOCKED",
            "error_code": "SECURITY_VALIDATION_ERROR",
            "target_path": target_path,
            "message": str(ex)
        }

    return None
