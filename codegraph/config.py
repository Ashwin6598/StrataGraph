"""
Configuration management for CodeGraph.
Supports environment variables with sensible defaults for local development and cloud production.
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


class Settings(BaseModel):
    # FalkorDB Database Connection
    falkordb_host: str = Field(default_factory=lambda: os.getenv("FALKORDB_HOST", "localhost"))
    falkordb_port: int = Field(default_factory=lambda: int(os.getenv("FALKORDB_PORT", "6379")))
    falkordb_password: str = Field(default_factory=lambda: os.getenv("FALKORDB_PASSWORD", ""))
    falkordb_graph: str = Field(default_factory=lambda: os.getenv("FALKORDB_GRAPH", "codegraph_demo"))

    # Resilience: In-Memory / File Fallback for local offline demo
    auto_fallback: bool = Field(
        default_factory=lambda: os.getenv("FALKORDB_AUTO_FALLBACK", "true").lower() in ("true", "1", "yes")
    )
    persist_file: str = Field(default_factory=lambda: os.getenv("FALKORDB_PERSIST_FILE", "codegraph_local_store.json"))

    # MCP Server Transport: "stdio" or "http"
    mcp_transport: str = Field(default_factory=lambda: os.getenv("MCP_TRANSPORT", "stdio").lower())
    mcp_http_host: str = Field(default_factory=lambda: os.getenv("MCP_HTTP_HOST", "0.0.0.0"))
    mcp_http_port: int = Field(default_factory=lambda: int(os.getenv("MCP_HTTP_PORT", "8000")))
    mcp_auth_token: str = Field(default_factory=lambda: os.getenv("MCP_AUTH_TOKEN", ""))

    # Code Domain Ownership & Email Approval
    code_domain_owner: str = Field(default_factory=lambda: os.getenv("CODE_DOMAIN_OWNER", "payment-lead@payflow.internal"))
    codebase_owner: str = Field(default_factory=lambda: os.getenv("CODEBASE_OWNER", "payment-tech-lead@payflow.internal"))
    prd_owner: str = Field(default_factory=lambda: os.getenv("PRD_OWNER", "product-lead@payflow.internal"))
    smtp_host: str = Field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = Field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = Field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = Field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = Field(default_factory=lambda: os.getenv("SMTP_FROM", "codegraph-alerts@payflow.internal"))
    approval_base_url: str = Field(default_factory=lambda: os.getenv("APPROVAL_BASE_URL", "http://localhost:8000"))


    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)


settings = Settings()
