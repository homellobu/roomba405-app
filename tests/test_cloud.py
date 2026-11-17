import pytest

from roomba.cloud import IRobotCloud


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)


def test_discovery_parses_endpoints():
    cloud = IRobotCloud(country="ES")
    cloud.http = FakeHTTP([
        FakeResponse({
            "current_deployment": "prod",
            "deployments": {
                "prod": {
                    "httpBase": "https://api.irobotapi.com",
                    "awsRegion": "us-east-1",
                    "mqttAts": "mqtt.example.com",
                    "irbtTopics": "v011-irbthbu",
                }
            },
            "gigya": {"api_key": "key123", "datacenter_domain": "gigya.com"},
        })
    ])
    disco = cloud.discover()
    assert disco["http_base"] == "https://api.irobotapi.com"
    assert disco["mqtt"] == "mqtt.example.com"
    assert disco["irbt_topics"] == "v011-irbthbu"
    assert disco["gigya_key"] == "key123"


def test_gigya_login_failure_raises():
    cloud = IRobotCloud(country="ES")
    cloud.http = FakeHTTP([
        FakeResponse({"statusCode": 403, "errorDetails": "invalid login"})
    ])
    with pytest.raises(Exception, match="invalid login"):
        cloud._gigya_login("a@b.c", "pw", "key", "gigya.com")


def test_login_chain_builds_session():
    cloud = IRobotCloud(country="ES")
    cloud.http = FakeHTTP([
        FakeResponse({
            "current_deployment": "prod",
            "deployments": {
                "prod": {
                    "httpBase": "https://api.irobotapi.com",
                    "awsRegion": "us-east-1",
                    "mqttAts": "mqtt.example.com",
                    "irbtTopics": "v011-irbthbu",
                }
            },
            "gigya": {"api_key": "key123", "datacenter_domain": "gigya.com"},
        }),
        FakeResponse({"statusCode": 200, "UID": "u1", "UIDSignature": "sig", "signatureTimestamp": "123"}),
        FakeResponse({"iot_token": "tok", "robots": {}}),
    ])
    session = cloud.login("a@b.c", "pw")
    assert session["iot_token"] == "tok"
    assert session["_discovery"]["irbt_topics"] == "v011-irbthbu"
    method, url, kwargs = cloud.http.calls[2]
    assert method == "POST"
    assert url == "https://api.irobotapi.com/v2/login"
    assert kwargs["json"]["gigya"]["uid"] == "u1"
