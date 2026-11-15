"""Runpod REST v1 transport. The controller owns all create retry decisions."""
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.wan_platform.fake_provider import Pod


_ABSENT = object()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RunpodProvider:
    def __init__(self, token, *, launch_profile=None, transport=None):
        if not token:
            raise ValueError("Runpod token is required")
        self._token = token
        self._profile = launch_profile
        self._transport = transport or build_opener(NoRedirect()).open

    def _request(self, method, path, data=None):
        request = Request(
            "https://rest.runpod.io/v1" + path,
            data=None if data is None else json.dumps(data).encode(),
            headers={"Authorization": "Bearer " + self._token,
                     "Content-Type": "application/json"},
            method=method,
        )
        try:
            with self._transport(request, timeout=15) as response:
                if method == "DELETE":
                    if response.status != 204:
                        raise ConnectionError("Unexpected Runpod delete response")
                    return
                return json.load(response)
        except HTTPError as error:
            error.close()
            if error.code == 404 and path.startswith("/pods/") and method in ("GET", "DELETE"):
                return _ABSENT
            raise ConnectionError(f"Runpod request failed with HTTP {error.code}") from None
        except (URLError, OSError, ValueError):
            raise ConnectionError("Runpod transport or response failure") from None

    @staticmethod
    def _name(batch_id, request_key):
        key = json.dumps([batch_id, request_key]).encode()
        return "wan-" + hashlib.sha256(key).hexdigest()[:40]

    @staticmethod
    def _id(record):
        if isinstance(record, dict) and isinstance(record.get("id"), str) and record["id"]:
            return record["id"]
        raise ConnectionError("Runpod response is missing a Pod ID")

    def create(self, batch_id, request_key):
        if self._profile is None:
            raise ConnectionError("Runpod launch profile is unavailable")
        record = self._request("POST", "/pods", {
            **self._profile,
            "name": self._name(batch_id, request_key),
            "computeType": "GPU",
            "gpuCount": 1,
        })
        return Pod(self._id(record), batch_id, request_key)

    def find(self, batch_id, request_key):
        inventory = self._request("GET", "/pods")
        if not isinstance(inventory, list):
            raise ConnectionError("Unexpected Runpod inventory response")
        name = self._name(batch_id, request_key)
        matches = []
        for record in inventory:
            pod_id = self._id(record)
            if not isinstance(record.get("name"), str):
                raise ConnectionError("Runpod inventory record is missing its name")
            if record["name"] == name:
                matches.append(Pod(pod_id, batch_id, request_key))
        return matches

    def get(self, pod_id):
        record = self._request("GET", "/pods/" + quote(pod_id, safe=""))
        if record is _ABSENT:
            return None
        if self._id(record) != pod_id:
            raise ConnectionError("Runpod response returned a different Pod ID")
        return record

    def delete(self, pod_id):
        self._request("DELETE", "/pods/" + quote(pod_id, safe=""))

