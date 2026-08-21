import plainletter


def test_package_exposes_a_version() -> None:
    assert isinstance(plainletter.__version__, str)
    assert plainletter.__version__.count(".") == 2
