import copy
from .provider_spec import ProviderSpec
from .roi import Roi
from .array import ArrayKey
from .array_spec import ArraySpec
from .graph import GraphKey
from .graph_spec import GraphSpec

class BatchRequest(ProviderSpec):
    '''A collection of (possibly partial) :class:`ArraySpec` and
    :class:`GraphSpec` forming a request.

    Inherits from :class:`ProviderSpec`.
    '''

    def add(self, key, shape, voxel_size=None):
        '''Convenience method to add an array or graph spec by providing only
        the shape of a ROI (in world units).

        A ROI with zero-offset will be generated. If more than one request is
        added, the ROIs with smaller shapes will be shifted to be centered in
        the largest one.

        Args:

            key (:class:`ArrayKey` or :class:`GraphKey`):

                The key for which to add a spec.

            shape (:class:`Coordinate`):

                A tuple containing the shape of the desired roi

            voxel_size (:class:`Coordinate`):

                A tuple contening the voxel sizes for each corresponding
                dimension
        '''

        if isinstance(key, ArrayKey):
            spec = ArraySpec()
        elif isinstance(key, GraphKey):
            spec = GraphSpec()
        else:
            raise RuntimeError("Only ArrayKey or GraphKey can be added.")

        spec.roi = Roi((0,)*len(shape), shape)

        if voxel_size is not None:
            spec.voxel_size = voxel_size

        self[key] = spec
        self.__center_rois()

    def copy(self):
        '''Create a copy of this request.'''
        return copy.deepcopy(self)

    def __center_rois(self):
        '''Ensure that all ROIs are centered around the same location.'''

        total_roi = self.get_total_roi()
        if total_roi is None:
            return

        center = total_roi.get_center()

        for specs_type in [self.array_specs, self.graph_specs]:
            for key in specs_type:
                roi = specs_type[key].roi
                specs_type[key].roi = roi.shift(center - roi.get_center())

    def merge(self, request):
        '''Merge another request with current request'''

        assert isinstance(request, BatchRequest)

        merged = self.copy()

        for key, spec in request.items():
            if key not in merged:
                merged[key] = spec
            else:
                if isinstance(spec, ArraySpec) and merged[key].nonspatial:
                    merged[key] = spec
                else:
                    merged[key].roi = merged[key].roi.union(spec.roi)

        return merged
