"""
Web Search Registry - Manages provider registration and discovery
"""

from typing import Dict, Optional, Type
from .base import WebSearchProvider


class WebSearchRegistry:
    """Registry for web search providers"""

    def __init__(self):
        self._providers: Dict[str, Type[WebSearchProvider]] = {}
        self._instances: Dict[str, WebSearchProvider] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default providers - done during import to avoid circular imports"""
        pass  # Will be populated after providers are defined

    def register(self, name: str, provider_class: Type[WebSearchProvider]):
        """Register a web search provider"""
        self._providers[name] = provider_class

    def get_provider(self, name: str, config: dict) -> Optional[WebSearchProvider]:
        """Get provider instance by name"""
        if name not in self._providers:
            return None

        # Create instance with config if not already cached
        cache_key = f"{name}:{hash(str(sorted(config.items())))}"
        if cache_key not in self._instances:
            provider_class = self._providers[name]

            # Validate config
            required_config = provider_class.get_required_config()
            missing_config = [key for key in required_config if key not in config]
            if missing_config:
                raise ValueError(f"Missing required config for {name}: {missing_config}")

            self._instances[cache_key] = provider_class(**config)

        return self._instances[cache_key]

    def list_providers(self) -> list:
        """List available provider names"""
        return list(self._providers.keys())

    def has_provider(self, name: str) -> bool:
        """Check if provider is registered"""
        return name in self._providers

# Global registry instance
registry = WebSearchRegistry()

def register_providers():
    """Register all available providers - call this after providers are imported"""
    global registry

    try:
        from .providers.bocha import BochaProvider
        registry.register(BochaProvider.name, BochaProvider)
    except ImportError:
        pass  # Provider not available

    # Add more providers here as they are implemented
    # from .providers.google import GoogleProvider
    # registry.register(GoogleProvider.name, GoogleProvider)

# Register providers on import
register_providers()