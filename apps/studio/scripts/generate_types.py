"""Generate local TypeScript types from the unchanged shared contract."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[3]
schema = json.loads((root / 'contracts/bundle.schema.json').read_text())
def name(value):
    return ''.join(part.title() for part in value.split('_'))
def convert(item):
    if '$ref' in item:
        return name(item['$ref'].split('/')[-1])
    if 'const' in item:
        return json.dumps(item['const'])
    if 'enum' in item:
        return ' | '.join(json.dumps(v) for v in item['enum'])
    kind = item['type']
    if isinstance(kind, list):
        return ' | '.join(convert({**item, 'type': k}) for k in kind)
    if kind == 'array':
        return 'Array<' + convert(item['items']) + '>'
    if kind == 'object':
        fields = [json.dumps(k) + ('' if k in item.get('required', []) else '?') + ': ' + convert(v) for k,v in item['properties'].items()]
        return '{\n' + ';\n'.join(fields) + '\n}'
    return {'integer':'number', 'number':'number', 'string':'string', 'boolean':'boolean', 'null':'null'}[kind]
output = '// Generated from contracts/bundle.schema.json by scripts/generate_types.py.\n'
for key, item in schema['$defs'].items():
    output += f'export type {name(key)} = {convert(item)};\n'
output += f'export type Bundle = {convert(schema)};\n'
(root/'apps/studio/src/contract.ts').write_text(output)

