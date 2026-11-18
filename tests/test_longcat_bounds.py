"""Fictional deadline, independent cleanup and process-group failure checks."""
import signal
import subprocess
import unittest
from unittest.mock import Mock, patch

from deployment.longcat_guard import validate, watch
from workers.gpu.longcat_bootstrap import bounded_process


class LongCatBoundsTests(unittest.TestCase):
    name='wan-longcat-song-0123456789abcdef'

    def test_original_deadline_cannot_be_extended_or_expired(self):
        validate(self.name,1000,5800,4000)
        for name,start,end,now in [(self.name,1000,5801,4000),
                (self.name,1000,5800,5800),(self.name,1001,5800,1000),
                ('wan-longcat-20261117-012345abcdef',1000,1500,1000)]:
            with self.assertRaises(ValueError):validate(name,start,end,now)

    def test_guard_paginates_and_deletes_only_exact_name_at_original_deadline(self):
        now=[1000];calls=[];present=[True]
        def request(method,path):
            calls.append((now[0],method,path))
            if method=='DELETE':present[0]=False;return
            if path=='/pods':return dict(pods=[dict(id='other',name=self.name+'x')],
                                       pagination=dict(hasNextPage=True,nextCursor='a+b/c'))
            self.assertEqual(path,'/pods?cursor=a%2Bb%2Fc')
            return dict(pods=[dict(id='match',name=self.name)] if present[0] else [],
                        pagination=dict(hasNextPage=False))
        watch(self.name,1000,1100,request,clock=lambda:now[0],
              pause=lambda seconds:now.__setitem__(0,now[0]+seconds),emit=lambda *a,**k:None)
        deletes=[c for c in calls if c[1]=='DELETE']
        self.assertEqual(deletes,[(1070,'DELETE','/pods/match')])
        self.assertEqual(now[0],1280)

    def test_guard_requires_complete_initial_inventory_and_verified_cleanup(self):
        repeated=lambda *a:dict(pods=[],pagination=dict(hasNextPage=True,nextCursor='repeat'))
        with self.assertRaises(ValueError):watch(self.name,1000,1100,repeated,clock=lambda:1000)
        now=[1000]
        def unavailable(method,path):
            if now[0]>=1070:raise OSError('fictional provider outage')
            return dict(pods=[],pagination=dict(hasNextPage=False))
        with self.assertRaises(SystemExit):watch(self.name,1000,1100,unavailable,
            clock=lambda:now[0],pause=lambda s:now.__setitem__(0,now[0]+s),emit=lambda *a,**k:None)

    def test_bootstrap_timeout_terminates_whole_group_and_does_not_restart(self):
        process=Mock(pid=12345)
        process.wait.side_effect=[subprocess.TimeoutExpired('fixture',165),
                                  subprocess.TimeoutExpired('fixture',5),0]
        with patch('workers.gpu.longcat_bootstrap.time.time',return_value=1000), \
             patch('workers.gpu.longcat_bootstrap.subprocess.Popen',return_value=process) as popen, \
             patch('workers.gpu.longcat_bootstrap.os.killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):bounded_process(['fixture'],1200,log=None)
            popen.assert_called_once()
            self.assertTrue(popen.call_args.kwargs['start_new_session'])
            self.assertEqual(kill.call_args_list[0].args,(12345,signal.SIGTERM))
            self.assertEqual(kill.call_args_list[1].args,(12345,signal.SIGKILL))
        with patch('workers.gpu.longcat_bootstrap.time.time',return_value=1100), \
             patch('workers.gpu.longcat_bootstrap.subprocess.Popen') as popen:
            with self.assertRaises(ValueError):bounded_process(['fixture'],1200,log=None)
            popen.assert_not_called()


if __name__=='__main__':unittest.main()
