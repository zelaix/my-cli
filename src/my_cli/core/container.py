"""
Dependency injection container for My CLI.

This module provides a simple dependency injection system for managing
service instances and their dependencies throughout the application.
"""

import asyncio
from typing import Dict, Any, TypeVar, Type, Optional, Callable, List
import logging
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceScope(Enum):
    """Service lifetime scopes."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


@dataclass
class ServiceDescriptor:
    """Describes how a service should be created and managed."""
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable] = None
    instance: Any = None
    scope: ServiceScope = ServiceScope.SINGLETON
    dependencies: List[Type] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ServiceContainer:
    """Simple dependency injection container."""
    
    def __init__(self):
        """Initialize the service container."""
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._instances: Dict[Type, Any] = {}
        self._scoped_instances: Dict[str, Dict[Type, Any]] = {}
        self._current_scope: Optional[str] = None
        self._lock = asyncio.Lock()
    
    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        instance: Optional[T] = None
    ) -> 'ServiceContainer':
        """Register a service as singleton.
        
        Args:
            service_type: Service interface/type
            implementation_type: Concrete implementation type
            factory: Factory function to create instance
            instance: Pre-created instance
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type,
            implementation_type,
            factory,
            instance,
            ServiceScope.SINGLETON
        )
    
    def register_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None
    ) -> 'ServiceContainer':
        """Register a service as transient (new instance each time).
        
        Args:
            service_type: Service interface/type
            implementation_type: Concrete implementation type
            factory: Factory function to create instance
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type,
            implementation_type,
            factory,
            None,
            ServiceScope.TRANSIENT
        )
    
    def register_scoped(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None
    ) -> 'ServiceContainer':
        """Register a service as scoped (one instance per scope).
        
        Args:
            service_type: Service interface/type
            implementation_type: Concrete implementation type
            factory: Factory function to create instance
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type,
            implementation_type,
            factory,
            None,
            ServiceScope.SCOPED
        )
    
    def _register_service(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]],
        factory: Optional[Callable],
        instance: Optional[T],
        scope: ServiceScope
    ) -> 'ServiceContainer':
        """Internal method to register a service.
        
        Args:
            service_type: Service interface/type
            implementation_type: Concrete implementation type
            factory: Factory function
            instance: Pre-created instance
            scope: Service scope
            
        Returns:
            Self for method chaining
        """
        if instance is not None and scope != ServiceScope.SINGLETON:
            raise ValueError("Pre-created instances can only be registered as singletons")
        
        if implementation_type is None and factory is None and instance is None:
            implementation_type = service_type
        
        # Extract dependencies from constructor if implementation_type is provided
        dependencies = []
        if implementation_type:
            dependencies = self._extract_dependencies(implementation_type)
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            instance=instance,
            scope=scope,
            dependencies=dependencies
        )
        
        self._services[service_type] = descriptor
        
        # Store singleton instance immediately if provided
        if instance is not None:
            self._instances[service_type] = instance
        
        logger.debug(f"Registered service: {service_type.__name__} ({scope.value})")
        return self
    
    async def get_service(self, service_type: Type[T]) -> T:
        """Get a service instance.
        
        Args:
            service_type: Type of service to retrieve
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered
        """
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} is not registered")
        
        descriptor = self._services[service_type]
        
        async with self._lock:
            if descriptor.scope == ServiceScope.SINGLETON:
                return await self._get_singleton(service_type, descriptor)
            elif descriptor.scope == ServiceScope.SCOPED:
                return await self._get_scoped(service_type, descriptor)
            else:  # TRANSIENT
                return await self._create_instance(descriptor)
    
    async def _get_singleton(self, service_type: Type[T], descriptor: ServiceDescriptor) -> T:
        """Get or create singleton instance."""
        if service_type in self._instances:
            return self._instances[service_type]
        
        instance = await self._create_instance(descriptor)
        self._instances[service_type] = instance
        return instance
    
    async def _get_scoped(self, service_type: Type[T], descriptor: ServiceDescriptor) -> T:
        """Get or create scoped instance."""
        if self._current_scope is None:
            raise ValueError("No active scope for scoped service")
        
        if self._current_scope not in self._scoped_instances:
            self._scoped_instances[self._current_scope] = {}
        
        scope_instances = self._scoped_instances[self._current_scope]
        
        if service_type in scope_instances:
            return scope_instances[service_type]
        
        instance = await self._create_instance(descriptor)
        scope_instances[service_type] = instance
        return instance
    
    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a new instance of a service."""
        if descriptor.instance is not None:
            return descriptor.instance
        
        if descriptor.factory is not None:
            # Use factory function
            if asyncio.iscoroutinefunction(descriptor.factory):
                return await descriptor.factory()
            else:
                return descriptor.factory()
        
        if descriptor.implementation_type is not None:
            # Create instance using constructor
            # Resolve dependencies first
            resolved_dependencies = []
            for dep_type in descriptor.dependencies:
                dependency = await self.get_service(dep_type)
                resolved_dependencies.append(dependency)
            
            # Create instance
            instance = descriptor.implementation_type(*resolved_dependencies)
            
            # Initialize if it has an async initialize method
            if hasattr(instance, 'initialize') and asyncio.iscoroutinefunction(instance.initialize):
                await instance.initialize()
            
            return instance
        
        raise ValueError(f"Cannot create instance for service {descriptor.service_type.__name__}")
    
    def _extract_dependencies(self, implementation_type: Type) -> List[Type]:
        """Extract constructor dependencies from a type.
        
        Args:
            implementation_type: Type to analyze
            
        Returns:
            List of dependency types
        """
        dependencies = []
        
        try:
            import inspect
            
            # Get constructor signature
            sig = inspect.signature(implementation_type.__init__)
            
            # Skip 'self' parameter
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                # If parameter has type annotation, add as dependency
                if param.annotation != inspect.Parameter.empty:
                    dependencies.append(param.annotation)
        
        except Exception as e:
            logger.debug(f"Could not extract dependencies for {implementation_type.__name__}: {e}")
        
        return dependencies
    
    def create_scope(self, scope_name: str) -> 'ServiceScope':
        """Create a new service scope.
        
        Args:
            scope_name: Name of the scope
            
        Returns:
            ServiceScope context manager
        """
        return ServiceScopeContext(self, scope_name)
    
    def _enter_scope(self, scope_name: str) -> None:
        """Enter a service scope."""
        self._current_scope = scope_name
        if scope_name not in self._scoped_instances:
            self._scoped_instances[scope_name] = {}
    
    def _exit_scope(self, scope_name: str) -> None:
        """Exit a service scope and cleanup instances."""
        if scope_name in self._scoped_instances:
            # Cleanup scoped instances
            scope_instances = self._scoped_instances[scope_name]
            for instance in scope_instances.values():
                if hasattr(instance, 'dispose'):
                    try:
                        if asyncio.iscoroutinefunction(instance.dispose):
                            # Schedule dispose for async cleanup
                            asyncio.create_task(instance.dispose())
                        else:
                            instance.dispose()
                    except Exception as e:
                        logger.error(f"Error disposing service instance: {e}")
            
            del self._scoped_instances[scope_name]
        
        self._current_scope = None
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered.
        
        Args:
            service_type: Service type to check
            
        Returns:
            True if service is registered
        """
        return service_type in self._services
    
    def get_registered_services(self) -> List[Type]:
        """Get list of all registered service types.
        
        Returns:
            List of registered service types
        """
        return list(self._services.keys())
    
    def clear(self) -> None:
        """Clear all registered services and instances."""
        # Dispose of singleton instances
        for instance in self._instances.values():
            if hasattr(instance, 'dispose'):
                try:
                    if asyncio.iscoroutinefunction(instance.dispose):
                        asyncio.create_task(instance.dispose())
                    else:
                        instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing service instance: {e}")
        
        self._services.clear()
        self._instances.clear()
        self._scoped_instances.clear()
        self._current_scope = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get container statistics.
        
        Returns:
            Dictionary with container statistics
        """
        scope_counts = {}
        for descriptor in self._services.values():
            scope = descriptor.scope.value
            scope_counts[scope] = scope_counts.get(scope, 0) + 1
        
        return {
            'registered_services': len(self._services),
            'singleton_instances': len(self._instances),
            'active_scopes': len(self._scoped_instances),
            'scope_distribution': scope_counts
        }


class ServiceScopeContext:
    """Context manager for service scopes."""
    
    def __init__(self, container: ServiceContainer, scope_name: str):
        """Initialize scope context.
        
        Args:
            container: Service container
            scope_name: Name of the scope
        """
        self.container = container
        self.scope_name = scope_name
    
    def __enter__(self):
        """Enter the scope."""
        self.container._enter_scope(self.scope_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the scope."""
        self.container._exit_scope(self.scope_name)
    
    async def __aenter__(self):
        """Async enter the scope."""
        self.container._enter_scope(self.scope_name)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async exit the scope."""
        self.container._exit_scope(self.scope_name)


# Global container instance
_global_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container.
    
    Returns:
        Global service container instance
    """
    global _global_container
    if _global_container is None:
        _global_container = ServiceContainer()
    return _global_container


def set_container(container: ServiceContainer) -> None:
    """Set the global service container.
    
    Args:
        container: Service container to set as global
    """
    global _global_container
    _global_container = container


async def get_service(service_type: Type[T]) -> T:
    """Get a service from the global container.
    
    Args:
        service_type: Type of service to retrieve
        
    Returns:
        Service instance
    """
    container = get_container()
    return await container.get_service(service_type)