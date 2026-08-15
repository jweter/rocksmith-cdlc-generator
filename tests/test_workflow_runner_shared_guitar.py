import pytest

from rocksmith_cdlc_generator.workflow_runner import _planner_command_argv


def test_runner_allows_only_bounded_shared_guitar_entrypoint() -> None:
    argv = _planner_command_argv(
        'cdlc-build-shared-guitar "C:\\Projects\\Song" --instrument lead'
    )
    assert argv[0] == "cdlc-build-shared-guitar"
    assert argv[-2:] == ["--instrument", "lead"]


def test_runner_still_rejects_unapproved_external_entrypoint() -> None:
    with pytest.raises(ValueError, match="not an approved automatic"):
        _planner_command_argv('powershell "C:\\Projects\\Song"')
