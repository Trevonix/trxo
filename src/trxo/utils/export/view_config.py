"""
View configuration for export commands.

This module defines default column configurations for different export commands
to provide sensible defaults for table display.
"""

from typing import Dict, List, Optional

# Default columns for each export command
DEFAULT_VIEW_COLUMNS: Dict[str, List[str]] = {
    "realms": ["_id", "name", "active", "parentPath"],
    "scripts": ["_id", "name", "description", "script", "language", "context"],
    "saml": ["_id", "entityId", "location", "entityConfig"],
    "journeys": ["_id", "name", "description", "enabled", "uiConfig"],
    "oauth": ["_id", "coreOAuth2ClientConfig", "advancedOAuth2ClientConfig"],
    "users": ["_id", "userName", "givenName", "sn", "mail"],
    "agents_gateway": ["_id", "secretLabelIdentifier", "igTokenIntrospection", "status"],
    "agents_java": [
       "_id",
       "ssoJ2EEAgentConfig",
       "amServicesJ2EEAgent",
       "applicationJ2EEAgentConfig",
       "globalJ2EEAgentConfig",
       "advancedJ2EEAgentConfig",
       ],
    "agents_web": [
        "_id",
        "miscWebAgentConfig",
        "advancedWebAgentConfig",
        "ssoWebAgentConfig",
        "amServicesWebAgent",
        "applicationWebAgentConfig",
        "globalWebAgentConfig",
    ],
    "authn": ["security", "core", "general", "trees"],
    "email_templates": ["_id", "subject", "from", "enabled"],
    "themes": ["_id", "isDefault", "fontFamily", "backgroundColor"],
    "services": ["_id", "name", "_type"],
    "endpoints": ["_id", "type", "source", "file"],
    "policies": ["_id", "name", "active", "description"],
    "managed": ["name", "schema.title", "schema.icon"],
    "mappings": ["name", "displayName", "source", "target"],
    "connectors": ["_id", "enabled", "connectorRef.displayName", "connectorRef.connectorName"],
    "esv_variables": ["_id", "valueBase64", "description"],
    "esv_secrets": [
        "_id",
        "valueBase64",
        "description",
        "loaded",
        "activeVersion",
        "loadedVersion",
        ],
}

# Command-specific column descriptions for help text
COLUMN_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "realms": {
        "_id": "Realm identifier",
        "name": "Realm name",
        "active": "Whether realm is active",
        "parentPath": "Parent realm path",
        "aliases": "Realm aliases"
    },
    "scripts": {
        "_id": "Script identifier",
        "name": "Script name",
        "script": "Script content (truncated)",
        "language": "Programming language",
        "context": "Execution context"
    },
    "services": {
        "_id": "Service identifier",
        "name": "Service name",
        "_type": "Service type information"
    },
    "themes": {
        "_id": "Theme identifier",
        "isDefault": "Whether this is the default theme",
        "fontFamily": "Font family used",
        "backgroundColor": "Background color",
        "logoEnabled": "Whether logo is enabled"
    },
    "oauth": {
        "_id": "OAuth client identifier",
        "clientId": "OAuth client ID",
        "clientType": "Type of OAuth client",
        "status": "Client status"
    },
    "endpoints": {
        "_id": "Endpoint identifier",
        "type": "Endpoint type (e.g., text/javascript)",
        "source": "Source code or configuration",
        "file": "Associated file path"
    },
    "policies": {
        "_id": "Policy identifier",
        "name": "Policy name",
        "active": "Whether policy is active",
        "description": "Policy description"
    },
    "managed": {
        "name": "Managed object name",
        "schema.title": "Object title from schema",
        "schema.icon": "Icon class from schema"
    },
    "mappings": {
        "name": "Mapping name/identifier",
        "displayName": "Human-readable display name",
        "source": "Source system/object",
        "target": "Target system/object"
    },
    "connectors": {
        "_id": "Connector identifier",
        "enabled": "Whether connector is enabled",
        "connectorRef.displayName": "Connector display name",
        "connectorRef.connectorName": "Connector class name"
    }
}


def get_default_columns(command_name: str) -> Optional[List[str]]:
    """Get default columns for a command"""
    return DEFAULT_VIEW_COLUMNS.get(command_name)


def get_column_description(command_name: str, column_name: str) -> str:
    """Get description for a specific column"""
    command_cols = COLUMN_DESCRIPTIONS.get(command_name, {})
    return command_cols.get(column_name, f"Column: {column_name}")


def get_available_columns_help(command_name: str) -> str:
    """Generate help text showing available columns for a command"""
    defaults = get_default_columns(command_name)
    if not defaults:
        return "Use --view to see available columns"

    descriptions = COLUMN_DESCRIPTIONS.get(command_name, {})
    help_lines = [f"Default columns for {command_name}:"]

    for col in defaults:
        desc = descriptions.get(col, "")
        if desc:
            help_lines.append(f"  • {col}: {desc}")
        else:
            help_lines.append(f"  • {col}")

    return "\n".join(help_lines)


def suggest_columns(command_name: str, view_columns: Optional[str]) -> Optional[str]:
    """Suggest default columns if none specified"""
    if view_columns:
        return view_columns

    defaults = get_default_columns(command_name)
    if defaults:
        return ",".join(defaults)

    return None
