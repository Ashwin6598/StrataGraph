"""
Identity and Access Management (IAM) and Role-Based Access Control (RBAC) for CodeGraph.
Maintains individual roles, permissions, and responsibilities across the multi-agent system:
- Program Manager: Agile execution flow (Epics, Features, Stories)
- Product / Business: PRD requirements, scenarios, guardrails
- Developer: Codebase modifications, bug fix staging, and proposing architectural changes
- Architect: Architectural decisions (ADRs) authoring and approving developer proposals
- Admin: Unrestricted superuser access
"""

from typing import Dict, Any, List, Optional, Set
from enum import Enum


class Role(str, Enum):
    PROGRAM_MANAGER = "PROGRAM_MANAGER"
    PRODUCT_MANAGER = "PRODUCT_MANAGER"
    DEVELOPER = "DEVELOPER"
    ARCHITECT = "ARCHITECT"
    ADMIN = "ADMIN"


class Permission(str, Enum):
    MANAGE_AGILE_FLOW = "MANAGE_AGILE_FLOW"        # Create/manage Epics, Features, Stories
    UPDATE_PRD = "UPDATE_PRD"                      # Create/update PRDs, requirements, scenarios
    MODIFY_CODEBASE = "MODIFY_CODEBASE"            # Stage/commit code fixes and logic modifications
    PROPOSE_ARCHITECTURE = "PROPOSE_ARCHITECTURE"  # Propose architectural ADR changes (awaiting approval)
    AUTHOR_ARCHITECTURE = "AUTHOR_ARCHITECTURE"    # Directly author or approve architectural ADRs
    READ_GRAPH = "READ_GRAPH"                      # Query graph, metrics, and diagnostics


ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.PROGRAM_MANAGER: {
        Permission.MANAGE_AGILE_FLOW,
        Permission.READ_GRAPH,
    },
    Role.PRODUCT_MANAGER: {
        Permission.UPDATE_PRD,
        Permission.READ_GRAPH,
    },
    Role.DEVELOPER: {
        Permission.MODIFY_CODEBASE,
        Permission.PROPOSE_ARCHITECTURE,
        Permission.READ_GRAPH,
    },
    Role.ARCHITECT: {
        Permission.AUTHOR_ARCHITECTURE,
        Permission.PROPOSE_ARCHITECTURE,
        Permission.READ_GRAPH,
    },
    Role.ADMIN: {
        Permission.MANAGE_AGILE_FLOW,
        Permission.UPDATE_PRD,
        Permission.MODIFY_CODEBASE,
        Permission.PROPOSE_ARCHITECTURE,
        Permission.AUTHOR_ARCHITECTURE,
        Permission.READ_GRAPH,
    },
}


class IAMManager:
    """Manages users, roles, and permission enforcement."""

    def __init__(self):
        # Default user identity registry
        self._users: Dict[str, Dict[str, Any]] = {
            "tpm-lead@payflow.internal": {
                "name": "Marcus Vance",
                "role": Role.PROGRAM_MANAGER,
                "title": "Lead Technical Program Manager"
            },
            "product-lead@payflow.internal": {
                "name": "Sarah Jenkins",
                "role": Role.PRODUCT_MANAGER,
                "title": "Principal Product Manager"
            },
            "payment-tech-lead@payflow.internal": {
                "name": "Alice Chen",
                "role": Role.DEVELOPER,
                "title": "Lead Software Engineer"
            },
            "developer@payflow.internal": {
                "name": "Bob Martinez",
                "role": Role.DEVELOPER,
                "title": "Senior Software Engineer"
            },
            "architect-lead@payflow.internal": {
                "name": "Alex Chen",
                "role": Role.ARCHITECT,
                "title": "Chief Systems Architect"
            },
            "admin@payflow.internal": {
                "name": "System Admin",
                "role": Role.ADMIN,
                "title": "Platform Administrator"
            }
        }

    def register_user(self, email: str, role: str, name: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Registers or updates a user identity in the IAM registry."""
        norm_role = Role(role.upper())
        user_record = {
            "name": name or email.split("@")[0].replace(".", " ").title(),
            "role": norm_role,
            "title": title or norm_role.value.replace("_", " ").title()
        }
        self._users[email.lower()] = user_record
        return {"email": email.lower(), **user_record}

    def get_user(self, email_or_role: str) -> Optional[Dict[str, Any]]:
        """Resolves user details by email or by direct role string."""
        clean = (email_or_role or "").strip().lower()
        if clean in self._users:
            return {"email": clean, **self._users[clean]}
        
        # Check if caller passed a raw role name (e.g. "PROGRAM_MANAGER")
        upper_role = clean.upper()
        for r in Role:
            if r.value == upper_role:
                return {
                    "email": f"default-{clean}@payflow.internal",
                    "name": f"Default {upper_role.replace('_', ' ').title()}",
                    "role": r,
                    "title": upper_role.replace('_', ' ').title()
                }
        return None

    def resolve_role(self, actor: Optional[str]) -> Role:
        """Resolves the Role enum for a given actor email, role name, or defaults."""
        if not actor:
            return Role.DEVELOPER  # Safe baseline default if unspecified
        user = self.get_user(actor)
        if user:
            return user["role"]
        try:
            return Role(actor.upper())
        except ValueError:
            pass

        # Intelligent heuristic fallback based on email naming
        clean = actor.lower()
        if "product" in clean or "pm" in clean.split("@")[0] or "prd" in clean:
            return Role.PRODUCT_MANAGER
        if "architect" in clean:
            return Role.ARCHITECT
        if "tpm" in clean or "program" in clean or "scrum" in clean:
            return Role.PROGRAM_MANAGER
        if "admin" in clean:
            return Role.ADMIN

        return Role.DEVELOPER

    def check_permission(self, actor: Optional[str], permission: Permission) -> bool:
        """Returns True if the actor possesses the specified permission."""
        role = self.resolve_role(actor)
        return permission in ROLE_PERMISSIONS.get(role, set())

    def enforce_permission(
        self,
        actor: Optional[str],
        permission: Permission,
        action_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validates actor permission for an action.
        Returns None if authorized.
        Returns a structured error dict if permission is denied.
        """
        role = self.resolve_role(actor)
        if permission not in ROLE_PERMISSIONS.get(role, set()):
            allowed_roles = [r.value for r, perms in ROLE_PERMISSIONS.items() if permission in perms]
            actor_label = actor or "Anonymous"
            return {
                "status": "PERMISSION_DENIED",
                "error_code": "IAM_ACCESS_DENIED",
                "actor": actor_label,
                "role": role.value,
                "required_permission": permission.value,
                "action": action_name,
                "message": (
                    f"Access Denied: Actor '{actor_label}' with role '{role.value}' lacks permission "
                    f"'{permission.value}' to perform '{action_name}'. "
                    f"Authorized roles: {', '.join(allowed_roles)}."
                )
            }
        return None

    def list_users(self) -> List[Dict[str, Any]]:
        """Lists all registered users and their assigned roles."""
        return [{"email": email, **details, "role": details["role"].value} for email, details in self._users.items()]

    def list_roles_and_permissions(self) -> Dict[str, List[str]]:
        """Returns all roles and their corresponding permissions."""
        return {
            role.value: [p.value for p in perms]
            for role, perms in ROLE_PERMISSIONS.items()
        }


# Global IAM singleton instance
iam = IAMManager()
