import unittest
from types import SimpleNamespace as Bunch

import pytest

from drillmaster.services import (Service,
                                  ServiceLoadError,
                                  RunningContext,
                                  ServiceCollection,
                                  ServiceAgent,
                                  ServiceDefinitionError)
from drillmaster.service_agent import Options
from drillmaster import services, service_agent

from common import MockDocker

class RunningContextTests(unittest.TestCase):

    def test_service_started(self):
        collection = object()
        service1 = Bunch(name='service1', dependencies=[])
        service2 = Bunch(name='service2', dependencies=[service1])
        context = RunningContext({'service1': service1, 'service2': service2},
                                 collection, Options(False, 'the-network', 50))
        startable = context.service_started('service1')
        assert len(startable) == 1
        assert startable[0].service is service2


    def test_done(self):
        collection = object()
        service1 = Bunch(name='service1', dependencies=[])
        service2 = Bunch(name='service2', dependencies=[service1])
        context = RunningContext({'service1': service1, 'service2': service2},
                                 collection, Options(False, 'the-network', 50))
        context.service_started('service1')
        context.service_started('service2')
        assert context.done


class ServiceDefinitionTests(unittest.TestCase):

    def test_missing_name(self):
        with pytest.raises(ServiceDefinitionError):
            class NewService(Service):
                pass

        with pytest.raises(ServiceDefinitionError):
            class NewService(Service):
                name = "yes"


    def test_missing_image(self):
        with pytest.raises(ServiceDefinitionError):
            class NewService(Service):
                name = "yes"

        with pytest.raises(ServiceDefinitionError):
            class NewService(Service):
                name = "yes"
                image = 34.56


    def test_invalid_field_types(self):
        with pytest.raises(ServiceDefinitionError):
            class NewService(Service):
                name = "yes"
                image = "yes"
                ports = "no"

        with pytest.raises(ServiceDefinitionError):
            class NewService(Service):
                name = "yes"
                image = "yes"
                env = "no"


class ServiceCollectionTests(unittest.TestCase):

    def setUp(self):
        self.docker = MockDocker()
        def get_fake_client():
            return self.docker
        services.get_client = get_fake_client
        service_agent.get_client = get_fake_client

    def test_raise_exception_on_no_services(self):
        collection = ServiceCollection()
        class NewServiceBaseSix(Service):
            name = "not used"
            image = "not used"
        collection._base_class = NewServiceBaseSix
        with pytest.raises(ServiceLoadError):
            collection.load_definitions()

    def test_raise_exception_on_same_name(self):
        collection = ServiceCollection()
        class NewServiceBaseOne(Service):
            name = "not used"
            image = "not used"

        collection._base_class = NewServiceBaseOne
        class ServiceOne(NewServiceBaseOne):
            name = "hello"
            image = "hello"
        class ServiceTwo(NewServiceBaseOne):
            name = "hello"
            image = "hello"
        with pytest.raises(ServiceLoadError):
            collection.load_definitions()


    def test_raise_exception_on_circular_dependency(self):
        collection = ServiceCollection()
        class NewServiceBaseTwo(Service):
            name = "not used"
            image = "not used"
        collection._base_class = NewServiceBaseTwo
        class ServiceOne(NewServiceBaseTwo):
            name = "hello"
            image = "hello"
            dependencies = ["howareyou"]

        class ServiceTwo(NewServiceBaseTwo):
            name = "goodbye"
            image = "hello"
            dependencies = ["hello"]

        class ServiceThree(NewServiceBaseTwo):
            name = "howareyou"
            image = "hello"
            dependencies = ["goodbye"]

        with pytest.raises(ServiceLoadError):
            collection.load_definitions()


    def test_load_services(self):
        collection = ServiceCollection()
        class NewServiceBaseThree(Service):
            name = "not used"
            image = "not used"
        collection._base_class = NewServiceBaseThree
        class ServiceOne(NewServiceBaseThree):
            name = "hello"
            image = "hello"
            dependencies = ["howareyou"]

        class ServiceTwo(NewServiceBaseThree):
            name = "goodbye"
            image = "hello"
            dependencies = ["hello"]

        class ServiceThree(NewServiceBaseThree):
            name = "howareyou"
            image = "hello"

        collection.load_definitions()
        assert len(collection) == 3


    def test_load_services_exclude(self):
        collection = ServiceCollection()
        class NewServiceBaseFive(Service):
            name = "not used"
            image = "not used"
        collection._base_class = NewServiceBaseFive
        class ServiceOne(NewServiceBaseFive):
            name = "hello"
            image = "hello"
            dependencies = ["howareyou"]

        class ServiceTwo(NewServiceBaseFive):
            name = "goodbye"
            image = "hello"
            dependencies = ["hello"]

        class ServiceThree(NewServiceBaseFive):
            name = "howareyou"
            image = "hello"

        collection.load_definitions(exclude=['goodbye'])
        assert len(collection) == 2


    def test_error_on_dependency_excluded(self):
        assert False, "to be written"


    def test_start_all(self):
        # This test does not fake threading, which is somehow dangerous, but the
        # aim is to make sure that the error handling etc. works also when there
        # is an exception in the service agent thread, and the
        # collection.start_all method does not hang.
        collection = ServiceCollection()
        class NewServiceBaseFour(Service):
            name = "not used"
            image = "not used"
        collection._base_class = NewServiceBaseFour
        class ServiceOne(NewServiceBaseFour):
            name = "hello"
            image = "hello/image"
            dependencies = ["howareyou"]

        class ServiceTwo(NewServiceBaseFour):
            name = "goodbye"
            image = "goodbye/image"
            dependencies = ["hello"]

        class ServiceThree(NewServiceBaseFour):
            name = "howareyou"
            image = "howareyou/image"
        collection.load_definitions()
        collection.start_all(Options(False, 'the-network', 50))
        assert len(self.docker._containers_created) == 3
        assert len(self.docker._containers_started) == 3
        # The one without dependencies should have been started first
        first_cont_id = self.docker._containers_started[0]
        first_cont = self.docker._containers_created[first_cont_id]
        assert first_cont['image'] == 'howareyou/image'
        assert first_cont['name'].startswith('howareyou')


    def test_stop_on_fail(self):
        assert False, "to be written"


    def test_start_next(self):
        # with lock stuff
        assert False, "to be written"


class ServiceCommandTests(unittest.TestCase):

    def setUp(self):
        self.docker = MockDocker()
        def get_fake_client():
            return self.docker
        services.get_client = get_fake_client
        class MockServiceCollection:
            def load_definitions(self, exclude=None):
                self.excluded = exclude
            def start_all(self, options):
                self.options = options
                return ["one", "two"]
        self.collection = MockServiceCollection()
        services.ServiceCollection = lambda: self.collection

    def test_start_service_create_network(self):
        services.start_services(False, [], "drillmaster", 50)
        assert self.docker._networks_created == [("drillmaster", "bridge")]


    def test_start_service_skip_service_creation_if_exists(self):
        self.docker._networks = ["drillmaster"]
        services.start_services(True, [], "drillmaster", 50)
        assert self.docker._networks_created == []
        assert self.collection.options.create_new
        assert self.collection.options.timeout == 50

    def test_start_service_exclude(self):
        services.start_services(True, ['blah'], "drillmaster", 50)
        assert self.collection.excluded == ['blah']
        assert self.collection.options.create_new
