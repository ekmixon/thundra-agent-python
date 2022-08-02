from threading import Lock


class WrapperFactory:
    lock = Lock()
    wrappers = {}

    @staticmethod
    def get_or_create(wrapper_class):
        with WrapperFactory.lock:
            if wrapper_class not in WrapperFactory.wrappers:
                WrapperFactory.wrappers[wrapper_class] = wrapper_class()
            return WrapperFactory.wrappers[wrapper_class]
