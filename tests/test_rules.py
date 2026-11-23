import importlib.util,json
from pathlib import Path
from types import SimpleNamespace
p=Path(__file__).resolve().parents[1]/'rules.py'
s=importlib.util.spec_from_file_location('rules',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
row={'qq':'12345','mode':'inherit','prompt':'沉稳','relation':'朋友','address':'小明','base_id':'base'}
try:m.effective(row);raise AssertionError('uncompiled accepted')
except ValueError:pass
row.update(compiled='完整新人格',compiled_key=m.signature(row))
assert m.effective(row)=='完整新人格'
changed={**row,'prompt':'活泼'}
try:m.effective(changed);raise AssertionError('stale accepted')
except ValueError:pass
examples=[{'role':'assistant','content':'旧人格例句'}]
r=SimpleNamespace(system_prompt='工具规则\n# Persona Instructions\n\n旧人格\n\n当前状态及记忆',prompt='用户原话',contexts=examples+[{'role':'user','content':'真实历史'}])
m.replace_persona(r,{'prompt':'旧人格','_begin_dialogs_processed':examples},'完整新人格')
assert '旧人格' not in r.system_prompt and '当前状态及记忆' in r.system_prompt and r.system_prompt.startswith('工具规则')
assert r.contexts==[{'role':'user','content':'真实历史'}] and r.prompt=='用户原话'
m.replace_persona(r,{'prompt':'旧人格'},'完整新人格');assert r.system_prompt.count('完整新人格')==1
assert m.effective({'mode':'replace','prompt':'替换全文'})=='替换全文'
assert m.match({'relations_json':json.dumps([row])},'99999') is None
assert m.match({'relations_json':json.dumps([row])},'12345','webchat') is None
r=SimpleNamespace(system_prompt='不可识别的旧人格与工具',contexts=[],prompt='用户')
try:m.replace_persona(r,{'prompt':'旧人格'},'新');raise AssertionError('unsafe replace')
except ValueError:pass
assert r.system_prompt=='不可识别的旧人格与工具'
print('PASS: compilation required, stale rejection, scoped replacement, memory/tools/history preserved, examples removed, idempotence, complete replacement, user/platform isolation, unknown boundary safety')
