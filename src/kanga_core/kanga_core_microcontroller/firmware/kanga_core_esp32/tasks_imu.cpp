#include "tasks_imu.h"

#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <string.h>

#include "I2Cdev.h"
#include "MPU6050_6Axis_MotionApps20.h"
#include "can_bus.h"
#include "i2c_bus.h"
#include "kanga_core_microcontroller/can_ids.hpp"
#include "kanga_core_microcontroller/can_protocol.hpp"
#include "pin_config.h"

using namespace kanga_core_microcontroller;

namespace
{

constexpr uint32_t kImuPublishPeriodMs = 20;  // 50 Hz
constexpr float kEarthGravityMs2 = 9.80665f;
constexpr float kDegToRad = 0.01745329251994329577f;

void publishImuOrientation(float qw, float qx, float qy, float qz)
{
  ImuOrientationFrame payload = {};
  payload.qw = floatToInt16(qw, kQuatScale);
  payload.qx = floatToInt16(qx, kQuatScale);
  payload.qy = floatToInt16(qy, kQuatScale);
  payload.qz = floatToInt16(qz, kQuatScale);

  CanFrame frame = {};
  frame.identifier = CAN_ID_IMU_ORIENTATION;
  frame.extd = 0;
  frame.data_length_code = sizeof(payload);
  memcpy(frame.data, &payload, sizeof(payload));

  if (!canBusWrite(frame))
  {
    return;
  }
}

void publishImuAngularVelocity(uint8_t sequence, float wx, float wy, float wz)
{
  ImuAngularVelocityFrame payload = {};
  payload.sequence = sequence;
  payload.wx = floatToInt16(wx, kGyroScale);
  payload.wy = floatToInt16(wy, kGyroScale);
  payload.wz = floatToInt16(wz, kGyroScale);

  CanFrame frame = {};
  frame.identifier = CAN_ID_IMU_ANGULAR_VEL;
  frame.extd = 0;
  frame.data_length_code = sizeof(payload);
  memcpy(frame.data, &payload, sizeof(payload));

  if (!canBusWrite(frame))
  {
    return;
  }
}

void publishImuLinearAccel(uint8_t sequence, float ax, float ay, float az)
{
  ImuLinearAccelFrame payload = {};
  payload.sequence = sequence;
  payload.ax = floatToInt16(ax, kAccelScale);
  payload.ay = floatToInt16(ay, kAccelScale);
  payload.az = floatToInt16(az, kAccelScale);

  CanFrame frame = {};
  frame.identifier = CAN_ID_IMU_LINEAR_ACCEL;
  frame.extd = 0;
  frame.data_length_code = sizeof(payload);
  memcpy(frame.data, &payload, sizeof(payload));

  if (!canBusWrite(frame))
  {
    return;
  }
}

// Generates deterministic sine-based motion for bench testing without hardware.
void generateEmulatedImuSample(
  float t,
  float &qw, float &qx, float &qy, float &qz,
  float &wx, float &wy, float &wz,
  float &ax, float &ay, float &az)
{
  const float yaw = 0.35f * sinf(t * 0.25f);
  const float pitch = 0.10f * sinf(t * 0.50f);
  const float roll = 0.05f * sinf(t * 0.33f);

  const float cy = cosf(yaw * 0.5f);
  const float sy = sinf(yaw * 0.5f);
  const float cp = cosf(pitch * 0.5f);
  const float sp = sinf(pitch * 0.5f);
  const float cr = cosf(roll * 0.5f);
  const float sr = sinf(roll * 0.5f);

  qw = cr * cp * cy + sr * sp * sy;
  qx = sr * cp * cy - cr * sp * sy;
  qy = cr * sp * cy + sr * cp * sy;
  qz = cr * cp * sy - sr * sp * cy;

  wx = 0.20f * cosf(t * 0.40f);
  wy = 0.15f * sinf(t * 0.55f);
  wz = 0.10f * cosf(t * 0.30f);

  ax = 0.30f * sinf(t * 0.80f);
  ay = 0.20f * cosf(t * 0.60f);
  az = 9.81f + 0.10f * sinf(t * 0.45f);
}

bool initMpu6050(MPU6050 &mpu, uint16_t &packetSize)
{
  Serial.println("Initializing MPU6050...");

  uint8_t dmpStatus = 0;
  {
    I2cBusLock lock;
    mpu.initialize();

    const uint8_t deviceId = mpu.getDeviceID();
    Serial.printf("MPU6050 library device ID: 0x%02X\n", deviceId);

    Wire.beginTransmission(kMpu6050I2cAddress);
    Wire.write(0x75);
    const uint8_t i2cStatus = Wire.endTransmission(false);
    if (i2cStatus == 0)
    {
      Wire.requestFrom(static_cast<uint16_t>(kMpu6050I2cAddress), static_cast<uint8_t>(1));
      if (Wire.available())
      {
        const uint8_t whoAmI = Wire.read();
        Serial.printf("MPU6050 raw WHO_AM_I: 0x%02X\n", whoAmI);
      }
    }
    else
    {
      Serial.println("MPU6050 WHO_AM_I read failed");
      return false;
    }

    if (mpu.testConnection())
    {
      Serial.println("MPU6050 testConnection(): PASS");
    }
    else
    {
      Serial.println("MPU6050 testConnection(): FAIL");
      Serial.println("Continuing: HW-123 clones may report an unsupported ID");
    }

    dmpStatus = mpu.dmpInitialize();
    if (dmpStatus != 0)
    {
      Serial.printf("MPU6050 DMP initialization failed: %u\n", dmpStatus);
      return false;
    }

    mpu.setXGyroOffset(0);
    mpu.setYGyroOffset(0);
    mpu.setZGyroOffset(0);
  }

  Serial.println("Calibrating MPU6050 gyro; keep the sensor still...");
  delay(1000);
  {
    I2cBusLock lock;
    mpu.CalibrateGyro(6);
    Serial.println("MPU6050 gyro calibration complete");
    mpu.PrintActiveOffsets();

    mpu.setDMPEnabled(true);
    packetSize = mpu.dmpGetFIFOPacketSize();
  }
  Serial.printf("MPU6050 DMP ready, packet size %u\n", packetSize);
  return true;
}

bool readMpu6050Sample(
  MPU6050 &mpu,
  uint8_t *fifoBuffer,
  float &qw, float &qx, float &qy, float &qz,
  float &wx, float &wy, float &wz,
  float &ax, float &ay, float &az)
{
  {
    I2cBusLock lock;
    if (!mpu.dmpGetCurrentFIFOPacket(fifoBuffer))
    {
      return false;
    }
  }

  Quaternion q;
  VectorInt16 rawAccel;
  VectorInt16 linearAccel;
  VectorInt16 gyro;
  VectorFloat gravity;

  mpu.dmpGetQuaternion(&q, fifoBuffer);
  mpu.dmpGetGravity(&gravity, &q);
  mpu.dmpGetAccel(&rawAccel, fifoBuffer);
  mpu.dmpGetLinearAccel(&linearAccel, &rawAccel, &gravity);
  mpu.dmpGetGyro(&gyro, fifoBuffer);

  qw = q.w;
  qx = q.x;
  qy = q.y;
  qz = q.z;

  const float gyroResolution = mpu.get_gyro_resolution();
  const float accelResolution = mpu.get_acce_resolution();

  wx = gyro.x * gyroResolution * kDegToRad;
  wy = gyro.y * gyroResolution * kDegToRad;
  wz = gyro.z * gyroResolution * kDegToRad;

  ax = linearAccel.x * accelResolution * kEarthGravityMs2;
  ay = linearAccel.y * accelResolution * kEarthGravityMs2;
  az = linearAccel.z * accelResolution * kEarthGravityMs2;
  return true;
}

void runEmulatedImuTask()
{
  Serial.println("MPU6050 I2C not configured; publishing emulated IMU samples");

  uint8_t sequence = 0;
  const uint32_t startMs = millis();

  for (;;)
  {
    const float t = (millis() - startMs) / 1000.0f;

    float qw = 0.0f;
    float qx = 0.0f;
    float qy = 0.0f;
    float qz = 0.0f;
    float wx = 0.0f;
    float wy = 0.0f;
    float wz = 0.0f;
    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    generateEmulatedImuSample(t, qw, qx, qy, qz, wx, wy, wz, ax, ay, az);

    publishImuOrientation(qw, qx, qy, qz);
    publishImuAngularVelocity(sequence, wx, wy, wz);
    publishImuLinearAccel(sequence, ax, ay, az);

    sequence++;
    vTaskDelay(pdMS_TO_TICKS(kImuPublishPeriodMs));
  }
}

void runMpu6050ImuTask()
{
  MPU6050 mpu(kMpu6050I2cAddress);
  uint16_t packetSize = 0;
  if (!initMpu6050(mpu, packetSize))
  {
    Serial.println("MPU6050 init failed; falling back to emulated IMU samples");
    runEmulatedImuTask();
    return;
  }

  uint8_t fifoBuffer[64];
  uint8_t sequence = 0;

  for (;;)
  {
    float qw = 0.0f;
    float qx = 0.0f;
    float qy = 0.0f;
    float qz = 0.0f;
    float wx = 0.0f;
    float wy = 0.0f;
    float wz = 0.0f;
    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;

    if (readMpu6050Sample(mpu, fifoBuffer, qw, qx, qy, qz, wx, wy, wz, ax, ay, az))
    {
      publishImuOrientation(qw, qx, qy, qz);
      publishImuAngularVelocity(sequence, wx, wy, wz);
      publishImuLinearAccel(sequence, ax, ay, az);
      sequence++;
    }

    vTaskDelay(pdMS_TO_TICKS(kImuPublishPeriodMs));
  }
}

void vImuTask(void *pvParameters)
{
  (void)pvParameters;

  if (!i2cBusConfigured())
  {
    runEmulatedImuTask();
    return;
  }

  runMpu6050ImuTask();
}

}  // namespace

void startImuTask()
{
  xTaskCreatePinnedToCore(
    vImuTask,
    "imu",
    8192,
    nullptr,
    2,
    nullptr,
    1);
}
