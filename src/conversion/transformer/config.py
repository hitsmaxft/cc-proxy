import logging
from typing import Dict, Any, List, Optional

from src.core.config import Config, config
from src.conversion.transformer.registry import transformer_registry

logger = logging.getLogger(__name__)


class TransformerConfig:
    """
    Configuration for transformers.

    This class manages transformer configuration from the main application config
    and provides methods to get transformers for specific providers and models.
    """

    config: Config
    transformer_configs: Dict[str, Dict[str, Any]]

    def __init__(self, config: Config):
        """
        Initialize transformer configuration.

        Args:
            config: The application config
        """
        self.config = config
        self.transformer_configs = self._load_transformer_configs()

    def _load_transformer_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Load transformer configurations from the application config.

        Returns:
            Dictionary of transformer configurations keyed by transformer name
        """
        # Get transformer configs from application config
        transformer_configs = getattr(self.config, "transformers", {})

        # If no transformer configs are defined, create default configs
        if not transformer_configs:
            transformer_configs = {}

        logger.info(f"Loaded transformer configurations: {transformer_configs}")
        return transformer_configs

    def get_transformers_for_model(self, provider: str, model: str) -> List[Any]:
        """
        Get transformers that should be applied to the given provider and model.

        Args:
            provider: The provider name
            model: The model name

        Returns:
            List of transformer instances that should be applied
        """
        return transformer_registry.get_transformers_for_model(
            provider, model, self.transformer_configs
        )

    def is_transformer_enabled(self, name: str) -> bool:
        """
        Check if a transformer is enabled.

        Args:
            name: The name of the transformer

        Returns:
            True if the transformer is enabled, False otherwise
        """
        if name not in self.transformer_configs:
            # Default to enabled for unknown transformers
            return True

        return self.transformer_configs.get(name, {}).get("enabled", True)

    def get_transformer_config(self, name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific transformer.

        Args:
            name: The name of the transformer

        Returns:
            Configuration for the transformer or an empty dict if not found
        """
        return self.transformer_configs.get(name, {})


# Global singleton instance
transformer_config = TransformerConfig(config)
