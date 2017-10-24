from .batch_filter import BatchFilter
from gunpowder.volume import VolumeTypes, Volume
import collections
import logging
import numpy as np

logger = logging.getLogger(__name__)


class BalanceLabels(BatchFilter):
    '''Creates a scale volume to balance the loss between positive and negative
    labels.

    Args:

        labels (:class:``VolumeType``): A volume containing binary labels.

        scales (:class:``VolumeType``): A volume with scales to be created. This
            new volume will have the same ROI and resolution as `labels`.

        mask (:class:``VolumeType``, optional): An optional mask (or list of
            masks) to consider for balancing. Every voxel marked with a 0 will
            not contribute to the scaling and will have a scale of 0 in
            `scales`.
    '''

    def __init__(self, labels, scales, mask=None):

        self.labels = labels
        self.scales = scales
        if mask is None:
            self.masks = []
        elif not isinstance(mask, collections.Iterable):
            self.masks = [mask]
        else:
            self.masks = mask

        self.skip_next = False

    def setup(self):

        assert self.labels in self.spec, (
            "Asked to balance labels %s, which are not provided."%self.labels)

        for mask in self.masks:
            assert mask in self.spec, (
                "Asked to apply mask %s to balance labels, but mask is not "
                "provided."%mask)

        spec = self.spec[self.labels].copy()
        spec.dtype = np.float32
        self.provides(self.scales, spec)

    def prepare(self, request):

        self.skip_next = True
        if self.scales in request:
            del request[self.scales]
            self.skip_next = False

    def process(self, batch, request):

        if self.skip_next:
            self.skip_next = False
            return

        labels = batch.volumes[self.labels]

        # initialize error scale with 1s
        error_scale = np.ones(labels.data.shape, dtype=np.float32)

        # set error_scale to 0 in masked-out areas
        for identifier in self.masks:
            mask = batch.volumes[identifier]
            assert labels.data.shape == mask.data.shape, (
                "Shape of mask %s %s does not match %s %s"%(
                    mask,
                    mask.data.shape,
                    self.labels,
                    labels.data.shape))
            error_scale *= mask.data

        # in the masked-in area, compute the fraction of positive samples
        masked_in = error_scale.sum()
        labels_binary = np.floor(np.clip(labels.data+0.5, a_min=0, a_max=1))
        num_pos  = (labels_binary * error_scale).sum()
        frac_pos = float(num_pos) / masked_in if masked_in > 0 else 0
        frac_pos = np.clip(frac_pos, 0.05, 0.95)
        frac_neg = 1.0 - frac_pos

        # compute the class weights for positive and negative samples
        w_pos = 1.0 / (2.0 * frac_pos)
        w_neg = 1.0 / (2.0 * frac_neg)

        # scale the masked-in error_scale with the class weights
        error_scale *= (labels_binary >= 0.5) * w_pos + (labels_binary < 0.5) * w_neg

        spec = self.spec[self.scales].copy()
        spec.roi = labels.spec.roi
        batch.volumes[self.scales] = Volume(error_scale, spec)
