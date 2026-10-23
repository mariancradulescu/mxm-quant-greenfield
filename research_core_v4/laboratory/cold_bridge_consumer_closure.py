"""Verify actual cold-workflow bridge installation before any custody key exists.

Derive the missing relative-module closure from current copied Python sources,
then import their actual installed package in the original sealed checkout.
"""
import argparse
import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import yaml

LAB=Path('research_core_v4/laboratory')
COMMAND='python3 -m research_core_v4.laboratory.chronology_csharp_bridge '


def contract(text, source_root, original_modules):
    copies = re.findall(r'cp (research_core_v4/laboratory/\w+\.py) '
                        r'\.sealed-chronology-source/(research_core_v4/laboratory/\w+\.py)', text)
    if not copies or any(a != b for a,b in copies):
        raise ValueError('COLD_BRIDGE_COPY_PATH')
    copied = {Path(a).stem for a,b in copies}
    required={'chronology_csharp_bridge'}
    checked=set()
    while required-checked:
        module=next(iter(required-checked));checked.add(module)
        if module not in copied:
            raise ValueError('MISSING_BRIDGE_DEPENDENCY_'+module)
        tree=ast.parse((Path(source_root)/LAB/(module+'.py')).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.level==1:
                names=[node.module.split('.')[0]] if node.module else [a.name for a in node.names]
                required.update(name for name in names if name not in original_modules)
    config=yaml.safe_load(text)
    triggers=config.get('on',config.get(True,{})).get('push',{}).get('paths',[])
    for module in required | {'durable_native_chronology'}:
        if str(LAB/(module+'.py')) not in triggers:
            raise ValueError('MISSING_BRIDGE_PUSH_TRIGGER_'+module)
    if 'python3 -m research_core_v4.laboratory.durable_native_chronology --out verification/r3-chronology' not in text:
        raise ValueError('MISSING_DURABLE_SOURCE_RESTORE')
    for job in config['jobs'].values():
        for step in job['steps']:
            if step.get('uses','').startswith('actions/download-artifact@') and \
                    step.get('with',{}).get('name')=='r3-chronology-39660692230':
                raise ValueError('EXPIRING_ORIGINAL_SOURCE_DEPENDENCY')
    return copies


def verify(sealed):
    source=Path.cwd();sealed=Path(sealed).resolve()
    original={p.stem for p in (sealed/LAB).glob('*.py')}
    consumers=[]
    for file in sorted(Path('.github/workflows').glob('*.yml')):
        text=file.read_text()
        if COMMAND not in text:continue
        copies=contract(text,source,original)
        for before,after in copies:
            shutil.copyfile(source/before,sealed/after)
        environment=dict(os.environ)
        # The subprocess must resolve modules in the ACTUAL sealed checkout,
        # not borrow a helper from a parent checkout via PYTHONPATH.
        environment.pop('PYTHONPATH',None)
        code=('import pathlib; '
              'import research_core_v4.laboratory.chronology_csharp_bridge as bridge; '
              'import research_core_v4.laboratory.captured_symbol_terms as terms; '
              'root=pathlib.Path.cwd(); '
              'assert pathlib.Path(bridge.__file__).resolve().is_relative_to(root); '
              'assert pathlib.Path(terms.__file__).resolve().is_relative_to(root)')
        subprocess.run([sys.executable,'-c',code],cwd=sealed,env=environment,check=True)
        consumers.append(str(file))
    if len(consumers)<2:raise ValueError('MISSING_COLD_BRIDGE_CONSUMER_INVENTORY')
    print('MXM_ACTUAL_COLD_BRIDGE_CONSUMER_IMPORT_CLOSURE_PASS_NO_KEYS',len(consumers))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('sealed_checkout')
    verify(p.parse_args().sealed_checkout)
