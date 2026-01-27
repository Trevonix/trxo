"""
Component mapper for import operations.

Maps item types to directory names and command names for data fetching.
"""

import re
from typing import Dict


class ComponentMapper:
    """Handles mapping between item types, directories, and command names"""
    
    # Component type to directory name mapping
    COMPONENT_MAP: Dict[str, str] = {
        # Direct mappings
        "journeys": "journeys",
        "scripts": "scripts",
        "themes": "themes",
        "services": "services",
        "policies": "policies",
        "oauth": "oauth",
        "saml": "saml",
        "agents_web": "agents_web",
        "agents_gateway": "agents_gateway",
        "agents_java": "agents_java",
        "authn": "authn",
        "email_templates": "email_templates",
        "endpoints": "endpoints",
        "esv_secrets": "esv",
        "esv_variables": "esv",
        "managed": "managed",
        "mappings": "mappings",
        "connectors": "connectors",
        "applications": "applications",
        "webhooks": "webhooks",
        "privileges": "privileges",
        "realms": "realms",
        
        # Descriptive name mappings (from get_item_type())
        "authentication settings": "authn",
        "Applications": "applications",
        "Journeys": "journeys",
        "Scripts": "scripts",
        "Themes": "themes",
        "themes (ui/themerealm)": "themes",
        "Services": "services",
        "Policies": "policies",
        "OAuth": "oauth",
        "OAuth2_Clients": "oauth",
        "SAML": "saml",
        "saml": "saml",
        "Web Agents": "agents_web",
        "Gateway Agents": "agents_gateway",
        "Java Agents": "agents_java",
        "IdentityGatewayAgent agents": "agents_gateway",
        "J2EEAgent agents": "agents_java",
        "WebAgent agents": "agents_web",
        "Email Templates": "email_templates",
        "email templates": "email_templates",
        "Endpoints": "endpoints",
        "custom endpoints": "endpoints",
        "Environment_Secrets": "esv_secrets",
        "Environment_Variables": "esv_variables",
        "Managed Objects": "managed",
        "managed_objects": "managed",
        "Mappings": "mappings",
        "sync mappings": "mappings",
        "Connectors": "connectors",
        "IDM connectors": "connectors",
        "Webhooks": "webhooks",
        "webhooks": "webhooks",
        "Privileges": "privileges",
        "Realms": "realms"
    }
    
    # Item type to command name mapping for data fetcher
    TYPE_TO_COMMAND: Dict[str, str] = {
        # Agent types
        "IdentityGatewayAgent agents": "agents_gateway",
        "J2EEAgent agents": "agents_java",
        "WebAgent agents": "agents_web",
        
        # Standard types
        "Applications": "applications",
        "authentication settings": "authn",
        "IDM connectors": "connectors",
        "email templates": "email",
        "custom endpoints": "endpoints",
        "Environment_Secrets": "esv_secrets",
        "Environment_Variables": "esv_variables",
        "journeys": "journeys",
        "managed_objects": "managed",
        "sync mappings": "mappings",
        "OAuth2_Clients": "oauth",
        "policies (alpha)": "policies",
        "policies": "policies",
        "Privileges": "privileges",
        "realms": "realms",
        "saml": "saml",
        "scripts": "scripts",
        "services": "services",
        "themes (ui/themerealm)": "themes",
        "themes": "themes",
        "webhooks (alpha)": "webhooks",
        "webhooks": "webhooks",
    }
    
    # Root-level components (not realm-specific)
    ROOT_LEVEL_COMPONENTS = [
        "custom endpoints", "email templates", "managed_objects", "sync mappings",
        "IDM connectors", "Privileges", "Applications", "Environment_Secrets",
        "Environment_Variables", "Realms"
    ]
    
    @staticmethod
    def get_component_directory(item_type: str) -> str:
        """
        Get the directory name for a given item type.
        
        Args:
            item_type: The item type to map
            
        Returns:
            Directory name for the component
        """
        component = ComponentMapper.COMPONENT_MAP.get(item_type, item_type)
        
        # Handle dynamic patterns like "policies (realm)"
        if component == item_type and "(" in item_type:
            base_type = item_type.split("(")[0].strip()
            component = ComponentMapper.COMPONENT_MAP.get(base_type, base_type)
        
        return component
    
    @staticmethod
    def get_command_name(item_type: str) -> str:
        """
        Get the command name for data fetcher based on item type.
        
        Args:
            item_type: The item type to map
            
        Returns:
            Command name for data fetcher
        """
        # Normalize item_type by removing any trailing parenthesized context
        base_type = re.sub(r"\s*\(.*\)$", "", item_type).strip()
        
        # Try normalized lookup first, then original, then fallback
        if base_type in ComponentMapper.TYPE_TO_COMMAND:
            return ComponentMapper.TYPE_TO_COMMAND[base_type]
        
        if item_type in ComponentMapper.TYPE_TO_COMMAND:
            return ComponentMapper.TYPE_TO_COMMAND[item_type]
        
        # Fallback: return a safe snake_case version of the base type
        return base_type.lower().replace(" ", "_")
    
    @staticmethod
    def is_root_level_component(item_type: str) -> bool:
        """
        Check if a component is root-level (not realm-specific).
        
        Args:
            item_type: The item type to check
            
        Returns:
            True if root-level component, False otherwise
        """
        return item_type in ComponentMapper.ROOT_LEVEL_COMPONENTS
