from rbgyanx_engine.run_config import RunConfig


def test_enable_ml_defaults_false():
    assert RunConfig().enable_ml is False
