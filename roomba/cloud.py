import requests

DISCOVERY_URL = "https://disc-prod.iot.irobotapi.com/v1/discover/endpoints"
APP_ID = "ANDROID-C7FB240E-DF34-42D7-AE4E-A8C17079A294"
USER_AGENT = "aspen production/4 CFNetwork/1474 Darwin/23.0.0"


class LoginError(RuntimeError):
    pass


class IRobotCloud:
    def __init__(self, country: str = "ES"):
        self.country = country
        self.http = requests.Session()
        self.http.headers["User-Agent"] = USER_AGENT

    def discover(self) -> dict:
        response = self.http.get(
            DISCOVERY_URL, params={"country_code": self.country}, timeout=15
        )
        response.raise_for_status()
        data = response.json()
        current = data["current_deployment"]
        deployment = data["deployments"][current]
        return {
            "http_base": deployment["httpBase"],
            "region": deployment["awsRegion"],
            "mqtt": deployment.get("mqttAts") or deployment["mqtt"],
            "irbt_topics": deployment["irbtTopics"],
            "deployment": current,
            "gigya_key": data["gigya"]["api_key"],
            "gigya_domain": data["gigya"]["datacenter_domain"],
        }

    def _gigya_login(self, email: str, password: str, key: str, domain: str) -> dict:
        response = self.http.post(
            f"https://accounts.{domain}/accounts.login",
            data={
                "apiKey": key,
                "targetEnv": "mobile",
                "loginID": email,
                "password": password,
                "format": "json",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("statusCode") != 200:
            raise LoginError(
                payload.get("errorDetails")
                or payload.get("errorMessage")
                or "Autenticación fallida"
            )
        return {
            "uid": payload["UID"],
            "signature": payload["UIDSignature"],
            "timestamp": payload["signatureTimestamp"],
        }

    def _account_login(self, http_base: str, gigya: dict) -> dict:
        response = self.http.post(
            f"{http_base}/v2/login",
            json={
                "app_id": APP_ID,
                "assume_robot_ownership": "0",
                "gigya": {
                    "signature": gigya["signature"],
                    "timestamp": gigya["timestamp"],
                    "uid": gigya["uid"],
                },
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def login(self, email: str, password: str, discovery: dict | None = None) -> dict:
        disco = discovery or self.discover()
        gigya = self._gigya_login(email, password, disco["gigya_key"], disco["gigya_domain"])
        account = self._account_login(disco["http_base"], gigya)
        account["_discovery"] = disco
        return account
