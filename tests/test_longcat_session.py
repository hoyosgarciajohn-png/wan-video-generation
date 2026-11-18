import io
import unittest
import zipfile
from deployment.longcat_session import budget, safe_members, PRIOR_PODS


class ProductionSessionTests(unittest.TestCase):
    def rows(self):
        return [dict(podId=p,totalAmount=2.75,gpuAmount=2.7) for p in PRIOR_PODS]

    def test_budget_preserves_all_spend_reserve_and_both_gpu_hours(self):
        result=budget(self.rows())
        self.assertEqual(result['prior_committed_cents'],825)
        self.assertEqual(result['storage_reserve_cents'],200)
        self.assertLessEqual(result['prior_gpu_seconds']+2*result['rental_seconds'],14400)
        self.assertLessEqual(result['prior_committed_cents']+result['compute_cap_cents']+200,2000)

    def test_missing_negative_or_exhausted_billing_refused(self):
        with self.assertRaises(ValueError):budget(self.rows()[:-1])
        rows=self.rows();rows[0]['totalAmount']=-1
        with self.assertRaises(ValueError):budget(rows)
        rows=self.rows();rows[0]['totalAmount']=19
        with self.assertRaises(ValueError):budget(rows)

    def test_zip_traversal_absolute_symlink_and_duplicate_refused(self):
        for name in ['../escape','/etc/file','bad\\path']:
            with zipfile.ZipFile(io.BytesIO(),mode='w') as archive:
                archive.writestr(name,b'x')
                with self.assertRaises(ValueError):safe_members(archive)
        with zipfile.ZipFile(io.BytesIO(),mode='w') as archive:
            member=zipfile.ZipInfo('link');member.external_attr=0o120777<<16
            archive.writestr(member,'/etc/file')
            with self.assertRaises(ValueError):safe_members(archive)

    def test_known_package_layout_allowed(self):
        with zipfile.ZipFile(io.BytesIO(),mode='w') as archive:
            archive.writestr('inputs/manifest.json','{}');archive.writestr('master/master.wav',b'x')
            self.assertEqual(len(safe_members(archive)),2)


if __name__=='__main__':unittest.main()
