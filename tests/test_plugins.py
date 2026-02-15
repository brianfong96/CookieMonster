from cookie_monster.plugins import auto_detect_adapter, get_adapter, list_adapters


def test_list_adapters_contains_builtins():
    names = list_adapters()
    assert "github" in names
    assert "gmail" in names
    assert "supabase" in names


def test_auto_detect_supabase():
    adapter = auto_detect_adapter("https://supabase.com/dashboard/project/abc")
    assert adapter is not None
    assert adapter.name == "supabase"


def test_get_adapter_defaults():
    adapter = get_adapter("github")
    defaults = adapter.defaults()
    assert "github.com" in defaults.allowed_domains
