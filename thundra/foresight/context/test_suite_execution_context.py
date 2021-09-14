from thundra.context.execution_context import ExecutionContext
from thundra.foresight.test_runner_tags import TestRunnerTags
from thundra.foresight.test_run_context import TestRunContext


class TestSuiteExecutionContext(TestRunContext, ExecutionContext):

    def __init__(self, **opts):
        super(TestSuiteExecutionContext, self).__init__(**opts)
        super(TestRunContext, self).__init__(**opts)
        self.test_suite_name = opts.get("node_id", '')
        self.completed = opts.get("completed", False)
        self.closed = opts.get("closed", False)


    def get_operation_name(self):
        return self.test_suite_name


    def get_additional_start_tags(self):
        return {
            TestRunnerTags.TEST_SUITE: self.test_suite_name
        }


    def get_additional_finish_tags(self):
        return {
            TestRunnerTags.TEST_SUITE_FAILED_COUNT: self.failed_count.value,
            TestRunnerTags.TEST_SUITE_TOTAL_COUNT: self.total_count.value,
            TestRunnerTags.TEST_SUITE_ABORTED_COUNT: self.aborted_count.value,
            TestRunnerTags.TEST_SUITE_SKIPPED_COUNT: self.ignored_count.value,
            TestRunnerTags.TEST_SUITE_SUCCESSFUL_COUNT: self.successful_count.value,
            TestRunnerTags.TEST_TIMEOUT: self.timeout
        }