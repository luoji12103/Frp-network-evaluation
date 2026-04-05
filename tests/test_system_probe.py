from probes.system_probe import get_load_average_for_platform


def test_windows_load_average_is_marked_unsupported() -> None:
    averages, metadata = get_load_average_for_platform("windows")
    assert averages == (None, None, None)
    assert metadata["load_average"] == "unsupported_on_windows"
