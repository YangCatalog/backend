import typing as t
from dataclasses import dataclass

from piwikapi.tests.request import FakeRequest
from piwikapi.tracking import PiwikTracker


@dataclass
class MatomoTrackerData:
    def __init__(self, site_url: str, site_id: str, token=''):
        self.site_url = site_url
        self.site_id = site_id
        self.token = token


def get_headers_dict(req) -> dict:
    keys_to_serialize = [
        'HTTP_USER_AGENT',
        'REMOTE_ADDR',
        'HTTP_REFERER',
        'HTTP_ACCEPT_LANGUAGE',
        'SERVER_NAME',
        'PATH_INFO',
        'QUERY_STRING',
    ]
    data = {
        'HTTPS': req.is_secure
    }
    for key in keys_to_serialize:
        if key in req.headers.environ:
            data[key] = req.headers.environ[key]
    return data


def record_analytic(headers: dict, data: MatomoTrackerData, client_ip: t.Optional[str]) -> None:
    """ Send analytics data to Piwik/Matomo """
    # Use "FakeRequest" because we had to serialize the real request
    fake_request = FakeRequest(headers)

    piwik_tracker = PiwikTracker(data.site_id, fake_request)
    piwik_tracker.set_api_url(data.site_url)
    # if data.token:
    #     piwik_tracker.set_token_auth(data.token)
    #     piwik_tracker.set_ip(client_ip)
    visited_url = fake_request.META['PATH_INFO'][:1000]
    piwik_tracker.do_track_page_view(visited_url)