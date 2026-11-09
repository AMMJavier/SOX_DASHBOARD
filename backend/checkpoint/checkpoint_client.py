import requests
import os


class CheckPointClient:

    def __init__(self, url, username, password):

        self.url = url
        self.username = username
        self.password = password
        self.sid = None
        self.verify_tls = os.getenv("CHECKPOINT_VERIFY_TLS", "false").lower() in ("1", "true", "yes", "on")


    def login(self):

        endpoint = f"{self.url}/web_api/login"

        payload = {
            "user": self.username,
            "password": self.password
        }


        response = requests.post(
            endpoint,
            json=payload,
            verify=self.verify_tls
        )


        response.raise_for_status()

        data = response.json()

        self.sid = data["sid"]

        print("Login Check Point exitoso")

        return self.sid



    def call_api(self, command, payload):

        endpoint = f"{self.url}/web_api/{command}"


        headers = {
            "X-chkp-sid": self.sid,
            "Content-Type": "application/json"
        }


        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            verify=self.verify_tls
        )


        response.raise_for_status()


        return response.json()



    def logout(self):

        endpoint = f"{self.url}/web_api/logout"


        headers = {
            "X-chkp-sid": self.sid
        }


        requests.post(
            endpoint,
            headers=headers,
            verify=self.verify_tls
        )

        print("Sesión cerrada")