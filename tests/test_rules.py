import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('rules', Path(__file__).parents[1] / 'rules.py')
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)

class PersonaTests(unittest.TestCase):
    def config(self, rows=(), **extra):
        return dict(enabled=True, injection_mode='reinforced', relations_json=json.dumps(rows), **extra)

    def request(self, persona='温柔、详细回答'):
        return SimpleNamespace(system_prompt=persona, prompt='你好', images=['image'], contexts=[{'role':'user','content':'history'}])

    def test_unmatched_preserves_persona_and_other_fields(self):
        req = self.request(); original = vars(req).copy()
        rules.inject(req, self.config(), '12345')
        self.assertEqual(vars(req), original)

    def test_old_global_style_is_ignored(self):
        cfg = self.config(style_prompt='旧版固定毒舌')
        req = self.request(); rules.inject(req, cfg)
        self.assertEqual(req.system_prompt, '温柔、详细回答')
        self.assertNotIn('style_prompt', rules.validate(cfg))
        self.assertNotIn('style_prompt', rules.settings(cfg))

    def test_each_request_uses_its_active_persona(self):
        cfg = self.config([dict(qq='12345', relation='朋友', address='阿林', prompt='耐心', mode='inherit')])
        for persona in ['温柔、详细回答', '严肃、简洁回答']:
            req = self.request(persona); rules.inject(req, cfg, '12345')
            self.assertTrue(req.system_prompt.startswith(persona))
            self.assertIn('阿林', req.system_prompt)
            self.assertNotIn('毒舌', req.system_prompt)

    def test_real_sender_and_platform_only(self):
        cfg = self.config([dict(qq='12345', prompt='专属要求')])
        for sender, platform in [('54321','aiocqhttp'), ('12345','telegram')]:
            self.assertEqual(rules.build_rules(cfg,sender,platform), ('',None))

    def test_repeated_injection_and_disable_cleanup(self):
        cfg = self.config([dict(qq='12345', prompt='专属要求')])
        req = self.request(); rules.inject(req,cfg,'12345'); once = vars(req).copy()
        rules.inject(req,cfg,'12345'); self.assertEqual(vars(req),once)
        cfg['enabled'] = False; rules.inject(req,cfg,'12345')
        self.assertEqual(req.system_prompt, '温柔、详细回答'); self.assertEqual(req.prompt, '你好')

    def test_replace_keeps_persona_and_requires_explicit_prompt(self):
        cfg = self.config([dict(qq='12345', mode='replace', prompt='说话活泼')])
        clean = rules.validate(cfg); req = self.request(); rules.inject(req,clean,'12345')
        self.assertTrue(req.system_prompt.startswith('温柔、详细回答'))
        self.assertIn('说话活泼',req.system_prompt)
        cfg['relations_json'] = json.dumps([dict(qq='12345',mode='replace',prompt='')])
        with self.assertRaises(ValueError): rules.validate(cfg)

    def test_system_mode_does_not_change_user_message(self):
        cfg = self.config([dict(qq='12345',prompt='专属要求')]); cfg['injection_mode']='system'
        req = self.request(); rules.inject(req,cfg,'12345'); self.assertEqual(req.prompt,'你好')

    def test_old_block_removed_when_unmatched(self):
        req = self.request('人格\n\n'+rules.OPEN+'旧文风'+rules.CLOSE)
        req.prompt += '\n\n'+rules.REMINDER+'旧提醒'+rules.END_REMINDER
        rules.inject(req,self.config(),'54321')
        self.assertEqual(req.system_prompt,'人格'); self.assertEqual(req.prompt,'你好')

if __name__ == '__main__': unittest.main()
