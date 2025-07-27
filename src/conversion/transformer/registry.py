import importlib
import logging
import pkgutil
from typing import Dict, List, Type, Optional

from src.conversion.transformer.base import AbstractTransformer

logger = logging.getLogger(__name__)


class TransformerRegistry:
    """
    Registry for transformer classes. Manages transformer registration and retrieval.

    The registry allows looking up transformers by name or querying for
    transformers that should apply to a given provider and model.
    """

    def __init__(self):
        self._transformers: Dict[str, Type[AbstractTransformer]] = {}

    def register(self, transformer_cls: Type[AbstractTransformer]) -> None:
        """
        Register a transformer class.

        Args:
            transformer_cls: The transformer class to register
        """
        if not issubclass(transformer_cls, AbstractTransformer):
            raise ValueError(
                f"{transformer_cls.__name__} is not a subclass of AbstractTransformer"
            )

        name = transformer_cls.name
        if name in self._transformers:
            logger.warning(
                f"Transformer with name '{name}' already registered. Overwriting."
            )

        self._transformers[name] = transformer_cls
        logger.debug(f"Registered transformer: {name}")

    def get_transformer(
        self, name: str, config: Optional[Dict] = None
    ) -> Optional[AbstractTransformer]:
        """
        Get a transformer instance by name.

        Args:
            name: The name of the transformer
            config: Optional configuration for the transformer

        Returns:
            An instance of the transformer or None if not found
        """
        transformer_cls = self._transformers.get(name)
        if not transformer_cls:
            logger.warning(f"No transformer found with name: {name}")
            return None

        return transformer_cls(config)

    def get_transformers_for_model(
        self, provider: str, model: str, configs: Optional[Dict[str, Dict]] = None
    ) -> List[AbstractTransformer]:
        """
        Get all transformers that should be applied to the given provider and model.

        Args:
            provider: The provider name
            model: The model name
            configs: Optional configurations for transformers keyed by transformer name

        Returns:
            List of transformer instances that should be applied
        """
        configs = configs or {}
        result = []

        for name, transformer_cls in self._transformers.items():
            # Create an instance to test if it should apply
            config = configs.get(name, {})
            transformer = transformer_cls(config)

            if transformer.should_apply_to(provider, model):
                logger.debug(
                    f"Adding transformer '{name}' for provider '{provider}' and model '{model}'"
                )
                result.append(transformer)
            else:
                logger.debug(
                    f"Skip transformer '{name}' for provider '{provider}' and model '{model}'"
                )

        return result

    def discover_and_register_transformers(
        self, package_name="src.conversion.transformer.transformers"
    ):
        """
        Discover and register all transformers in the given package.

        Args:
            package_name: The package to scan for transformers
        """
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.warning(f"Could not import package: {package_name}")
            return

        for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
            if is_pkg:
                # Recursively discover transformers in subpackages
                self.discover_and_register_transformers(f"{package_name}.{name}")
                continue

            # Import the module
            try:
                module = importlib.import_module(f"{package_name}.{name}")

                # Find all AbstractTransformer subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, AbstractTransformer)
                        and attr is not AbstractTransformer
                    ):
                        self.register(attr)

            except (ImportError, AttributeError) as e:
                logger.warning(f"Error importing module {name}: {e}")


# Global singleton instance
transformer_registry = TransformerRegistry()
