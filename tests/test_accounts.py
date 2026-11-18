import json
from pathlib import Path
import tempfile
import unittest
from services.controller.accounts import Accounts, AuthUnavailable
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from services.controller.http_api import StudioAPI

class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.now=1000.; self.mail=[]
        self.control=ControlService(self.root/'db',self.root/'assets')
        self.accounts=Accounts(self.control,'https://studio.example',clock=lambda:self.now,send=lambda email,url:self.mail.append((email,url)))
        self.accounts.provision('alice@example.test','original-owner')
        self.api=StudioAPI(StudioWorkspace(self.control),{'a'*40:'original-owner'},'https://studio.example',accounts=self.accounts)
        self.h={'Host':'studio.example','Origin':'https://studio.example','Content-Type':'application/json','X-WAN-Request':'studio'}
    def call(self,path,value):
        return self.api.dispatch('POST','/v1/studio/'+path,self.h,json.dumps(value).encode())
    def reset_link(self):
        self.accounts.recovery('alice@example.test')
        return self.mail[-1][1].split('/')[-1]
    def test_existing_owner_mapping_no_public_claim(self):
        self.assertEqual(self.call('auth/signup',{'email':'alice@example.test','owner':'original-owner'}).status,401)
        self.assertEqual(self.call('session',{'email':'alice@example.test','password':'fictional-passphrase'}).status,401)
        with self.assertRaises(ValueError):self.accounts.provision('alice@example.test','attacker')
        with self.assertRaises(ValueError):self.accounts.provision('other@example.test','original-owner')
        self.accounts.reset(self.reset_link(),'fictional-passphrase')
        r=self.call('session',{'email':'ALICE@example.test','password':'fictional-passphrase'})
        self.assertEqual(self.call('session',{'token':'a'*40}).status,401)
        self.assertEqual(r.data['owner_id'],'original-owner'); self.assertIn('HttpOnly',r.headers['Set-Cookie'])
        reopened=Accounts(self.control,'https://studio.example')
        self.assertEqual(reopened.authenticate('alice@example.test','fictional-passphrase'),'original-owner')
        self.assertIsNone(reopened.authenticate('alice@example.test','incorrect'))
    def test_reset_one_use_expiry_hash_and_revocation(self):
        token=self.reset_link();self.accounts.reset(token,'fictional-passphrase')
        login=self.call('session',{'email':'alice@example.test','password':'fictional-passphrase'})
        with self.assertRaises(ValueError):self.accounts.reset(token,'fictional-passphrase-2')
        token=self.reset_link()
        with self.control.transaction() as db:
            self.assertNotIn(token,str(db.execute('SELECT * FROM studio_recovery').fetchall()))
            self.assertNotIn('fictional-passphrase',str(db.execute('SELECT * FROM studio_accounts').fetchall()))
        self.assertEqual(self.call('auth/reset',{'token':token,'password':'fictional-new-password'}).status,200)
        h={**self.h,'Cookie':login.headers['Set-Cookie'].split(';')[0]}
        self.assertEqual(self.api.dispatch('GET','/v1/studio/session',h).status,401)
        token=self.reset_link();self.now+=1801
        with self.assertRaises(ValueError):self.accounts.reset(token,'fictional-passphrase')
    def test_generic_recovery_csrf_limits_and_failure(self):
        a=self.call('auth/recovery',{'email':'alice@example.test'})
        b=self.call('auth/recovery',{'email':'unknown@example.test'})
        self.assertEqual(a.data,b.data);self.assertEqual(len(self.mail),1)
        h={**self.h,'Origin':'https://evil.example'}
        self.assertEqual(self.api.dispatch('POST','/v1/studio/auth/reset',h,b'{}').status,403)
        for _ in range(8):self.call('auth/recovery',{'email':'unknown@example.test'})
        self.assertEqual(self.call('auth/recovery',{'email':'unknown@example.test'}).status,429)
        self.accounts.send=None
        with self.assertRaises(AuthUnavailable):self.accounts.recovery('alice@example.test')
    def test_mail_failure_invalidates_link(self):
        def fail(*args):raise RuntimeError('secret-provider-detail')
        self.accounts.send=fail
        r=self.call('auth/recovery',{'email':'alice@example.test'})
        self.assertEqual(r.status,503);self.assertNotIn('secret',str(r.data))
        with self.control.transaction() as db:self.assertEqual(db.execute('SELECT count(*) FROM studio_recovery').fetchone()[0],0)
    def test_backup_restore_removes_recovery_capabilities(self):
        from services.controller.backup import create_backup,restore_backup
        self.api.studio.create('original-owner','Fictional','music_video',0)
        token=self.reset_link()
        create_backup(self.control.db_path,self.control.asset_root,self.root/'backup')
        r=restore_backup(self.root/'backup',self.root/'restore')
        a=Accounts(ControlService(r['database'],r['assets']),'https://studio.example',clock=lambda:self.now)
        with self.assertRaises(ValueError):a.reset(token,'fictional-passphrase')
