"""
Smoke tests to verify basic application integrity.
Ensures that all modules can be imported without errors.
"""
import sys
import unittest
import importlib

class TestSmoke(unittest.TestCase):
    def test_import_main(self):
        """Test that tockerdui.main can be imported successfully."""
        try:
            import tockerdui.main
        except ImportError as e:
            self.fail(f"Failed to import tockerdui.main: {e}")

    def test_import_main_actions(self):
        """Test that tockerdui.main_actions can be imported successfully."""
        try:
            import tockerdui.main_actions
        except ImportError as e:
            self.fail(f"Failed to import tockerdui.main_actions: {e}")

    def test_import_backend(self):
        """Test that tockerdui.backend can be imported successfully."""
        try:
            import tockerdui.backend
        except ImportError as e:
            self.fail(f"Failed to import tockerdui.backend: {e}")
            
    def test_import_ui(self):
        """Test that tockerdui.ui can be imported successfully."""
        try:
            import tockerdui.ui
        except ImportError as e:
            self.fail(f"Failed to import tockerdui.ui: {e}")

if __name__ == '__main__':
    unittest.main()
