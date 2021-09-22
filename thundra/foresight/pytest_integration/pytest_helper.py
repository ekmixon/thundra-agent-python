from thundra.application.application_info import ApplicationInfo
from thundra.application.application_info_provider import ApplicationInfoProvider
from thundra.opentracing.tracer import ThundraTracer
from thundra.foresight.test_runner_support import TestRunnerSupport
from thundra.foresight.environment.environment_info_support import EnvironmentSupport
from thundra.foresight.util.test_wrapper_utils import TestWrapperUtils
from thundra.context.execution_context_manager import ExecutionContextManager
from thundra.foresight.test_runner_tags import TestRunnerTags
import thundra.foresight.utils as utils
import uuid, os
import pytest
from thundra.plugins.invocation import invocation_support, invocation_trace_support
from thundra import constants


THUNDRA_SCOPE = "x-thundra-scope"


class HandleSpan:

    @staticmethod
    def create_span(request, operation_name, app_info={}):
        tracer = ThundraTracer().get_instance()
        parent_span = tracer.get_active_span()
        parent_transaction_id = parent_span.transaction_id if parent_span.transaction_id else None
        trace_id = str(uuid.uuid4())
        transaction_id = parent_transaction_id or str(uuid.uuid4())
        execution_context = ExecutionContextManager.get()
        scope =  tracer.start_active_span(
            child_of= parent_span,
            span_id=str(uuid.uuid4()),
            operation_name=operation_name,
            trace_id=trace_id,
            transaction_id=transaction_id,
            start_time=utils.current_milli_time(),
            execution_context = execution_context
        )
        span = scope.span
        span.domain_name = app_info.get("applicationDomainName")
        span.class_name = app_info.get("applicationClassName")
        span.service_name = app_info.get("applicationName")
        HandleSpan.inject_scope(request, scope)
        return scope.span


    @staticmethod
    def finish_span(request, tagName):
        context = ExecutionContextManager.get()
        scope = HandleSpan.extract_scope(request)
        current_span = scope.span
        current_span.finish(f_time=utils.current_milli_time())
        scope.close()
        if not context or not context.invocation_data:
            #TODO Add log
            return

        invocation_data = context.invocation_data
        if invocation_data:
            duration = current_span.get_duration()
            current_duration = 0
            if tagName in invocation_data["tags"]:
                current_duration = invocation_data["tags"][tagName]
            duration = duration + current_duration
            invocation_data["tags"][tagName] = duration


    @staticmethod
    def inject_scope(request, scope):
        setattr(request, THUNDRA_SCOPE, scope)


    @staticmethod
    def extract_scope(request):
        return getattr(request, THUNDRA_SCOPE, None)

class PytestHelper:

    TEST_APP_ID_PREFIX = "python:test:pytest:"
    TEST_APP_INSTANCE_ID_PREFIX = str(uuid.uuid4()) + ":"
    TEST_APP_STAGE = "test"
    TEST_APP_VERSION = pytest.__version__
    TEST_FIXTURE_DOMAIN_NAME = "TestFixture"
    TEST_DOMAIN_NAME = "Test"
    TEST_SUITE_DOMAIN_NAME = "TestSuite"
    TEST_CLASS_NAME = "Pytest"
    TEST_OPERATION_NAME = "RunTest"
    TEST_BEFORE_ALL_OPERATION_NAME = "beforeAll"
    TEST_AFTER_ALL_OPERATION_NAME = "afterAll"
    TEST_BEFORE_EACH_OPERATION_NAME = "beforeEach"
    TEST_AFTER_EACH_OPERATION_NAME = "afterEach"
    MAX_TEST_METHOD_NAME = 100
    TEST_SUITE_CONTEXT_PROP_NAME = "THUNDRA::TEST_SUITE_CONTEXT"
    TEST_OPERATION_NAME_INDEX = 2
    TEST_SUITE = "module"
    TEST_CASE = "function"


    @staticmethod
    def get_test_application_name(request):
        return request.node.nodeid.replace("::", os.sep)


    @classmethod
    def get_test_application_id(cls, request):
        return cls.TEST_APP_ID_PREFIX + cls.get_test_application_name(request)


    @classmethod
    def get_test_application_instance_id(cls, request):
        return cls.TEST_APP_INSTANCE_ID_PREFIX + cls.get_test_application_name(request)


    @classmethod
    def get_test_application_info(cls, request):
        domain_name = None
        application_id = None
        if request.scope == cls.TEST_SUITE:
            domain_name = cls.TEST_SUITE_DOMAIN_NAME
            application_id = cls.get_test_application_id(request)
        if request.scope == cls.TEST_CASE:
            domain_name = cls.TEST_DOMAIN_NAME
        return ApplicationInfo(
            application_id,
            cls.get_test_application_instance_id(request),
            domain_name,
            cls.TEST_CLASS_NAME,
            cls.get_test_application_name(request),
            cls.TEST_APP_VERSION,
            cls.TEST_APP_STAGE,
            ApplicationInfoProvider.APPLICATION_RUNTIME,
            ApplicationInfoProvider.APPLICATION_RUNTIME_VERSION,
            None,
        )

    @staticmethod
    def get_test_fixture_application_name(request):
        return request.fixturename


    @classmethod
    def get_test_fixture_application_id(cls, request):
        return cls.TEST_APP_ID_PREFIX + cls.get_test_fixture_application_name(request)


    @classmethod
    def get_test_fixture_application_instance_id(cls, request):
        return cls.TEST_APP_INSTANCE_ID_PREFIX + cls.get_test_fixture_application_name(request)


    @classmethod
    def get_test_fixture_application_info(cls, request):
        return ApplicationInfo(
            cls.get_test_fixture_application_id(request),
            cls.TEST_FIXTURE_DOMAIN_NAME,
            cls.TEST_CLASS_NAME,
            cls.get_test_fixture_application_name(request),
            cls.TEST_APP_VERSION,
            cls.TEST_APP_STAGE,
            ApplicationInfoProvider.APPLICATION_RUNTIME,
            ApplicationInfoProvider.APPLICATION_RUNTIME_VERSION,
            None,
        )


    @classmethod
    def get_test_method_name(cls, request):
        nodeid = cls.get_test_application_name(request)
        if len(nodeid) > cls.MAX_TEST_METHOD_NAME:
            nodeid = "..." + nodeid[(len(nodeid)-cls.MAX_TEST_METHOD_NAME) + 3:]
        return nodeid


    @classmethod
    def get_test_name(cls, request):
        return cls.get_test_method_name(request)

    
    @staticmethod
    def session_setup(executor, api_key=None):
        EnvironmentSupport.init()
        TestWrapperUtils(plugin_executor = executor)
        TestRunnerSupport.start_test_run()


    @staticmethod
    def session_teardown():
        TestRunnerSupport.finish_current_test_run()


    @classmethod
    def start_test_suite_span(cls, request):
        test_wrapper_utils = TestWrapperUtils.get_instance()
        test_suite_name = request.node.nodeid
        context = test_wrapper_utils.create_test_suite_execution_context(test_suite_name)
        ExecutionContextManager.set(context)
        app_info = cls.get_test_application_info(request)
        test_wrapper_utils.change_app_info(app_info)
        TestRunnerSupport.set_test_suite_application_info(app_info)
        TestRunnerSupport.set_test_suite_execution_context(context)
        test_wrapper_utils.before_test_process(context)


    @classmethod
    def start_before_all_span(cls, request):
        app_info = cls.get_test_fixture_application_info(request).to_json()
        span = HandleSpan.create_span(request, cls.TEST_BEFORE_ALL_OPERATION_NAME, app_info)
        span.set_tag(TestRunnerTags.TEST_SUITE, request.node.nodeid)


    @staticmethod
    def finish_before_all_span(request):
        HandleSpan.finish_span(request, TestRunnerTags.TEST_BEFORE_ALL_DURATION)


    @classmethod
    def start_after_all_span(cls, request):
        app_info = cls.get_test_fixture_application_info(request).to_json()
        span = HandleSpan.create_span(request, cls.TEST_AFTER_ALL_OPERATION_NAME, app_info)
        span.set_tag(TestRunnerTags.TEST_SUITE, request.node.nodeid)
        


    @staticmethod
    def finish_after_all_span(request):
        HandleSpan.finish_span(request, TestRunnerTags.TEST_AFTER_ALL_DURATION)


    @staticmethod
    def finish_test_suite_span():
        test_wrapper_utils = TestWrapperUtils.get_instance()
        context = ExecutionContextManager.get()
        test_wrapper_utils.after_test_process(context)


    @classmethod
    def start_test_span(cls, request):
        test_wrapper_utils = TestWrapperUtils.get_instance()
        app_info = cls.get_test_application_info(request)
        test_wrapper_utils.change_app_info(app_info)
        current_context = ExecutionContextManager.get()
        parent_transaction_id = current_context.invocation_data.get("transactionId")
        context = test_wrapper_utils.create_test_case_execution_context(request, app_info, parent_transaction_id)   
        ExecutionContextManager.set(context)
        TestRunnerSupport.set_test_case_application_info(app_info)
        test_wrapper_utils.before_test_process(context)


    @classmethod
    def start_before_each_span(cls, request):
        app_info = cls.get_test_fixture_application_info(request).to_json()
        span = HandleSpan.create_span(request, cls.TEST_BEFORE_EACH_OPERATION_NAME, app_info)
        span.set_tag(TestRunnerTags.TEST_SUITE, request.node.location[0])


    @staticmethod
    def finish_before_each_span(request):
        HandleSpan.finish_span(request, TestRunnerTags.TEST_BEFORE_EACH_DURATION)


    @classmethod
    def start_after_each_span(cls, request):
        app_info = cls.get_test_fixture_application_info(request).to_json()
        span = HandleSpan.create_span(request, cls.TEST_AFTER_EACH_OPERATION_NAME, app_info)
        span.set_tag(TestRunnerTags.TEST_SUITE, request.node.location[0])


    @classmethod
    def finish_after_each_span(cls, request):
        scope = HandleSpan.extract_scope(request)
        span = scope.span
        span.set_tag(TestRunnerTags.TEST_NAME, cls.get_test_method_name(request))
        HandleSpan.finish_span(request, TestRunnerTags.TEST_AFTER_EACH_DURATION)


    @staticmethod
    def finish_test_span():
        test_wrapper_utils = TestWrapperUtils.get_instance()
        context = ExecutionContextManager.get()
        test_wrapper_utils.after_test_process(context)
        app_info = TestRunnerSupport.test_suite_application_info
        context = TestRunnerSupport.test_suite_execution_context
        test_wrapper_utils.change_app_info(app_info)
        ExecutionContextManager.set(context)
