import typing as t


class Implementation:
    def __init__(self):
        self.vendor: t.Optional[str] = None
        self.platform: t.Optional[str] = None
        self.software_version: t.Optional[str] = None
        self.software_flavor: t.Optional[str] = None
        self.os_version: t.Optional[str] = None
        self.feature_set: t.Optional[str] = None
        self.os_type: t.Optional[str] = None
        self.feature = []
        self.deviations = []
        self.conformance_type: t.Optional[str] = None
        self.capabilities = []
        self.netconf_versions = []

    class Deviation:
        def __init__(self):
            self.name: t.Optional[str] = None
            self.revision: t.Optional[str] = None
            self.schema: t.Optional[str] = None
