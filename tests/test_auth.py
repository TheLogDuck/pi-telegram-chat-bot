# Backward compatibility tests verifying modules.auth re-exports modules.access_control.
from modules.auth import is_admin, register_access_control, register_auth


def test_auth_backward_compatibility():
    """Verifies that legacy imports from modules.auth still work seamlessly."""
    assert callable(is_admin)
    assert register_auth is register_access_control
