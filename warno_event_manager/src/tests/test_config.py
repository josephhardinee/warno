from unittest import TestCase
import os

from .. import warno_event_manager
from WarnoConfig import config


class TestGet_config_context(TestCase):
    list_required_keys = ['DB_HOST', 'DB_USER', 'DB_NAME']

    def test_data_store_path_defined(self):
        self.assertIsNotNone(os.getenv('DATA_STORE_PATH'), 'DATA_STORE_PATH not set')

    def test_get_config_context_database_entries(self):
        """Test the configuration context"""

        cfg = config.get_config_context()

        for value in self.list_required_keys:
            self.assertIn(value, cfg['database'], 'config context does not contain key:"%s"' % value)

        self.assertIn('DB_PASS', cfg['s_database'], 'config context does not contain key: "DB_PASS"')

    def test_get_config_context_top_level_dicts(self):
        cfg = config.get_config_context()

        self.assertIn('setup', cfg, 'Configuration should have "setup" entry' )
        self.assertIn('type', cfg, 'Configuration should have "type" entry')
