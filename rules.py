import hashlib
import json
import re


def signature(row):
    fields = {k: row.get(k, '') for k in ('qq', 'mode', 'prompt', 'relation', 'address', 'base_id')}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def settings(config):
    return {'enabled': config.get('enabled', True), 'injection_mode': 'system',
            'relations_json': config.get('relations_json', '[]')}


def revision(config):
    return hashlib.sha256(json.dumps(settings(config), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def match(config, sender, platform='aiocqhttp'):
    if not config.get('enabled', True) or platform not in ('aiocqhttp', 'qq_official'):
        return None
    try:
        return next((r for r in json.loads(config.get('relations_json', '[]'))
                     if r.get('enabled', True) and r.get('qq') == str(sender)), None)
    except (ValueError, TypeError, AttributeError):
        return None


def effective(row):
    if row.get('mode') == 'replace':
        text = row.get('prompt', '').strip()
        if not text:
            raise ValueError('完全替换模式需要填写完整人格')
        # These fields are explicit parts of this new persona, never old persona content.
        for key, label in [('relation', '与当前用户的关系'), ('address', '对当前用户的称呼')]:
            if row.get(key):
                text += '\n' + label + '：' + row[key]
        return text
    if row.get('compiled_key') != signature(row) or not row.get('compiled', '').strip():
        raise ValueError('请先生成融合人格，检查结果后保存')
    return row['compiled'].strip()


def validate(data, require_ready=True):
    if not isinstance(data, dict) or type(data.get('enabled')) is not bool:
        raise ValueError('配置格式错误')
    raw = data.get('relations_json', '[]')
    if not isinstance(raw, str) or len(raw) > 4000000:
        raise ValueError('人物配置过大')
    try:
        rows = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError('人物配置不是有效 JSON') from None
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError('人物列表最多 200 人')
    result, seen = [], set()
    limits = dict(qq=20, label=80, relation=500, address=80, prompt=16000,
                  base_id=200, compiled=40000, compiled_key=64, base_hash=64)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('人物条目格式错误')
        item = {}
        for key, limit in limits.items():
            value = row.get(key, '')
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError('字段过长或类型错误：' + key)
            item[key] = value.strip()
        qq = item['qq']
        if not re.fullmatch(r'[1-9][0-9]{4,19}', qq) or qq in seen:
            raise ValueError('QQ 号无效或重复')
        seen.add(qq)
        item['mode'] = row.get('mode', 'inherit')
        if item['mode'] not in ('inherit', 'replace'):
            raise ValueError('人格模式无效')
        item['enabled'] = row.get('enabled', True)
        if type(item['enabled']) is not bool:
            raise ValueError('启用状态无效')
        if require_ready and item['enabled']:
            effective(item)
        result.append(item)
    return {'enabled': data['enabled'], 'injection_mode': 'system',
            'relations_json': json.dumps(result, ensure_ascii=False)}


def replace_persona(req, old_persona, new_prompt):
    old = (old_persona or {}).get('prompt', '')
    system = req.system_prompt or ''
    previous = getattr(req, '_shijun_applied_prompt', None)
    if previous:
        old = previous
    needle = '# Persona Instructions\n\n' + old + '\n'
    if old and system.count(needle) == 1:
        req.system_prompt = system.replace(needle, '# Persona Instructions\n\n' + new_prompt + '\n', 1)
    elif not old and '# Persona Instructions' not in system:
        req.system_prompt = '# Persona Instructions\n\n' + new_prompt + '\n' + system
    else:
        raise ValueError('未找到完整人格边界，保留本次请求，避免覆盖其他插件内容')
    # Original persona example conversations are not the user's actual history.
    examples = (old_persona or {}).get('_begin_dialogs_processed') or []
    if examples and req.contexts[:len(examples)] == examples:
        del req.contexts[:len(examples)]
    try:
        req._shijun_applied_prompt = new_prompt
    except (ValueError, AttributeError):
        pass
