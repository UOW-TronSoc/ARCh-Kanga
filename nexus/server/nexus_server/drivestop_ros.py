"""One read-only subscription to the global /drivestop topic."""

from __future__ import annotations

from nexus_server.drivestop import DrivestopStore

DRIVESTOP_TOPIC = "/drivestop"
DRIVESTOP_HISTORY = "keep_last"
DRIVESTOP_DEPTH = 1
DRIVESTOP_RELIABILITY = "reliable"
DRIVESTOP_DURABILITY = "transient_local"


def configure_drivestop(node: object, store: DrivestopStore) -> None:
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import Bool

    qos = QoSProfile(
        history={"keep_last": HistoryPolicy.KEEP_LAST}[DRIVESTOP_HISTORY],
        depth=DRIVESTOP_DEPTH,
        reliability={"reliable": ReliabilityPolicy.RELIABLE}[DRIVESTOP_RELIABILITY],
        durability={"transient_local": DurabilityPolicy.TRANSIENT_LOCAL}[DRIVESTOP_DURABILITY],
    )

    def on_drivestop(message: Bool) -> None:
        store.observe(bool(message.data), node.count_publishers(DRIVESTOP_TOPIC))

    def poll_publishers() -> None:
        store.set_publisher_count(node.count_publishers(DRIVESTOP_TOPIC))

    node.create_subscription(Bool, DRIVESTOP_TOPIC, on_drivestop, qos)
    node.create_timer(0.2, poll_publishers)

    from sensor_msgs.msg import JointState

    mode_topic = "/core/drive_manager/closed_loop"

    def on_mode(message: Bool) -> None:
        store.observe_mode(bool(message.data), node.count_publishers(mode_topic))

    def poll_mode() -> None:
        store.set_mode_publisher_count(node.count_publishers(mode_topic))

    node.create_subscription(Bool, mode_topic, on_mode, qos)
    node.create_timer(0.2, poll_mode)

    def on_wheels(message: JointState) -> None:
        wheels = []
        for index, name in enumerate(message.name):
            if index >= len(message.velocity):
                continue
            velocity = float(message.velocity[index])
            if velocity != velocity:  # NaN
                continue
            wheels.append((str(name), velocity))
        if wheels:
            store.observe_wheels(wheels)

    node.create_subscription(JointState, "/core/wheel_joint_states", on_wheels, 10)
