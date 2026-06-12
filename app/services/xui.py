import json
import random
import string
import time
import uuid as uuid_gen
from urllib.parse import quote

import requests

from app.utils import (
    get_panel_inbound_id,
    get_panel_password,
    get_panel_sub_base_url,
    get_panel_url,
    get_panel_username,
    get_setting,
)


class XUIManager:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = get_panel_url().rstrip("/")
        self.username = get_panel_username()
        self.password = get_panel_password()
        self.inbound_id = get_panel_inbound_id()

        if not self.base_url:
            raise Exception("آدرس پنل تنظیم نشده است.")

    def login(self):
        if not self.username or not self.password:
            return False, "یوزرنیم یا پسورد پنل تنظیم نشده است."

        try:
            response = self.session.post(
                f"{self.base_url}/login",
                data={
                    "username": self.username,
                    "password": self.password,
                },
                timeout=20,
                verify=False,
            )

            if response.status_code not in [200, 204]:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"

            try:
                data = response.json()
                if data.get("success") is False:
                    return False, str(data)
            except Exception:
                pass

            return True, "LOGIN_OK"

        except Exception as e:
            return False, str(e)

    def list_inbounds(self):
        ok, msg = self.login()
        if not ok:
            return False, msg, None

        try:
            response = self.session.get(
                f"{self.base_url}/panel/api/inbounds/list",
                timeout=20,
                verify=False,
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:200]}", None

            data = response.json()
            if not data.get("success"):
                return False, str(data), None

            return True, "OK", data.get("obj", [])

        except Exception as e:
            return False, str(e), None

    def test_connection(self):
        ok, msg, inbounds = self.list_inbounds()
        if not ok:
            return False, msg, 0

        return True, "OK", len(inbounds or [])

    def get_inbound(self):
        ok, msg, inbounds = self.list_inbounds()
        if not ok:
            return False, msg, None

        try:
            inbound_id = int(self.inbound_id)
        except Exception:
            return False, "Inbound ID باید عدد باشد.", None

        for inbound in inbounds or []:
            try:
                if int(inbound.get("id")) == inbound_id:
                    return True, "OK", inbound
            except Exception:
                continue

        return False, f"Inbound ID {inbound_id} پیدا نشد.", None

    def get_panel_clients_map(self):
        ok, msg, inbound = self.get_inbound()
        if not ok or not inbound:
            return False, msg, {}

        try:
            clients_map = {}

            settings_raw = inbound.get("settings", "{}")
            if isinstance(settings_raw, str):
                settings = json.loads(settings_raw or "{}")
            else:
                settings = settings_raw or {}

            for client in settings.get("clients", []):
                email = client.get("email")
                if not email:
                    continue

                clients_map[email] = {
                    "client": client,
                    "stats": None,
                    "up": 0,
                    "down": 0,
                    "total": 0,
                    "enable": client.get("enable", True),
                }

            for stat in inbound.get("clientStats", []):
                email = stat.get("email")
                if not email:
                    continue

                up = int(stat.get("up", 0) or 0)
                down = int(stat.get("down", 0) or 0)

                if email not in clients_map:
                    clients_map[email] = {
                        "client": None,
                        "stats": stat,
                        "up": up,
                        "down": down,
                        "total": up + down,
                        "enable": stat.get("enable", True),
                    }
                else:
                    clients_map[email]["stats"] = stat
                    clients_map[email]["up"] = up
                    clients_map[email]["down"] = down
                    clients_map[email]["total"] = up + down
                    clients_map[email]["enable"] = stat.get(
                        "enable",
                        clients_map[email]["enable"],
                    )

            return True, "OK", clients_map

        except Exception as e:
            return False, str(e), {}

    def get_all_panel_clients_map(self):
        ok, msg, inbounds = self.list_inbounds()
        if not ok:
            return False, msg, {}

        try:
            clients_map = {}

            for inbound in inbounds or []:
                inbound_id = inbound.get("id")

                settings_raw = inbound.get("settings", "{}")
                if isinstance(settings_raw, str):
                    settings = json.loads(settings_raw or "{}")
                else:
                    settings = settings_raw or {}

                for client in settings.get("clients", []):
                    email = client.get("email")
                    sub_id = client.get("subId")

                    item = {
                        "client": client,
                        "stats": None,
                        "inbound_id": inbound_id,
                        "email": email,
                        "sub_id": sub_id,
                        "up": 0,
                        "down": 0,
                        "total": 0,
                        "enable": client.get("enable", True),
                    }

                    if email:
                        clients_map[f"email:{email}"] = item

                    if sub_id:
                        clients_map[f"sub:{sub_id}"] = item

                for stat in inbound.get("clientStats", []):
                    email = stat.get("email")
                    if not email:
                        continue

                    key = f"email:{email}"
                    up = int(stat.get("up", 0) or 0)
                    down = int(stat.get("down", 0) or 0)

                    if key in clients_map:
                        clients_map[key]["stats"] = stat
                        clients_map[key]["up"] = up
                        clients_map[key]["down"] = down
                        clients_map[key]["total"] = up + down
                        clients_map[key]["enable"] = stat.get(
                            "enable",
                            clients_map[key].get("enable", True),
                        )
                    else:
                        clients_map[key] = {
                            "client": None,
                            "stats": stat,
                            "inbound_id": inbound_id,
                            "email": email,
                            "sub_id": None,
                            "up": up,
                            "down": down,
                            "total": up + down,
                            "enable": stat.get("enable", True),
                        }

            return True, "OK", clients_map

        except Exception as e:
            return False, str(e), {}

    def get_client_traffic(self, client_email):
        ok, msg, clients_map = self.get_panel_clients_map()
        if not ok:
            return False, msg, None

        item = clients_map.get(client_email)
        if not item:
            return False, "کلاینت در پنل پیدا نشد.", None

        return True, "OK", {
            "email": client_email,
            "up": int(item.get("up", 0) or 0),
            "down": int(item.get("down", 0) or 0),
            "total": int(item.get("total", 0) or 0),
            "enable": item.get("enable", True),
        }

    def add_client(self, email, limit_gb, expiry_days, service_type="fixed"):
        ok, msg = self.login()
        if not ok:
            return False, msg, None

        try:
            client_uuid = str(uuid_gen.uuid4())
            sub_id = "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(16)
            )

            expiry_time = 0
            if expiry_days and int(expiry_days) > 0:
                expiry_time = int((time.time() + int(expiry_days) * 86400) * 1000)

            total_gb = 0
            if limit_gb and float(limit_gb) > 0:
                total_gb = int(float(limit_gb) * 1024 * 1024 * 1024)

            settings = {
                "clients": [
                    {
                        "id": client_uuid,
                        "flow": "",
                        "email": email,
                        "limitIp": 1,
                        "totalGB": total_gb,
                        "expiryTime": expiry_time,
                        "enable": True,
                        "tgId": "",
                        "subId": sub_id,
                        "reset": 0,
                        "comment": service_type,
                    }
                ]
            }

            payload = {
                "id": int(self.inbound_id),
                "settings": json.dumps(settings),
            }

            response = self.session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                data=payload,
                timeout=20,
                verify=False,
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:300]}", None

            data = response.json()
            if not data.get("success"):
                return False, str(data), None

            sub_base = get_panel_sub_base_url()
            sub_link = f"{sub_base}/{sub_id}"

            result = {
                "uuid": client_uuid,
                "email": email,
                "sub_id": sub_id,
                "sub_link": sub_link,
                "vless_link": None,
            }

            ok_inbound, _, inbound = self.get_inbound()
            if ok_inbound and inbound:
                result["vless_link"] = self.build_vless_link(
                    inbound,
                    client_uuid,
                    email,
                )

            return True, "OK", result

        except Exception as e:
            return False, str(e), None

    def add_trial_client(self, email, limit_gb, expiry_minutes):
        ok, msg = self.login()
        if not ok:
            return False, msg, None

        try:
            client_uuid = str(uuid_gen.uuid4())
            sub_id = "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(16)
            )

            expiry_time = int((time.time() + int(expiry_minutes) * 60) * 1000)
            total_gb = int(float(limit_gb) * 1024 * 1024 * 1024)

            settings = {
                "clients": [
                    {
                        "id": client_uuid,
                        "flow": "",
                        "email": email,
                        "limitIp": 1,
                        "totalGB": total_gb,
                        "expiryTime": expiry_time,
                        "enable": True,
                        "tgId": "",
                        "subId": sub_id,
                        "reset": 0,
                        "comment": "instant_trial",
                    }
                ]
            }

            payload = {
                "id": int(self.inbound_id),
                "settings": json.dumps(settings),
            }

            response = self.session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                data=payload,
                timeout=20,
                verify=False,
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:300]}", None

            data = response.json()
            if not data.get("success"):
                return False, str(data), None

            sub_base = get_panel_sub_base_url()
            sub_link = f"{sub_base}/{sub_id}"

            result = {
                "uuid": client_uuid,
                "email": email,
                "sub_id": sub_id,
                "sub_link": sub_link,
                "vless_link": None,
            }

            ok_inbound, _, inbound = self.get_inbound()
            if ok_inbound and inbound:
                result["vless_link"] = self.build_vless_link(
                    inbound,
                    client_uuid,
                    email,
                )

            return True, "OK", result

        except Exception as e:
            return False, str(e), None

    def disable_client(self, client_email):
        ok, msg, inbound = self.get_inbound()
        if not ok or not inbound:
            return False, msg

        try:
            settings_raw = inbound.get("settings", "{}")
            if isinstance(settings_raw, str):
                settings = json.loads(settings_raw or "{}")
            else:
                settings = settings_raw or {}

            target_client = None
            for client in settings.get("clients", []):
                if client.get("email") == client_email:
                    client["enable"] = False
                    target_client = client
                    break

            if not target_client:
                return False, "کلاینت داخل settings پیدا نشد."

            client_uuid = target_client.get("id")

            payload = {
                "id": int(self.inbound_id),
                "settings": json.dumps({"clients": [target_client]}),
            }

            response = self.session.post(
                f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}",
                data=payload,
                timeout=20,
                verify=False,
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:300]}"

            data = response.json()
            if not data.get("success"):
                return False, str(data)

            return True, "OK"

        except Exception as e:
            return False, str(e)

    def build_vless_link(self, inbound, client_uuid, email):
        try:
            if inbound.get("protocol", "vless") != "vless":
                return None

            port = inbound.get("port")
            stream_settings_raw = inbound.get("streamSettings", "{}")

            if isinstance(stream_settings_raw, str):
                stream_settings = json.loads(stream_settings_raw or "{}")
            else:
                stream_settings = stream_settings_raw or {}

            network = stream_settings.get("network", "tcp")
            security = stream_settings.get("security", "none")

            host = get_setting("panel_vless_host", "")
            if not host:
                host = (
                    get_panel_url()
                    .replace("https://", "")
                    .replace("http://", "")
                    .split("/")[0]
                    .split(":")[0]
                )

            params = {
                "type": network,
                "encryption": "none",
                "security": security,
            }

            if network == "ws":
                ws_settings = stream_settings.get("wsSettings", {})
                params["path"] = ws_settings.get("path", "/")
                headers = ws_settings.get("headers", {})
                if headers.get("Host"):
                    params["host"] = headers.get("Host")

            elif network == "xhttp":
                xhttp_settings = stream_settings.get("xhttpSettings", {})
                params["path"] = xhttp_settings.get("path", "/")
                params["mode"] = xhttp_settings.get("mode", "auto")

            elif network == "grpc":
                grpc_settings = stream_settings.get("grpcSettings", {})
                if grpc_settings.get("serviceName"):
                    params["serviceName"] = grpc_settings.get("serviceName")

            if security == "tls":
                tls_settings = stream_settings.get("tlsSettings", {})
                if tls_settings.get("serverName"):
                    params["sni"] = tls_settings.get("serverName")

            if security == "reality":
                reality_settings = stream_settings.get("realitySettings", {})
                server_names = reality_settings.get("serverNames", [])
                short_ids = reality_settings.get("shortIds", [])
                public_key = reality_settings.get("settings", {}).get("publicKey", "")

                if server_names:
                    params["sni"] = server_names[0]
                if short_ids:
                    params["sid"] = short_ids[0]
                if public_key:
                    params["pbk"] = public_key
                params["fp"] = "chrome"

            query = "&".join(
                f"{quote(str(k))}={quote(str(v))}"
                for k, v in params.items()
                if v is not None and str(v) != ""
            )

            return f"vless://{client_uuid}@{host}:{port}?{query}#{quote(str(email))}"

        except Exception as e:
            print("BUILD VLESS ERROR:", e)
            return None
