"""Process-local fictional GPU inventory for controller development.

This implements no persistence, credentials, network access or production billing.
B02 supplies the durable controller and a real provider adapter.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Pod:
    id: str
    batch_id: str
    request_key: str


class FakeGpuProvider:
    def __init__(self):
        self._pods = {}
        self._next_id = 1
        self.timeout_after_create = False
        self.fail_next_delete = False

    def create(self, batch_id: str, request_key: str) -> Pod:
        # Real creation can allocate a resource before a client sees a response.
        pod = Pod(f"fake-pod-{self._next_id}", batch_id, request_key)
        self._next_id += 1
        self._pods[pod.id] = pod
        if self.timeout_after_create:
            self.timeout_after_create = False
            raise TimeoutError("Fictional timeout after allocation")
        return pod

    def find(self, batch_id: str, request_key: str) -> list[Pod]:
        return [pod for pod in self._pods.values()
                if pod.batch_id == batch_id and pod.request_key == request_key]

    def get(self, pod_id: str) -> Pod | None:
        return self._pods.get(pod_id)

    def delete(self, pod_id: str) -> None:
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise ConnectionError("Fictional provider deletion failure")
        self._pods.pop(pod_id, None)
