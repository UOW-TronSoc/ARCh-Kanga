export const ROS_LOG_DEBUG = 10;
export const ROS_LOG_INFO = 20;
export const ROS_LOG_WARN = 30;
export const ROS_LOG_ERROR = 40;
export const ROS_LOG_FATAL = 50;

export const HTTP_LOG_DEBUG = 10;
export const HTTP_LOG_INFO = 20;
export const HTTP_LOG_WARNING = 30;
export const HTTP_LOG_ERROR = 40;
export const HTTP_LOG_CRITICAL = 50;

export const ROS_LEVEL_OPTIONS = [
  ["DEBUG", ROS_LOG_DEBUG],
  ["INFO", ROS_LOG_INFO],
  ["WARN", ROS_LOG_WARN],
  ["ERROR", ROS_LOG_ERROR],
  ["FATAL", ROS_LOG_FATAL],
];

export const HTTP_LEVEL_OPTIONS = [
  ["DEBUG", HTTP_LOG_DEBUG],
  ["INFO", HTTP_LOG_INFO],
  ["WARNING", HTTP_LOG_WARNING],
  ["ERROR", HTTP_LOG_ERROR],
  ["CRITICAL", HTTP_LOG_CRITICAL],
];

const HTTP_LEVEL_VALUES = {
  DEBUG: HTTP_LOG_DEBUG,
  INFO: HTTP_LOG_INFO,
  WARNING: HTTP_LOG_WARNING,
  WARN: HTTP_LOG_WARNING,
  ERROR: HTTP_LOG_ERROR,
  CRITICAL: HTTP_LOG_CRITICAL,
  FATAL: HTTP_LOG_CRITICAL,
};

export function http_level_value(name) {
  return HTTP_LEVEL_VALUES[String(name || "").toUpperCase()] ?? HTTP_LOG_INFO;
}

export function http_level_name(name) {
  const key = String(name || "INFO").toUpperCase();
  if (key === "WARN") return "WARNING";
  if (key === "FATAL") return "CRITICAL";
  if (HTTP_LEVEL_VALUES[key] != null) return key;
  return "INFO";
}
