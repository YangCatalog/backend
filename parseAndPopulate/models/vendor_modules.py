import typing as t
from dataclasses import dataclass

VendorPlatformData = t.TypedDict(
    'VendorPlatformData',
    {
        'software-flavor': str,
        'platform': str,
        'software-version': str,
        'os-version': str,
        'feature-set': str,
        'os': str,
        'vendor': str,
    },
)


@dataclass
class VendorInfo:
    platform_data: list[VendorPlatformData]
    conformance_type: t.Optional[str]
    capabilities: list[str]
    netconf_versions: list[str]
