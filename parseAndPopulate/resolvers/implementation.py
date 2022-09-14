from parseAndPopulate.models.implementation import Implementation
from parseAndPopulate.resolvers.resolver import Resolver


class ImplementationResolver(Resolver):
    def __init__(self, vendor_info_dict: dict, features: list, deviations: list) -> None:
        self.vendor_info = vendor_info_dict
        self.features = features
        self.deviations = deviations

    def resolve(self) -> list:
        """
        Parameters from vendor_info_dict:
            platform_data:       (list) list of platform_data loaded from platform_metadata.json
            conformance_type:    (str) string representing conformance type of module
            capabilities:        (list) list of netconf capabilities loaded from platform_metadata.json
            netconf_versions:    (list) list of netconf versions loaded from platform-metadata.json
        
        Other parameters:
            features:            (list) list of features from initializations data for VendorModule
            deviations:          (list) list of deviations from initializations data for VendorModule
        """
        platform_data = self.vendor_info["platform_data"]
        conformance_type = self.vendor_info["conformance_type"]
        capabilities = self.vendor_info["capabilities"]
        netconf_versions = self.vendor_info["netconf_versions"]

        implementations = []
        for data in platform_data:
            implementation = Implementation()
            implementation.vendor = data['vendor']
            implementation.platform = data['platform']
            implementation.software_version = data['software-version']
            implementation.software_flavor = data['software-flavor']
            implementation.os_version = data['os-version']
            implementation.feature_set = data['feature-set']
            implementation.os_type = data['os']
            implementation.feature = self.features
            implementation.capabilities = capabilities
            implementation.netconf_versions = netconf_versions

            for deviation in self.deviations:
                dev = implementation.Deviation()
                dev.name = deviation['name']
                dev.revision = deviation['revision']
                implementation.deviations.append(dev)

            implementation.conformance_type = conformance_type

            implementations.append(implementation)
        return implementations
