import asyncio
from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api.web import request, json_response, error_response
from .rules import build_rules, inject, revision, settings, validate
from .style import DEFAULT_STYLE


@register('astrbot_plugin_natural_style', 'local', '识君：简短毒舌文风与按 QQ 定制的人物关系', '2.0.1')
class NaturalStylePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._lock = asyncio.Lock()
        base = '/astrbot_plugin_natural_style'
        context.register_web_api(base + '/settings', self.get_settings, ['GET'], '读取识君配置')
        context.register_web_api(base + '/settings', self.save_settings, ['POST'], '保存识君配置')
        context.register_web_api(base + '/preview', self.preview, ['POST'], '预览提示词')

    @filter.on_llm_request(priority=-1000000000)
    async def apply_style(self, event: AstrMessageEvent, req: ProviderRequest):
        if not self.config.get('enabled', True):
            return
        inject(req, self.config, str(event.get_sender_id()), event.get_platform_name())

    async def get_settings(self):
        from astrbot.core.star.star_handler import EventType, star_handlers_registry
        hooks = star_handlers_registry.get_handlers_by_event_type(EventType.OnLLMRequestEvent)
        order = [{'name': h.handler_full_name, 'priority': h.extras_configs.get('priority', 0)} for h in hooks]
        return json_response({'status': 'ok', 'data': {'config': settings(self.config),
                             'revision': revision(self.config), 'default_style': DEFAULT_STYLE,
                             'hook_order': order}})

    async def save_settings(self):
        data = await request.json()
        try:
            if not isinstance(data, dict):
                raise ValueError('请求格式错误')
            clean = validate(data.get('config'))
            async with self._lock:
                if data.get('revision') != revision(self.config):
                    return error_response('配置已在其他页面修改，请重新载入后再保存', status_code=409)
                before = dict(self.config)
                try:
                    self.config.save_config(clean)
                except Exception:
                    self.config.clear()
                    self.config.update(before)
                    return error_response('配置未保存，请检查服务端磁盘及日志后重试', status_code=500)
            return await self.get_settings()
        except ValueError as exc:
            return error_response(str(exc))

    async def preview(self):
        data = await request.json()
        try:
            if not isinstance(data, dict):
                raise ValueError('请求格式错误')
            clean = validate(data.get('config'))
            block, matched = build_rules(clean, str(data.get('qq', '')))
            return json_response({'status': 'ok', 'data': {'prompt': block, 'matched': bool(matched)}})
        except ValueError as exc:
            return error_response(str(exc))
