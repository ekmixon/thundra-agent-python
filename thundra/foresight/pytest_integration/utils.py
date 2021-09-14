import wrapt
from thundra.foresight.pytest_integration.pytest_helper import PytestHelper
"""
    Refactor this file. It's been written rapidly.
"""


def _wrapper_setup_fixture(wrapped, instance, args, kwargs):
    res = None
    try:
        request = args[1]
        if not "x_thundra" in request.fixturename:
            if request.scope == "function":
                PytestHelper.start_before_each_span(request)
            else:
                PytestHelper.start_before_all_span(request)
            res = wrapped(*args, **kwargs)
            if request.scope == "function":
                PytestHelper.finish_before_each_span()
            else:
                PytestHelper.finish_before_all_span()
        else:
            res = wrapped(*args, **kwargs)
    except Exception as err:
        print("error occured while fixture_setup function wrapped") # TODO
        res = wrapped(*args, **kwargs)
    if res:
        return res


def _wrapper_teardown_fixture(wrapped, instance, args, kwargs):
    try:
        if not "x_thundra" in kwargs["request"].fixturename:
            request = kwargs["request"]
            if request.scope == "function":
                PytestHelper.start_after_each_span(request)
            else:
                PytestHelper.start_after_all_span(request)
            wrapped(*args, **kwargs)
            if request.scope == "function":
                PytestHelper.finish_after_each_span(request)
            else:
                PytestHelper.finish_after_all_span()
        else:
            wrapped(*args, **kwargs)
    except Exception as err:
        print("error occured while fixture_teardown function wrapped") # TODO
        wrapped(*args, **kwargs)


def patch():
    '''
        fixture function has been called in call_fixture_func.
    '''
    wrapt.wrap_function_wrapper(
            "_pytest.fixtures",
            "call_fixture_func",
            _wrapper_setup_fixture
        )
    '''
        teardown functions has been stored in a stack(FixtureDef._finalizer).
        finish function has been iterated over this stack and call teardown fixtures.
    '''    
    wrapt.wrap_function_wrapper(
            "_pytest.fixtures",
            "FixtureDef.finish",
            _wrapper_teardown_fixture
        )


def unpatch():
    pass #TODO