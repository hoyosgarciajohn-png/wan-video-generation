"""Lifecycle-to-HTTP adapter rehearsal. All responses and resource IDs are fictional."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from services.controller.lifecycle import Lifecycle
from services.controller.runpod import RunpodProvider


class Reply(io.BytesIO):
    def __init__(self, value=None, status=200):
        super().__init__(b'' if value is None else json.dumps(value).encode())
        self.status = status
        self.headers = {}


PROFILE = {'image':'example/wan@sha256:'+'a'*64,'gpu':{'id':'fictional-gpu','count':1},
           'cloud':'SECURE','disk':50,'dataCenterIds':['fictional-dc'],'mounts':{},'ports':[],'env':{}}


class RunpodHTTPIntegrationTests(unittest.TestCase):
    def test_explicit_rejection_closes_immediately_and_survives_restart_without_retry(self):
        for status in (400,401,402,403,404,409,413,422,429):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as root:
                calls = []
                def transport(request, timeout):
                    calls.append(request.get_method())
                    raise HTTPError(request.full_url,status,'ignored',{'x-request-id':'fictional-rejection'},
                                    io.BytesIO(b'{"detail":"No deployment was accepted"}'))
                provider=RunpodProvider('fictional',launch_profile=PROFILE,scope='project',transport=transport)
                path=Path(root)/'state.sqlite'
                life=Lifecycle(path,provider)
                batch=life.admit('project','one',{},100,0)
                life.provision('project',batch,1)
                restarted=Lifecycle(path,provider)
                row=restarted.status('project',batch)
                self.assertEqual((row['state'],row['cleanup'],row['pod_id']),('failed','confirmed',None))
                self.assertEqual(json.loads(row['create_diagnostic'])['http_status'],status)
                restarted.provision('project',batch,2)
                self.assertEqual(restarted.watchdog(101),[])
                self.assertEqual(calls,['POST'])

    def test_unknown_without_allocation_never_closes_from_empty_inventory(self):
        for status in (408,500):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as root:
                calls=[]
                def transport(request,timeout):
                    calls.append(request.get_method())
                    if request.get_method()=='POST':
                        raise HTTPError(request.full_url,status,'secret',{},io.BytesIO(b'{}'))
                    return Reply({'pods':[],'pagination':{'hasNextPage':False,'nextCursor':None}})
                provider=RunpodProvider('fictional',launch_profile=PROFILE,scope='project',transport=transport)
                path=Path(root)/'state.sqlite'
                life=Lifecycle(path,provider); batch=life.admit('project','one',{},10,0)
                life.provision('project',batch,1)
                life=Lifecycle(path,provider); life.provision('project',batch,2)
                self.assertEqual(life.watchdog(11),[batch])
                row=life.status('project',batch)
                self.assertEqual(row['cleanup'],'failed')
                self.assertEqual(json.loads(row['create_diagnostic'])['outcome'],'unknown')
                self.assertEqual(calls.count('POST'),1)

    def test_ambiguous_create_restart_transient_inventory_and_confirmed_absence(self):
        with tempfile.TemporaryDirectory() as root:
            pods, calls = {}, []
            failing_inventory = [False]
            failing_delete = [True]
            def transport(request, timeout):
                method = request.get_method()
                path = request.full_url.split('/v2',1)[1]
                calls.append((method,path))
                if method == 'POST':
                    payload = json.loads(request.data)
                    pods['fictional-pod'] = dict(id='fictional-pod',name=payload['name'])
                    raise TimeoutError('Synthetic lost create response')
                if path == '/pods':
                    if failing_inventory[0]:
                        raise HTTPError(request.full_url,503,'Synthetic outage',{},io.BytesIO(b'fictional secret body'))
                    return Reply({'pods':list(pods.values()),'pagination':{'hasNextPage':False,'nextCursor':None}})
                if method == 'GET':
                    if 'fictional-pod' in pods:
                        return Reply(pods['fictional-pod'])
                    raise HTTPError(request.full_url,404,'Absent',{},io.BytesIO())
                if method == 'DELETE':
                    if failing_delete[0]:
                        failing_delete[0] = False
                        raise HTTPError(request.full_url,503,'Synthetic transient delete',{},io.BytesIO())
                    pods.clear()
                    return Reply(status=204)
                raise AssertionError('Unexpected request')
            provider = RunpodProvider('fictional-token',launch_profile=PROFILE,scope='fictional-owner/fictional-project',transport=transport)
            path = Path(root)/'state.sqlite'
            lifecycle = Lifecycle(path,provider)
            batch = lifecycle.admit('fictional-project','intent',{},100,0)
            lifecycle.provision('fictional-project',batch,1)
            self.assertEqual(lifecycle.status('fictional-project',batch)['state'],'provisioning')
            lifecycle = Lifecycle(path,provider)
            failing_inventory[0] = True
            lifecycle.provision('fictional-project',batch,2)
            self.assertEqual(sum(method == 'POST' for method,_ in calls),1)
            self.assertEqual(lifecycle.status('fictional-project',batch)['state'],'provisioning')
            failing_inventory[0] = False
            lifecycle.provision('fictional-project',batch,3)
            self.assertEqual(lifecycle.status('fictional-project',batch)['state'],'rendering')
            lifecycle.finish(batch,'succeeded')
            self.assertEqual(lifecycle.watchdog(4),[batch])
            self.assertEqual(lifecycle.status('fictional-project',batch)['cleanup'],'failed')
            self.assertTrue(pods)
            self.assertEqual(lifecycle.watchdog(5),[])
            self.assertEqual(lifecycle.status('fictional-project',batch)['cleanup'],'confirmed')
            self.assertEqual(sum(method == 'POST' for method,_ in calls),1)
            self.assertFalse(pods)

    def test_inventory_failure_never_means_no_resources(self):
        calls = []
        def transport(request,timeout):
            calls.append(request.get_method())
            if request.get_method() == 'POST':
                raise TimeoutError('Unknown allocation')
            raise HTTPError(request.full_url,429,'Synthetic throttling',{},io.BytesIO())
        provider = RunpodProvider('fictional-token',launch_profile=PROFILE,scope='fictional-owner/fictional-project',transport=transport)
        with tempfile.TemporaryDirectory() as root:
            lifecycle = Lifecycle(Path(root)/'state.sqlite',provider)
            batch = lifecycle.admit('fictional-project','intent',{},10,0)
            lifecycle.provision('fictional-project',batch,1)
            lifecycle.cancel('fictional-project',batch)
            self.assertEqual(lifecycle.watchdog(2),[batch])
            self.assertEqual(lifecycle.status('fictional-project',batch)['cleanup'],'failed')
            self.assertEqual(calls.count('POST'),1)
            self.assertNotIn('DELETE',calls)

    def test_cleanup_after_restart_requires_durable_expected_identity(self):
        calls = []
        def transport(request,timeout):
            calls.append((request.get_method(),request.full_url))
            if request.full_url.endswith('/pods'):
                return Reply({'pods':[],'pagination':{'hasNextPage':False,'nextCursor':None}})
            raise HTTPError(request.full_url,404,'Synthetic already deleted',{},io.BytesIO())
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'state.sqlite'
            provider = RunpodProvider('fictional-token',scope='fictional-owner/fictional-project',transport=transport)
            lifecycle = Lifecycle(path,provider)
            batch = lifecycle.admit('fictional-project','intent',{},100,0)
            with lifecycle.transaction() as db:
                db.execute("UPDATE pod_batches SET state='succeeded',pod_id='fictional-pod' WHERE id=?",(batch,))
            self.assertEqual(lifecycle.watchdog(1),[batch])
            self.assertFalse(any(url.endswith('/fictional-pod') for _,url in calls))
            name = provider._name(batch,batch)
            restarted = RunpodProvider('fictional-token',scope='fictional-owner/fictional-project',transport=transport,
                expected_names=lambda pod: name if pod == 'fictional-pod' else None)
            lifecycle = Lifecycle(path,restarted)
            self.assertEqual(lifecycle.watchdog(2),[])
            self.assertEqual(lifecycle.status('fictional-project',batch)['cleanup'],'confirmed')
            self.assertFalse(any(method == 'DELETE' for method,_ in calls))
