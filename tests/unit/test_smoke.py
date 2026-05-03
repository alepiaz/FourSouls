def test_smoke_import():
    import foursouls
    assert isinstance(foursouls.__version__, str)