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
