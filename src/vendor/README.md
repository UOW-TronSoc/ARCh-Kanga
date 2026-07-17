# Vendor repositories

External ROS repositories used by Kanga are imported beneath this structure
folder and remain independently maintained. This folder is not a ROS package.

Use a version-controlled `.repos` manifest and `vcs import` so each dependency
is pinned to an intentional revision. Do not manually copy third-party source
trees into this repository.

The reusable ODrive ROS integration is intended to live in its own repository
and be imported here once that repository and its stable interface exist. It
must remain independent of Kanga-specific packages so other club projects can
reuse it.
