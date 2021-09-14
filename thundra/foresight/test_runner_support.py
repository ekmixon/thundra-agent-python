from thundra.config.config_provider import ConfigProvider
from thundra.config import config_names
from thundra.foresight.environment.environment_info_support import EnvironmentSupport
from thundra.foresight.model.test_run_start import TestRunStart
from thundra.foresight.model.test_run_status import TestRunStatus
from thundra.foresight.model.test_run_result import TestRunResult
from thundra.foresight.model.test_run_finish import TestRunFinish
from thundra.foresight.test_run_context import TestRunContext
from uuid import uuid4
from thundra.foresight.util.test_wrapper_utils import TestWrapperUtils
import thundra.foresight.utils as utils
import logging, socket, threading

LOGGER = logging.getLogger(__name__)


class _TestRunScope:
    
    def __init__(self, id=None, task_id = None, start_timestamp = None, context = None):

        self.id = id
        self.task_id = task_id
        self.start_timestamp = start_timestamp
        self.context = context

class _StatusReporter:

    def __init__(self):
        self.delay = TestRunnerSupport.STATUS_REPORT_FREQ_SECS
        self.t = None


    def start(self):
        if not self.t:
            self.t = threading.Timer(self.delay, self.report_status)
            self.t.start()


    def stop(self):
        if self.t and self.t.is_alive():
            self.t.cancel()


    def report_status(self):
        test_wrapper_utils = TestWrapperUtils.get_instance()
        status_time = utils.current_milli_time()
        test_run_status = TestRunStatus(
            id = TestRunnerSupport.test_run_scope.id,
            project_id = TestRunnerSupport.PROJECT_ID,
            task_id = TestRunnerSupport.test_run_scope.task_id,
            start_timestamp= TestRunnerSupport.test_run_scope.start_timestamp,
            status_timestamp= status_time,
            total_count= TestRunnerSupport.test_run_scope.context.total_count.value,
            successful_count= TestRunnerSupport.test_run_scope.context.successful_count.value,
            failed_count = TestRunnerSupport.test_run_scope.context.failed_count.value,
            ignored_count= TestRunnerSupport.test_run_scope.context.ignored_count.value,
            aborted_count= TestRunnerSupport.test_run_scope.context.aborted_count.value,
            host_name = TestRunnerSupport.HOST_NAME,
            environment_info= EnvironmentSupport.environment_info,
            # TODO tags
        )
        test_wrapper_utils.send_test_run_data(test_run_status) # TODO


class TestRunnerSupport:

    PROJECT_ID = ConfigProvider.get(config_names.THUNDRA_TEST_PROJECT_ID)
    STATUS_REPORT_FREQ_SECS = ConfigProvider.get(config_names.THUNDRA_TEST_STATUS_REPORT_FREQUENCY)
    LOG_ENABLE = ConfigProvider.get(config_names.THUNDRA_TEST_LOG_ENABLE)
    MAX_LOG_COUNT = ConfigProvider.get(config_names.THUNDRA_TEST_LOG_COUNT_MAX)
    MAX_SPAN_COUNT = ConfigProvider.get(config_names.THUNDRA_TEST_SPAN_COUNT_MAX)
    HOST_NAME = socket.gethostname()

    test_suite_contexts = dict()
    started_test_suites = set()
    test_run_scope = None
    test_run_reporter = None
    status_reporter = None


    @classmethod
    def on_test_suite_start(cls, test_module_name):
        cls.add_started_test_suite(test_module_name)


    @classmethod
    def add_started_test_suite(cls, test_module_name, thundra_span): #TODO thundra_span?
        if not test_module_name:
            return False
        cls.started_test_suites.add(test_module_name)
        return True


    @classmethod
    def on_test_suite_finish(cls, test_module_name):
        cls.remove_started_test_suite(test_module_name)
    

    @classmethod
    def remove_started_test_suite(cls, test_module_name):
        if not test_module_name:
            return False
        try:
            cls.started_test_suites.remove(test_module_name)
        except Exception as err:
            LOGGER.error("Started test suite with {} name couldn't be removed".format(test_module_name), err)
        return True


    @classmethod
    def clear_started_test_suites(cls):
        cls.started_test_suites.clear()


    @classmethod
    def start_test_suite_context(cls, test_suite_context):
        cls.test_suite_contexts[test_suite_context.transaction_id] = test_suite_context


    @classmethod
    def finish_test_suite_context(cls, test_suite_context):
        try:
            del cls.test_suite_contexts[test_suite_context.transaction_id]
        except Exception as err:
            LOGGER.error("Test suite couldn't removed from test suite contexts", err)


    @classmethod
    def clear_test_run(cls):
        cls.test_run_scope = None


    @staticmethod
    def do_get_test_run_id():
        test_run_id = None
        environment_info = EnvironmentSupport.environment_info
        if not environment_info:
            test_run_id = environment_info.get_test_run_id()
        if not test_run_id:
            test_run_id = str(uuid4())
        return test_run_id


    @classmethod
    def start_test_run(cls):
        test_wrapper_utils = TestWrapperUtils.get_instance()
        context = TestRunContext()
        id = cls.do_get_test_run_id()
        task_id = str(uuid4())
        current_time = utils.current_milli_time()
        cls.test_run_scope = _TestRunScope(id, task_id, current_time, context)
        #TODO Sampling
        test_run_start = TestRunStart(
            cls.test_run_scope.id,
            cls.PROJECT_ID,
            cls.test_run_scope.task_id,
            cls.test_run_scope.start_timestamp,
            cls.HOST_NAME,
            EnvironmentSupport.environment_info
        )
        test_wrapper_utils.send_test_run_data(cls.test_run_reporter, test_run_start) #TODO
        if cls.status_reporter:
            cls.status_reporter.stop()
        else:
            cls.status_reporter = _StatusReporter()
        cls.status_reporter.start()
    

    @classmethod
    def finish_current_test_run(cls):
        test_run_context = cls.get_test_run_context()
        if test_run_context:
            test_run_result = TestRunResult(
                total_count = test_run_context.total_count.value,
                successful_count = test_run_context.successful_count.value,
                failed_count = test_run_context.failed_count.value,
                ignored_count = test_run_context.ignored_count.value,
                aborted_count = test_run_context.aborted_count.value
            ) 
            cls.finish_test_run(test_run_result)


    @classmethod
    def finish_test_run(cls, test_run_result):
        try:
            test_wrapper_utils = TestWrapperUtils.get_instance()
            finish_time = utils.current_milli_time()
            if cls.test_run_scope:
                #TODO Sampler reset
                if cls.status_reporter:
                    try:
                        cls.status_reporter.stop()
                    finally:
                        cls.status_reporter = None
                test_run_finish = TestRunFinish(
                    id = cls.test_run_scope.id,
                    project_id = cls.PROJECT_ID,
                    task_id = cls.test_run_scope.task_id,
                    start_timestamp= cls.test_run_scope.start_timestamp,
                    finish_timestamp= finish_time,
                    duration = finish_time - cls.test_run_scope.start_timestamp,
                    total_count= test_run_result.total_count,
                    successful_count= test_run_result.successful_count,
                    failed_count = test_run_result.failed_count,
                    ignored_count= test_run_result.ignored_count,
                    aborted_count= test_run_result.aborted_count,
                    host_name = cls.HOST_NAME,
                    environment_info= EnvironmentSupport.environment_info,
                    # TODO tags
                )
                test_wrapper_utils.send_test_run_data(test_run_finish) # TODO ASK
        except Exception as err:
            LOGGER.error("Thundra foresight finist test run error", err)
        finally:
            cls.test_run_scope = None

    @classmethod
    def get_test_run_context(cls):
        if not cls.test_run_scope:
            return cls.test_run_scope.context
        return None


    @classmethod 
    def get_test_run_id(cls):
        if cls.test_run_scope:
            return cls.test_run_scope.id
        return None


    @classmethod
    def get_test_run_task_id(cls):
        if cls.test_run_scope.task_id:
            return cls.test_run_scope.task_id
        return None