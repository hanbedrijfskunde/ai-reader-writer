from app.config import load_settings


def test_load_settings_reads_env_file(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("ANTHROPIC_API_KEY=dummy-value\nDEFAULT_MODEL=claude-haiku-4-5\n")
    settings = load_settings(env_file=env, data_dir=tmp_path / "data")
    assert settings.anthropic_key == "dummy-value"
    assert settings.default_model == "claude-haiku-4-5"
    assert settings.db_path == tmp_path / "data" / "reader.sqlite"


def test_load_settings_defaults_model_when_absent(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("ANTHROPIC_API_KEY=dummy-value\n")
    settings = load_settings(env_file=env, data_dir=tmp_path / "data")
    assert settings.default_model == "claude-sonnet-4-6"
