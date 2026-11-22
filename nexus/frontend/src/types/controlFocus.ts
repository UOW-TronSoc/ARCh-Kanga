export type ControlTarget =
  | { kind: 'inactive' }
  | { kind: 'drivetrain' }
  | { kind: 'payload'; payloadId: string };