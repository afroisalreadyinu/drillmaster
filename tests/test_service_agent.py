import unittest
from unittest.mock import patch
from types import SimpleNamespace as Bunch

from drillmaster import service_agent, context
from drillmaster.service_agent import ServiceAgent, Options

from common import FakeDocker, FakeService, FakeServiceCollection

DEFAULT_OPTIONS = Options(False, 'the-network', 1)

class ServiceAgentTests(unittest.TestCase):

    def setUp(self):
        self.docker = FakeDocker.Instance = FakeDocker()
        service_agent.DockerClient = self.docker


    def test_can_start(self):
        service1 = Bunch(name='service1', dependencies=[])
        service2 = Bunch(name='service2', dependencies=[service1])
        agent = ServiceAgent(service2, None, DEFAULT_OPTIONS)
        assert agent.can_start is False

    def test_run_image(self):
        agent = ServiceAgent(FakeService(), None, DEFAULT_OPTIONS)
        agent.run_image()
        assert len(self.docker._services_started) == 1
        prefix, service, network_name = self.docker._services_started[0]
        assert prefix == "service1-drillmaster"
        assert service.name == 'service1'
        assert service.image == 'not/used'
        assert network_name == 'the-network'


    def test_run_image_extrapolate_env(self):
        service = FakeService()
        service.env = {'ENV_ONE': 'http://{host}:{port:d}'}
        context.Context['host'] = 'zombo.com'
        context.Context['port'] = 80
        agent = ServiceAgent(service, None, DEFAULT_OPTIONS)
        agent.run_image()
        assert len(self.docker._services_started) == 1
        _, service, _ = self.docker._services_started[0]
        assert service.env['ENV_ONE'] == 'http://zombo.com:80'


    def test_agent_status_change_happy_path(self):
        class ServiceAgentTestSubclass(ServiceAgent):
            def ping(self):
                assert self.status == 'in-progress'
                return super().ping()
        agent = ServiceAgentTestSubclass(FakeService(), FakeServiceCollection(), DEFAULT_OPTIONS)
        assert agent.status == 'null'
        agent.run()
        assert agent.status == 'started'


    def test_agent_status_change_sad_path(self):
        class ServiceAgentTestSubclass(ServiceAgent):
            def ping(self):
                assert self.status == 'in-progress'
                raise ValueError("I failed miserably")
        agent = ServiceAgentTestSubclass(FakeService(), FakeServiceCollection(), DEFAULT_OPTIONS)
        assert agent.status == 'null'
        agent.run()
        assert agent.status == 'failed'


    def test_skip_if_running_on_same_network(self):
        service = FakeService()
        agent = ServiceAgent(service, None, DEFAULT_OPTIONS)
        self.docker._existing_containers = [Bunch(status='running',
                                                  name="{}-drillmaster-123".format(service.name),
                                                  network='the-network')]
        agent.run_image()
        assert len(self.docker._services_started) == 0
        assert len(self.docker._existing_queried) == 1
        assert self.docker._existing_queried[0] == ("service1-drillmaster", "the-network")


    def test_start_old_container_if_exists(self):
        service = FakeService()
        agent = ServiceAgent(service, None, DEFAULT_OPTIONS)
        restarted = False
        def start():
            nonlocal restarted
            restarted = True
        self.docker._existing_containers = [Bunch(status='exited',
                                                  start=start,
                                                  network='the-network',
                                                  name="{}-drillmaster-123".format(service.name))]
        agent.run_image()
        assert len(self.docker._services_started) == 0
        assert restarted


    def test_start_new_if_run_new_containers(self):
        service = FakeService()
        agent = ServiceAgent(service, None, Options(True, 'the-network', 1))
        restarted = False
        def start():
            nonlocal restarted
            restarted = True
        self.docker._existing_containers = [Bunch(status='exited',
                                                  start=start,
                                                  network='the-network',
                                                  name="{}-drillmaster-123".format(service.name))]
        agent.run_image()
        assert len(self.docker._services_started) == 1
        assert not restarted


    def test_start_new_if_always_start_new(self):
        service = FakeService()
        service.always_start_new = True
        agent = ServiceAgent(service, None, Options(True, 'the-network', 1))
        restarted = False
        def start():
            nonlocal restarted
            restarted = True
        self.docker._existing_containers = [Bunch(status='exited',
                                                  start=start,
                                                  network='the-network',
                                                  name="{}-drillmaster-123".format(service.name))]
        agent.run_image()
        assert len(self.docker._services_started) == 1
        assert not restarted


    def test_ping_and_init_after_run(self):
        fake_collection = FakeServiceCollection()
        fake_service = FakeService()
        agent = ServiceAgent(fake_service, fake_collection, DEFAULT_OPTIONS)
        agent.run()
        assert fake_collection.started_service == 'service1'
        assert fake_service.ping_count == 1
        assert fake_service.init_called


    def test_no_ping_or_init_if_running(self):
        service = FakeService()
        fake_collection = FakeServiceCollection()
        agent = ServiceAgent(service, fake_collection, Options(True, 'the-network', 1))
        self.docker._existing_containers = [Bunch(status='running',
                                                  network='the-network',
                                                  name="{}-drillmaster-123".format(service.name))]
        agent.run()
        assert service.ping_count == 0
        assert not service.init_called


    def test_yes_ping_no_init_if_started(self):
        service = FakeService()
        fake_collection = FakeServiceCollection()
        agent = ServiceAgent(service, fake_collection, Options(False, 'the-network', 1))
        def start():
            pass
        self.docker._existing_containers = [Bunch(status='exited',
                                                  start=start,
                                                  network='the-network',
                                                  name="{}-drillmaster-123".format(service.name))]
        agent.run()
        assert service.ping_count == 1
        assert not service.init_called


    @patch('drillmaster.service_agent.time')
    def test_ping_timeout(self, mock_time):
        mock_time.monotonic.side_effect = [0, 0.2, 0.6, 0.8, 1]
        fake_collection = FakeServiceCollection()
        fake_service = FakeService(fail_ping=True)
        agent = ServiceAgent(fake_service, fake_collection, DEFAULT_OPTIONS)
        agent.run()
        assert fake_service.ping_count == 3
        assert mock_time.sleep.call_count == 3


    def test_service_failed_on_failed_ping(self):
        fake_collection = FakeServiceCollection()
        fake_service = FakeService(fail_ping=True)
        agent = ServiceAgent(fake_service, fake_collection, DEFAULT_OPTIONS)
        agent.run()
        assert fake_service.ping_count > 0
        assert fake_collection.started_service is None
        assert fake_collection.failed_service == 'service1'


    def test_call_collection_failed_on_error(self):
        fake_collection = FakeServiceCollection()
        fake_service = FakeService(exception_at_init=ValueError)
        agent = ServiceAgent(fake_service, fake_collection, DEFAULT_OPTIONS)
        agent.run()
        assert fake_service.ping_count > 0
        assert fake_collection.started_service is None
        assert fake_collection.failed_service == 'service1'
