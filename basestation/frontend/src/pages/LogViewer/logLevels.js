export const ROS_LOG_DEBUG = 10;
export const ROS_LOG_INFO = 20;
export const ROS_LOG_WARN = 30;
export const ROS_LOG_ERROR = 40;
export const ROS_LOG_FATAL = 50;

const HTTP_LEVEL_VALUES = {
  DEBUG: ROS_LOG_DEBUG,
  INFO: ROS_LOG_INFO,
  WARNING: ROS_LOG_WARN,
  WARN: ROS_LOG_WARN,
  ERROR: ROS_LOG_ERROR,
  CRITICAL: ROS_LOG_FATAL,
  FATAL: ROS_LOG_FATAL,
};

export function http_level_value(name) {
  return HTTP_LEVEL_VALUES[String(name || "").toUpperCase()] ?? ROS_LOG_INFO;
}
