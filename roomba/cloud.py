import logging

import requests

log = logging.getLogger(__name__)

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
        log.info("Paso 1/4: descubriendo endpoints (país=%s)...", self.country)
        response = self.http.get(
            DISCOVERY_URL, params={"country_code": self.country}, timeout=15
        )
        response.raise_for_status()
        data = response.json()
        current = data["current_deployment"]
        deployment = data["deployments"][current]
        disco = {
            "http_base": deployment["httpBase"],
            "region": deployment["awsRegion"],
            "mqtt": deployment.get("mqttAts") or deployment["mqtt"],
            "irbt_topics": deployment["irbtTopics"],
            "deployment": current,
            "gigya_key": data["gigya"]["api_key"],
            "gigya_domain": data["gigya"]["datacenter_domain"],
        }
        log.info("Paso 1/4 OK: deployment=%s", disco["deployment"])
        return disco

    def _gigya_login(self, email: str, password: str, key: str, domain: str) -> dict:
        log.info("Paso 2/4: login Gigya (%s)...", email)
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
            log.error("Gigya rechazó el login: %s", payload)
            raise LoginError(
                payload.get("errorDetails")
                or payload.get("errorMessage")
                or "Autenticación fallida"
            )
        log.info("Paso 2/4 OK")
        return {
            "uid": payload["UID"],
            "signature": payload["UIDSignature"],
            "timestamp": payload["signatureTimestamp"],
        }

    def _account_login(self, http_base: str, gigya: dict) -> dict:
        log.info("Paso 3/4: login en la API de iRobot...")
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
        if response.status_code >= 400:
            log.error("/v2/login devolvió HTTP %s: %s", response.status_code, response.text[:500])
            raise LoginError(
                f"El servidor de iRobot rechazó el login (HTTP {response.status_code}). "
                "Comprueba email y contraseña, y que el robot esté dado de alta en la app oficial."
            )
        payload = response.json()
        robots = payload.get("robots") or {}
        log.info("Paso 3/4 OK: %d robot(s) en la cuenta: %s",
                 len(robots), ", ".join(f"{v.get('name', b)} [{b}]" for b, v in robots.items()) or "(ninguno)")
        return payload

    def login(self, email: str, password: str, discovery: dict | None = None) -> dict:
        disco = discovery or self.discover()
        gigya = self._gigya_login(email, password, disco["gigya_key"], disco["gigya_domain"])
        account = self._account_login(disco["http_base"], gigya)
        log.info("Paso 4/4: conexión MQTT (se realiza al conectar con el robot)")
        account["_discovery"] = disco
        return account
