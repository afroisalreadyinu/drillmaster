import unittest
import uuid

import pytest

from drillmaster.services import (Service,
                                  ServiceCollection,
                                  ServiceLoadError,
                                  ServiceDefinitionError)
from drillmaster import services

class MockDocker:
    def __init__(self):
        parent = self
        self._networks = []
        self._networking_configs = None
        self._networks_created = []
        self._containers_created = {}
        self._containers_started = []

        class Networks:
            def list(self, names):
                return [x for x in parent._networks if x in names]
            def create(self, network_name, driver=None):
                parent._networks_created.append((network_name, driver))
        self.networks = Networks()

        class API:
            def create_networking_config(self, networking_dict):
                parent._networking_configs = networking_dict
            def create_host_config(*args, **kwargs):
                pass
            def create_endpoint_config(self, aliases=None):
                pass
            def create_container(self, image, **kwargs):
                _id = str(uuid.uuid4())
                parent._containers_created[_id] = {'image': image, **kwargs}
                return {'Id': _id}
            def start(self, container_id):
                parent._containers_started.append(container_id)
        self.api = API()


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
        self.docker = services.the_docker = MockDocker()

    def test_raise_exception_on_no_services(self):
        collection = ServiceCollection()
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


    #@patch('drillmaster.services.threading.Thread')
    def test_start_all(self):
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
        collection.start_all('the-network')
        assert len(self.docker._containers_created) == 3
        assert len(self.docker._containers_started) == 3
        # The one without dependencies should have been started first
        first_cont_id = self.docker._containers_started[0]
        first_cont = self.docker._containers_created[first_cont_id]
        assert first_cont['image'] == 'howareyou/image'
        assert first_cont['name'].startswith('howareyou')


class ServiceCommandTests(unittest.TestCase):

    def setUp(self):
        self.docker = MockDocker()
        class DockerInit:
            @classmethod
            def from_env(cls):
                return self.docker

        services.docker = DockerInit
        class MockServiceCollection:
            def load_definitions(self, exclude=None):
                self.excluded = exclude
                pass
            def start_all(self, network_name):
                self.network_name = network_name
                return ["one", "two"]
        self.collection = MockServiceCollection()
        services.ServiceCollection = lambda: self.collection

    def test_start_service_create_network(self):
        services.start_services(False, [], "drillmaster")
        assert self.docker._networks_created == [("drillmaster", "bridge")]


    def test_start_service_skip_service_creation_if_exists(self):
        self.docker._networks = ["drillmaster"]
        services.start_services(False, [], "drillmaster")
        assert self.docker._networks_created == []

    def test_start_service_exclude(self):
        services.start_services(False, ['blah'], "drillmaster")
        assert self.collection.excluded == ['blah']
