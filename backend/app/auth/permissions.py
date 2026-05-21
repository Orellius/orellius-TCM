"""Role-Based Access Control (RBAC) definitions.

Roles:
  - admin: full access (settings, channels, pipeline, user management)
  - editor: approve/reject messages, manage templates, start/stop pipeline
  - viewer: read-only dashboard, message feed, logs
"""

# Role hierarchy — higher roles inherit lower role permissions
ROLE_HIERARCHY = {
    "admin": 3,
    "editor": 2,
    "viewer": 1,
}

# Map endpoints to minimum required role
ENDPOINT_ROLES = {
    # Admin only
    "settings.update": "admin",
    "channels.add": "admin",
    "channels.remove": "admin",
    "users.manage": "admin",
    # Editor+
    "pipeline.start": "editor",
    "pipeline.stop": "editor",
    "review.approve": "editor",
    "review.reject": "editor",
    "review.archive": "editor",
    "templates.create": "editor",
    "templates.update": "editor",
    "templates.delete": "editor",
    # Viewer+ (read-only)
    "pipeline.status": "viewer",
    "messages.read": "viewer",
    "channels.list": "viewer",
    "settings.read": "viewer",
    "logs.read": "viewer",
}


def has_permission(user_role: str, required_role: str) -> bool:
    """Check if a user role has sufficient permission."""
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 999)
    return user_level >= required_level
