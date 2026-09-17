import ast,json
from pathlib import Path
import hcl2,yaml
root=Path(__file__).resolve().parents[1]
for path in (root/'src').rglob('*.py'): ast.parse(path.read_text(encoding='utf-8'))
for path in (root/'infra').glob('*.tf'):
    with path.open() as f: hcl2.load(f)
for path in (root/'dbt').rglob('*.yml'): yaml.safe_load(path.read_text())
yaml.safe_load((root/'compose.yaml').read_text())
json.loads((root/'config.json').read_text())
for name in ['index.html','style.css','app.js']: assert (root/'dashboard'/name).is_file()
print('PASS: Python AST, HCL syntax, YAML, JSON and dashboard entrypoints. Not terraform validate or AWS deployment.')
