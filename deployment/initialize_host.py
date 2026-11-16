"""Initialize cleanup tables without installing signing keys or paid transport."""
import json
import os
from deployment.hosted_app import open_control
from services.controller.live_admission import LiveAdmission
from services.controller.live_execution import LiveExecution
from services.controller.studio import StudioWorkspace


def initialize(environment):
    control = open_control(environment)
    admission = LiveAdmission(StudioWorkspace(control))
    LiveExecution(admission)
    return {'initialized': True, 'paid_dispatch': False,
            'approval_keys_installed': False, 'provider_transport_installed': False}


if __name__ == '__main__':
    print(json.dumps(initialize(os.environ)))
