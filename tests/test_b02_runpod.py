import io
import json
import unittest
from urllib.error import HTTPError

from services.controller.runpod import RunpodProvider


class Response(io.BytesIO):
    def __init__(self, status, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = status


class RunpodTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.replies = iter(())
        self.provider = RunpodProvider(
            "fictional-key", launch_profile={"imageName": "fictional-image"},
            transport=self.transport,
        )

    def transport(self, request, timeout):
        self.calls.append((request, timeout))
        status, payload = next(self.replies)
        if status >= 400:
            raise HTTPError(request.full_url, status, "fictional", {}, None)
        return Response(status, payload)

    def test_create_and_inventory_match_exact_launch_name(self):
        name = self.provider._name("batch", "key")
        self.replies = iter([(201, {"id": "pod"}), (200, [
            {"id": "pod", "name": name}, {"id": "other", "name": name + "-other"},
        ])])
        pod = self.provider.create("batch", "key")
        self.assertEqual(self.provider.find("batch", "key"), [pod])
        request, timeout = self.calls[0]
        self.assertEqual(request.full_url, "https://rest.runpod.io/v1/pods")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer fictional-key")
        self.assertGreater(timeout, 0)
        self.assertEqual(json.loads(request.data)["gpuCount"], 1)

    def test_delete_and_verify_404(self):
        self.replies = iter([(204, None), (404, None)])
        self.provider.delete("pod")
        self.assertIsNone(self.provider.get("pod"))
        self.assertEqual([req.get_method() for req, _ in self.calls], ["DELETE", "GET"])

    def test_uncertain_responses_do_not_establish_absence(self):
        self.replies = iter([(403, None), (200, None), (200, {"pods": []}), (500, None)])
        for call in (lambda: self.provider.get("pod"), lambda: self.provider.get("pod"),
                     lambda: self.provider.find("batch", "key"), lambda: self.provider.delete("pod")):
            with self.assertRaises(ConnectionError):
                call()

