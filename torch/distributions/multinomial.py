import torch
from torch.distributions.distribution import Distribution
from torch.autograd import Variable
from torch.distributions import Categorical
from numbers import Number
from torch.distributions import constraints
from torch.distributions.utils import log_sum_exp, broadcast_all


class Multinomial(Distribution):
    r"""
    Creates a Multinomial distribution parameterized by `total_count` and
    either `probs` or `logits` (but not both). The innermost dimension of
    `probs` indexes over categories. All other dimensions index over batches.

    Note that `total_count` need not be specified if only :meth:`log_prob` is
    called (see example below)

    -   :meth:`sample` requires a single shared `total_count` for all
        parameters and samples.
    -   :meth:`log_prob` allows different `total_count` for each parameter and
        sample.

    Example::

        >>> m = Multinomial(100, torch.Tensor([ 1, 1, 1, 1]))
        >>> x = m.sample()  # equal probability of 0, 1, 2, 3
         21
         24
         30
         25
        [torch.FloatTensor of size 4]]

        >>> Multinomial(probs=torch.Tensor([1, 1, 1, 1])).log_prob(x)
        -4.1338
        [torch.FloatTensor of size 1]

    Args:
        total_count (int): number of trials
        probs (Tensor or Variable): event probabilities
        logits (Tensor or Variable): event log probabilities
    """
    params = {'logits': constraints.real}  # Let logits be the canonical parameterization.

    def __init__(self, total_count=1, probs=None, logits=None):
        if not isinstance(total_count, Number):
            raise NotImplementedError('inhomogeneous total_count is not supported')
        self.total_count = total_count
        self._categorical = Categorical(probs=probs, logits=logits)
        batch_shape = probs.size()[:-1] if probs is not None else logits.size()[:-1]
        event_shape = probs.size()[-1:] if probs is not None else logits.size()[-1:]
        super(Multinomial, self).__init__(batch_shape, event_shape)

    @constraints.dependent_property
    def support(self):
        return constraints.integer_interval(0, self.total_count)

    @property
    def logits(self):
        return self._categorical.logits

    @property
    def probs(self):
        return self._categorical.probs

    def sample(self, sample_shape=torch.Size()):
        sample_shape = torch.Size(sample_shape)
        samples = self._categorical.sample(torch.Size((self.total_count,)) + sample_shape)
        # samples.shape is (total_count, sample_shape, batch_shape), need to change it to
        # (sample_shape, batch_shape, total_count)
        shifted_idx = list(range(samples.dim()))
        shifted_idx.append(shifted_idx.pop(0))
        samples = samples.permute(*shifted_idx)
        counts = samples.new(self._extended_shape(sample_shape)).zero_()
        counts.scatter_add_(-1, samples, torch.ones_like(samples))
        return counts.type_as(self.probs)

    def log_prob(self, value):
        self._validate_log_prob_arg(value)
        logits, value = broadcast_all(self.logits.clone(), value)
        log_factorial_n = torch.lgamma(value.sum(-1) + 1)
        log_factorial_xs = torch.lgamma(value + 1).sum(-1)
        logits[(value == 0) & (logits == -float('inf'))] = 0
        log_powers = (logits * value).sum(-1)
        return log_factorial_n - log_factorial_xs + log_powers
