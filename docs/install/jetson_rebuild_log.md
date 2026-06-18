# Jetson / NVIDIA Rebuild Log

Raw lab log template for the upcoming NVIDIA host rebuild. Copy this template per
rebuild and fill it in as you go. Keep it raw and honest; it is a debugging record.

## Device

-

## JetPack version

-

## Ubuntu version

-

## Kernel

-

## Date

-

## Person

-

## Fresh install state

-

## Docker install notes

-

## CAN adapter notes

-

## CAN native test

```
# ./scripts/setup_can.bash can0 500000
# ./scripts/check_can.bash can0
```

-

## Docker CAN test

```
# docker compose -f docker/compose.can-test.yaml build
# docker compose -f docker/compose.can-test.yaml run --rm can-test
#   ip -details link show type can
#   candump can0 -n 10
```

-

## ROS build test

```
# ./scripts/build_workspace.bash
```

-

## Problems encountered

-

## Final verification checklist

- [ ] Docker works
- [ ] Docker Compose works
- [ ] USB-CAN adapter detected
- [ ] can0/can1 exists
- [ ] candump works on host
- [ ] container sees can0/can1
- [ ] candump works inside container
- [ ] workspace builds inside container
