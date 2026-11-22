import pytest
from lib.entrypoint import exit_on_error


@pytest.mark.parametrize("rc", [0, None])
def test_exit_on_error_does_not_raise_on_success(rc):
    exit_on_error(rc)


def test_exit_on_error_raises_system_exit_on_failure():
    with pytest.raises(SystemExit) as excinfo:
        exit_on_error(2)
    assert excinfo.value.code == 2
