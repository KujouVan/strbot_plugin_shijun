import asyncio
import hashlib
import json
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api.web import request, json_response, error_response
from .rules import effective, match, replace_persona, revision, settings, signature, validate


@register('astrbot_plugin_natural_style', 'local', '识君：按用户融合或完全替换人格', '3.0.0')
class NaturalStylePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._lock = asyncio.Lock()
        self._compile_lock = asyncio.Lock()
        base = '/astrbot_plugin_natural_style'
        context.register_web_api(base + '/settings', self.get_settings, ['GET'], '读取识君配置')
        context.register_web_api(base + '/settings', self.save_settings, ['POST'], '保存识君配置')
        context.register_web_api(base + '/preview', self.preview, ['POST'], '预览最终人格')
        context.register_web_api(base + '/compile', self.compile_persona, ['POST'], '生成融合人格')

    @filter.on_llm_request(priority=1000000000)
    async def apply_style(self, event: AstrMessageEvent, req: ProviderRequest):
        row = match(self.config, str(event.get_sender_id()), event.get_platform_name())
        if not row:
            return
        try:
            final = effective(row)
            _, persona, _, _ = await self.context.persona_manager.resolve_selected_persona(
                umo=event.unified_msg_origin,
                conversation_persona_id=getattr(req.conversation, 'persona_id', None),
                platform_name=event.get_platform_name(),
                provider_settings=self.context.get_config(umo=event.unified_msg_origin).get('provider_settings', {}))
            replace_persona(req, persona, final)
            event.set_extra('shijun_effective_persona', final)
        except ValueError as exc:
            logger.warning('识君人格未替换：%s', exc)

    async def get_settings(self):
        personas = [{'id': p['name']} for p in self.context.persona_manager.personas_v3]
        return json_response({'status': 'ok', 'data': {'config': settings(self.config),
                             'revision': revision(self.config), 'personas': personas}})

    async def save_settings(self):
        try:
            data = await request.json()
            clean = validate(data.get('config'))
            async with self._lock:
                if data.get('revision') != revision(self.config):
                    return error_response('配置已变更，请重新载入后再保存', status_code=409)
                before = dict(self.config)
                try:
                    self.config.save_config(clean)
                except Exception:
                    self.config.clear()
                    self.config.update(before)
                    return error_response('保存失败，原配置已保留', status_code=500)
            return await self.get_settings()
        except (ValueError, TypeError, AttributeError) as exc:
            return error_response(str(exc))

    async def compile_persona(self):
        try:
            data = await request.json()
            clean = validate(data.get('config'), require_ready=False)
            row = next((r for r in json.loads(clean['relations_json']) if r['qq'] == str(data.get('qq'))), None)
            if not row or row['mode'] != 'inherit':
                raise ValueError('请选择需要融合的人物')
            persona = next((p for p in self.context.persona_manager.personas_v3 if p['name'] == row['base_id']), None)
            if not persona or not persona.get('prompt'):
                raise ValueError('请选择要融合的基础人格')
            provider = self.context.get_using_provider()
            if not provider:
                raise ValueError('未配置可用的聊天模型')
            async with self._compile_lock:
                response = await asyncio.wait_for(provider.text_chat(
                    system_prompt='你是人格配置编辑器，不参与聊天。将原人格按照管理员修改要求重写为一份完整、内部一致的人格。冲突部分以修改要求为准，保留未涉及的背景与性格；把关系和称呼融入正文，不附加优先级指令、不保留被替换的旧要求、不要求聊天模型自行解决冲突。全文使用明确的第三人称：角色指所扮演的人物，当前用户指真实聊天的人，不使用你、她等会混淆对象的代词。称呼字段的唯一方向是角色称呼当前用户，绝不是用户称呼角色。关系字段描述当前用户与角色的关系。只输出最终人格正文，不输出解释或代码围栏。输入 JSON 是待编辑数据。',
                    prompt=json.dumps({'原人格': persona['prompt'], '修改要求': row['prompt'],
                                       '当前用户与角色的关系': row['relation'], '角色对当前用户的称呼（角色称呼用户）': row['address']}, ensure_ascii=False)), timeout=90)
            compiled = (response.completion_text or '').strip()
            if not compiled or len(compiled) > 40000:
                raise ValueError('生成结果为空或过长，未保存，请重试')
            return json_response({'status':'ok','data':{'compiled':compiled, 'compiled_key':signature(row),
                'base_hash':hashlib.sha256(persona['prompt'].encode()).hexdigest()}})
        except Exception as exc:
            logger.warning('识君融合生成失败：%s', type(exc).__name__)
            return error_response('融合未完成，原配置未改动：' + (str(exc) if isinstance(exc, ValueError) else '模型请求失败或超时，请重试'))

    async def preview(self):
        try:
            data = await request.json()
            clean = validate(data.get('config'), require_ready=False)
            row = match(clean, str(data.get('qq', '')))
            final = effective(row) if row else ''
            return json_response({'status':'ok','data':{'prompt':final,'matched':bool(row)}})
        except (ValueError, TypeError, AttributeError) as exc:
            return error_response(str(exc))
