"""Frame names shared by everything that produces or consumes body/pose.

The TF broadcaster throws away any pose stamped with a parent frame it was not
expecting, so whoever publishes the pose and whoever reads it have to agree on
these two names. Keeping them here means a launch-time override moves both ends
together, which separate per-node parameter files could not guarantee.
"""

DEFAULT_BODY_POSE_PARENT_FRAME = "body_origin"
DEFAULT_BODY_POSE_CHILD_FRAME = "base_link"
