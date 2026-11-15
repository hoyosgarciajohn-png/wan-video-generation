"""Versioned Studio envelope stays compatible with bundle contract 0.1.0."""
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


class StudioContractTest(unittest.TestCase):
    def test_versioned_shared_workspace_fixture(self):
        schema = json.loads((ROOT / 'contracts/studio-workspace.schema.json').read_text())
        bundle = json.loads((ROOT / 'contracts/bundle.schema.json').read_text())
        registry = Registry().with_resource('https://wan.local/contracts/bundle.schema.json', Resource.from_contents(bundle))
        validator = Draft202012Validator(schema, registry=registry)
        fixture = json.loads((ROOT / 'fixtures/studio-workspace.json').read_text())
        validator.validate(fixture)
        validator.validate(dict(version=1, revision=0, projects=[]))
