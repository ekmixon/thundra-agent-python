from thundra.samplers.base_sampler import BaseSampler


class ErrorAwareSampler(BaseSampler):

    def __init__(self):
        pass

    def is_sampled(self, span=None):
        return span.get_tag("error") if span else False
