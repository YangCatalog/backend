import typing as t

_UserFields = t.TypedDict(
    '_UserFields',
    {
        'username': str,
        'password': str,
        'email': str,
        'models-provider': str,
        'first-name': str,
        'last-name': str,
        'registration-datetime': str,
    },
)

_TempUserFields = t.TypedDict(
    '_TempUserFields',
    {
        'motivation': str,
    },
)

_ApprovedUserFields = t.TypedDict(
    '_ApprovedUserFields',
    {
        'access-rights-sdo': str,
        'access-rights-vendor': str,
    },
)


class TempUserFields(_UserFields, _TempUserFields):
    pass


class ApprovedUserFields(_UserFields, _ApprovedUserFields):
    pass
