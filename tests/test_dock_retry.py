from roomba.robot import DOCK_PHASES, Roomba


class FakeRobot(Roomba):
    def __init__(self, wait_results):
        self.wait_results = list(wait_results)
        self.sent = []

    def send(self, command):
        self.sent.append(command)

    def _wait_for_phase(self, phases, timeout):
        return self.wait_results.pop(0) if self.wait_results else None


def test_dock_succeeds_first_attempt():
    robot = FakeRobot(["hmUsrDock"])
    assert robot.dock_with_retry(attempts=3) is True
    assert robot.sent == ["dock"]


def test_dock_succeeds_after_retry():
    robot = FakeRobot([None, "hmUsrDock"])
    assert robot.dock_with_retry(attempts=3) is True
    assert robot.sent == ["dock", "dock"]


def test_dock_fails_after_all_attempts():
    robot = FakeRobot([None, None, None])
    assert robot.dock_with_retry(attempts=3) is False
    assert robot.sent == ["dock", "dock", "dock"]


def test_dock_accepts_all_return_phases():
    for phase in DOCK_PHASES:
        robot = FakeRobot([phase])
        assert robot.dock_with_retry(attempts=2) is True
