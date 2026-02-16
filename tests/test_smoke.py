"""
Smoke tests to verify basic application integrity.
Ensures that all modules can be imported without errors.
"""
import unittest

class TestSmoke(unittest.TestCase):
    def test_import_textual_app(self):
        """Test that tockerdui.textual_app can be imported successfully."""
        try:
            import tockerdui.textual_app
        except ImportError as e:
            self.fail(f"Failed to import tockerdui.textual_app: {e}")

    def test_import_main_module(self):
        """Test that tockerdui.__main__ can be imported successfully."""
        try:
            import tockerdui.__main__
        except ImportError as e:
            self.fail(f"Failed to import tockerdui.__main__: {e}")

    def test_import_backend(self):
        """Test that tockerdui.backend can be imported successfully."""
        try:
            import tockerdui.backend
        except ImportError as e:
            self.fail(f"Failed to import tockerdui.backend: {e}")

if __name__ == '__main__':
    unittest.main()
