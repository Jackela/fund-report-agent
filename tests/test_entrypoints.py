import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import types

ROOT = Path(__file__).resolve().parents[1]


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'fund-report.yaml'
        self.config.write_text('''provider:
  active: aliyun
  aliyun:
    api_key_pass_key: unused/test
profiles:
  dad:
    email: example@example.invalid
  k7407:
    email: other@example.invalid
defaults:
  profile: k7407
  template: weekend_recap
''')
        self.env = {k: v for k, v in os.environ.items() if k not in ['PROFILE', 'TEMPLATE', 'PROVIDER']}
        self.env['FUND_REPORT_CONFIG'] = str(self.config)

    def run_entry(self, entry, **env):
        return subprocess.run([sys.executable, str(ROOT / entry), '--check-config'],
                              cwd=self.temp.name, env={**self.env, **env},
                              capture_output=True, text=True)

    def test_all_compatibility_entries_select_same_config(self):
        for entry in ['run_and_send_pipeline.py', 'src/main.py', 'references/run_and_send_pipeline.py', 'references/src/main.py']:
            with self.subTest(entry=entry):
                result = self.run_entry(entry)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'profile': 'k7407', 'provider': 'aliyun', 'template': 'weekend_recap'})

    def test_environment_selection_overrides_defaults(self):
        result = self.run_entry('run_and_send_pipeline.py', PROFILE='dad', TEMPLATE='ad_hoc')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['profile'], 'dad')
        self.assertEqual(json.loads(result.stdout)['template'], 'ad_hoc')

    def test_unknown_selection_and_missing_config_fail(self):
        self.assertNotEqual(self.run_entry('run_and_send_pipeline.py', PROFILE='unknown').returncode, 0)
        self.config.unlink()
        result = self.run_entry('src/main.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('配置文件不存在', result.stderr)

    def test_check_config_never_reads_credentials_or_imports_data_agent(self):
        from src import config, pipeline
        with patch.object(config, 'CONFIG_FILE', self.config), patch.object(config, '_config_cache', None), \
             patch.dict(os.environ, {'PROFILE': 'dad', 'TEMPLATE': 'ad_hoc', 'PROVIDER': 'aliyun'}), \
             patch.object(config, '_get_pass', side_effect=AssertionError('No credential reads')):
            self.assertEqual(pipeline.main(['--check-config']), 0)
            self.assertNotIn('src.data_agent', sys.modules)

    def test_email_uses_selected_profile_without_smtp(self):
        from src import email_agent
        with patch.object(email_agent, 'get_recipients', return_value=['test@example.invalid']) as recipients, \
             patch.object(email_agent, 'EmailAgent') as agent:
            agent.return_value.run.return_value = True
            self.assertTrue(email_agent.send_fund_report('local fixture', profile='dad'))
            recipients.assert_called_once_with('dad')
            self.assertEqual(agent.return_value.run.call_args.kwargs['to_emails'], ['test@example.invalid'])

    def test_mocked_pipeline_propagates_mail_failure_and_rejects_empty_report(self):
        from src import config, pipeline, registry, email_agent
        data_module = types.ModuleType('src.data_agent')
        data_module.DataAgent = MagicMock()
        data_module.DataAgent.return_value.export_for_research.return_value = 'local fixture data'
        provider = MagicMock()
        provider.research.return_value = 'local report fixture ' * 100
        with patch.object(config, 'CONFIG_FILE', self.config), patch.object(config, '_config_cache', None), \
             patch.dict(os.environ, {'PROFILE': 'dad', 'TEMPLATE': 'ad_hoc', 'PROVIDER': 'aliyun'}), \
             patch.dict(sys.modules, {'src.data_agent': data_module}), \
             patch.object(config, 'get_api_key', return_value='local-test-key'), \
             patch.dict(registry.ProviderRegistry._items, {'aliyun': provider}), \
             patch.object(pipeline, 'OUTPUT_DIR', self.temp.name), \
             patch.object(email_agent, 'send_fund_report', return_value=False) as send:
            self.assertEqual(pipeline.main([]), 1)
            self.assertIn('local report fixture', send.call_args.kwargs['report_html'])
            provider.research.return_value = ''
            send.reset_mock()
            with self.assertRaisesRegex(RuntimeError, 'AI 返回为空'):
                pipeline.main([])
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
