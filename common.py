import sys

import blockimgdiff


class Options(object):
    def __init__(self):
        platform_search_path = {
            "linux2": "out/host/linux-x86",
            "darwin": "out/host/darwin-x86",
        }

        self.search_path = platform_search_path.get(sys.platform, None)
        self.signapk_path = "framework/signapk.jar"  # Relative to search_path
        self.signapk_shared_library_path = "lib64"  # Relative to search_path
        self.extra_signapk_args = []
        self.java_path = "java"  # Use the one on the path by default.
        self.java_args = ["-Xmx2048m"]  # The default JVM args.
        self.public_key_suffix = ".x509.pem"
        self.private_key_suffix = ".pk8"
        # use otatools built boot_signer by default
        self.boot_signer_path = "boot_signer"
        self.boot_signer_args = []
        self.verity_signer_path = None
        self.verity_signer_args = []
        self.verbose = False
        self.tempfiles = []
        self.device_specific = None
        self.extras = {}
        self.info_dict = None
        self.source_info_dict = None
        self.target_info_dict = None
        self.worker_threads = None
        # Stash size cannot exceed cache_size * threshold.
        self.cache_size = None
        self.stash_threshold = 0.8


OPTIONS = Options()
DataImage = blockimgdiff.DataImage
