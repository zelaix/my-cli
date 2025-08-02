"""
Tests for the dependency injection container.
"""

import pytest
import asyncio
from typing import Optional
from unittest.mock import Mock, AsyncMock

from my_cli.core.container import (
    ServiceContainer, ServiceScope, ServiceDescriptor,
    get_container, set_container, get_service
)


class TestService:
    """Simple test service."""
    
    def __init__(self, value: str = "test"):
        self.value = value
        self.initialized = False
        self.disposed = False
    
    async def initialize(self):
        """Async initialization method."""
        self.initialized = True
    
    def dispose(self):
        """Cleanup method."""
        self.disposed = True


class TestServiceWithDependency:
    """Test service with a dependency."""
    
    def __init__(self, dependency: TestService):
        self.dependency = dependency
        self.initialized = False
    
    async def initialize(self):
        self.initialized = True


class TestAsyncService:
    """Service with async factory."""
    
    def __init__(self, value: str):
        self.value = value


async def async_factory() -> TestAsyncService:
    """Async factory function."""
    await asyncio.sleep(0.01)  # Simulate async work
    return TestAsyncService("async_created")


def sync_factory() -> TestService:
    """Sync factory function."""
    return TestService("factory_created")


class TestServiceContainer:
    """Test the ServiceContainer class."""
    
    @pytest.fixture
    def container(self):
        return ServiceContainer()
    
    def test_register_singleton_with_type(self, container):
        """Test registering a singleton with type."""
        result = container.register_singleton(TestService)
        assert result is container  # Should return self for chaining
        assert container.is_registered(TestService)
    
    def test_register_singleton_with_instance(self, container):
        """Test registering a singleton with instance."""
        instance = TestService("instance")
        container.register_singleton(TestService, instance=instance)
        
        assert container.is_registered(TestService)
    
    def test_register_singleton_with_factory(self, container):
        """Test registering a singleton with factory."""
        container.register_singleton(TestService, factory=sync_factory)
        assert container.is_registered(TestService)
    
    def test_register_transient(self, container):
        """Test registering a transient service."""
        container.register_transient(TestService)
        assert container.is_registered(TestService)
    
    def test_register_scoped(self, container):
        """Test registering a scoped service."""
        container.register_scoped(TestService)
        assert container.is_registered(TestService)
    
    def test_register_with_invalid_instance_scope(self, container):
        """Test registering instance with non-singleton scope fails."""
        instance = TestService()
        
        with pytest.raises(ValueError, match="Pre-created instances can only be registered as singletons"):
            container.register_transient(TestService, instance=instance)
    
    @pytest.mark.asyncio
    async def test_get_singleton_service(self, container):
        """Test getting a singleton service."""
        container.register_singleton(TestService)
        
        service1 = await container.get_service(TestService)
        service2 = await container.get_service(TestService)
        
        assert isinstance(service1, TestService)
        assert service1 is service2  # Same instance
        assert service1.initialized  # Should be initialized
    
    @pytest.mark.asyncio
    async def test_get_transient_service(self, container):
        """Test getting a transient service."""
        container.register_transient(TestService)
        
        service1 = await container.get_service(TestService)
        service2 = await container.get_service(TestService)
        
        assert isinstance(service1, TestService)
        assert isinstance(service2, TestService)
        assert service1 is not service2  # Different instances
    
    @pytest.mark.asyncio
    async def test_get_scoped_service(self, container):
        """Test getting a scoped service."""
        container.register_scoped(TestService)
        
        with container.create_scope("test_scope"):
            service1 = await container.get_service(TestService)
            service2 = await container.get_service(TestService)
            
            assert isinstance(service1, TestService)
            assert service1 is service2  # Same instance within scope
    
    @pytest.mark.asyncio
    async def test_get_scoped_service_different_scopes(self, container):
        """Test getting scoped service in different scopes."""
        container.register_scoped(TestService)
        
        with container.create_scope("scope1"):
            service1 = await container.get_service(TestService)
        
        with container.create_scope("scope2"):
            service2 = await container.get_service(TestService)
        
        assert service1 is not service2  # Different instances in different scopes
    
    @pytest.mark.asyncio
    async def test_get_service_not_registered(self, container):
        """Test getting a service that's not registered."""
        with pytest.raises(ValueError, match="Service TestService is not registered"):
            await container.get_service(TestService)
    
    @pytest.mark.asyncio
    async def test_get_scoped_service_no_scope(self, container):
        """Test getting scoped service without active scope."""
        container.register_scoped(TestService)
        
        with pytest.raises(ValueError, match="No active scope for scoped service"):
            await container.get_service(TestService)
    
    @pytest.mark.asyncio
    async def test_service_with_dependency(self, container):
        """Test service with dependency injection."""
        container.register_singleton(TestService)
        container.register_singleton(TestServiceWithDependency)
        
        service = await container.get_service(TestServiceWithDependency)
        
        assert isinstance(service, TestServiceWithDependency)
        assert isinstance(service.dependency, TestService)
        assert service.initialized
        assert service.dependency.initialized
    
    @pytest.mark.asyncio
    async def test_async_factory(self, container):
        """Test async factory function."""
        container.register_singleton(TestAsyncService, factory=async_factory)
        
        service = await container.get_service(TestAsyncService)
        
        assert isinstance(service, TestAsyncService)
        assert service.value == "async_created"
    
    @pytest.mark.asyncio
    async def test_sync_factory(self, container):
        """Test sync factory function."""
        container.register_singleton(TestService, factory=sync_factory)
        
        service = await container.get_service(TestService)
        
        assert isinstance(service, TestService)
        assert service.value == "factory_created"
    
    def test_is_registered(self, container):
        """Test checking if service is registered."""
        assert not container.is_registered(TestService)
        
        container.register_singleton(TestService)
        assert container.is_registered(TestService)
    
    def test_get_registered_services(self, container):
        """Test getting list of registered services."""
        assert container.get_registered_services() == []
        
        container.register_singleton(TestService)
        container.register_transient(TestAsyncService)
        
        services = container.get_registered_services()
        assert len(services) == 2
        assert TestService in services
        assert TestAsyncService in services
    
    def test_clear(self, container):
        """Test clearing all services."""
        instance = TestService()
        container.register_singleton(TestService, instance=instance)
        container.register_transient(TestAsyncService)
        
        container.clear()
        
        assert not container.is_registered(TestService)
        assert not container.is_registered(TestAsyncService)
        assert instance.disposed  # Should call dispose
    
    def test_get_stats(self, container):
        """Test getting container statistics."""
        container.register_singleton(TestService)
        container.register_transient(TestAsyncService)
        container.register_scoped(TestServiceWithDependency)
        
        stats = container.get_stats()
        
        assert stats['registered_services'] == 3
        assert stats['singleton_instances'] == 0  # Not created yet
        assert stats['active_scopes'] == 0
        assert stats['scope_distribution']['singleton'] == 1
        assert stats['scope_distribution']['transient'] == 1
        assert stats['scope_distribution']['scoped'] == 1


class TestServiceScopeContext:
    """Test the ServiceScopeContext class."""
    
    @pytest.fixture
    def container(self):
        return ServiceContainer()
    
    def test_sync_context_manager(self, container):
        """Test sync context manager."""
        container.register_scoped(TestService)
        
        with container.create_scope("test") as scope:
            assert scope is not None
            # Container should have active scope
        
        # Scope should be cleaned up
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, container):
        """Test async context manager."""
        container.register_scoped(TestService)
        
        async with container.create_scope("test") as scope:
            assert scope is not None
            service = await container.get_service(TestService)
            assert isinstance(service, TestService)
        
        # Scope should be cleaned up


class TestGlobalFunctions:
    """Test global container functions."""
    
    def test_get_container(self):
        """Test getting global container."""
        container = get_container()
        assert isinstance(container, ServiceContainer)
        
        # Should return same instance
        container2 = get_container()
        assert container is container2
    
    def test_set_container(self):
        """Test setting global container."""
        custom_container = ServiceContainer()
        set_container(custom_container)
        
        retrieved = get_container()
        assert retrieved is custom_container
    
    @pytest.mark.asyncio
    async def test_get_service_global(self):
        """Test getting service from global container."""
        container = get_container()
        container.register_singleton(TestService)
        
        service = await get_service(TestService)
        assert isinstance(service, TestService)