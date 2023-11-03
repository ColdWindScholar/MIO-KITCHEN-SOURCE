import blockimgdiff


class Options(object):
    def __init__(self):
        # Stash size cannot exceed cache_size * threshold.
        self.cache_size = None
        self.stash_threshold = 0.8


OPTIONS = Options()
DataImage = blockimgdiff.DataImage
