from roomba.robot import Roomba


class PrefixRobot(Roomba):
    def __init__(self, irbt_topics, state, robot_depl_id=None):
        self.irbt_topics = irbt_topics
        self._state = state
        self.robot_depl_id = robot_depl_id

    def snapshot(self):
        return self._state


def test_prefix_realigned_from_shadow():
    robot = PrefixRobot(
        "v005-irbthbu",
        {"svcEndpoints": {"svcDeplId": "v011"}},
    )
    robot._align_topic_prefix()
    assert robot.irbt_topics == "v011-irbthbu"


def test_prefix_kept_when_matching():
    robot = PrefixRobot(
        "v011-irbthbu",
        {"svcEndpoints": {"svcDeplId": "v011"}},
    )
    robot._align_topic_prefix()
    assert robot.irbt_topics == "v011-irbthbu"


def test_prefix_falls_back_to_login_info():
    robot = PrefixRobot("v005-irbthbu", {}, robot_depl_id="v011")
    robot._align_topic_prefix()
    assert robot.irbt_topics == "v011-irbthbu"


def test_prefix_unchanged_without_deployment_info():
    robot = PrefixRobot("v005-irbthbu", {})
    robot._align_topic_prefix()
    assert robot.irbt_topics == "v005-irbthbu"


def test_deployment_from_robot_info_variants():
    assert Roomba._deployment_from_robot_info({"svc_deployment_id": "v011"}) == "v011"
    assert Roomba._deployment_from_robot_info({"svcDeplId": "v011"}) == "v011"
    assert Roomba._deployment_from_robot_info({"svcEndpoints": {"svcDeplId": "v011"}}) == "v011"
    assert Roomba._deployment_from_robot_info({}) is None
