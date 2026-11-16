"""One authenticated GET; verifies access, never creates or deletes resources."""
import json
import os
from services.controller.runpod import RunpodProvider, https_transport


def check(token, *, transport):
    provider = RunpodProvider(token, scope='credential-access-check', transport=transport)
    inventory = provider._request('GET', '/pods?limit=1&includeClusterPods=true')
    if (not isinstance(inventory, dict) or not isinstance(inventory.get('pods'), list)
            or not isinstance(inventory.get('pagination'), dict)
            or type(inventory['pagination'].get('hasNextPage')) is not bool):
        raise ValueError('Unexpected inventory shape')
    # Never return provider records: they can contain env values and addresses.
    return {'status': 'AUTHENTICATED_POD_READ_PASS', 'requests': 1,
            'method': 'GET', 'resources_created': 0, 'resources_deleted': 0,
            'deletion_permission_verified': False, 'shutdown_verified': False}


def main():
    try:
        result = check(os.environ['RUNPOD_CLEANUP_TOKEN'], transport=https_transport())
    except Exception:
        print(json.dumps({'status': 'CREDENTIAL_CHECK_FAILED'}), flush=True)
        raise SystemExit(1) from None
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
