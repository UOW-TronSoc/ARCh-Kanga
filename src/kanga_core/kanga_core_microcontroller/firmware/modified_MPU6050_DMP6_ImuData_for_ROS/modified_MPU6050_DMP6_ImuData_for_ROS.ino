/*
  ESP32 + HW-123 / MPU6050-compatible IMU
  Electronic Cats MPU6050 Library

  ESP32 wiring:
    SDA -> GPIO 21
    SCL -> GPIO 22

  I2C address:
    0x68

  Outputs:
    - Quaternion: w x y z
    - Angular velocity: wx wy wz [rad/s]
    - Linear acceleration: ax ay az [m/s^2]
    - Yaw/Pitch/Roll [degrees]

  NOTE:
    This HW-123 reports WHO_AM_I = 0x72 rather than the
    standard MPU6050 value 0x68.

    Therefore testConnection() fails even though the device
    responds and the DMP initializes successfully.
*/

#include <Wire.h>
#include "I2Cdev.h"
#include "MPU6050_6Axis_MotionApps20.h"

// ------------------------------------------------------------
// Configuration
// ------------------------------------------------------------

#define SDA_PIN 21
#define SCL_PIN 22

#define MPU_ADDRESS 0x68

#define EARTH_GRAVITY_MS2 9.80665f
#define DEG_TO_RAD 0.01745329251994329577f
#define RAD_TO_DEG 57.29577951308232088f

MPU6050 mpu(MPU_ADDRESS);

// ------------------------------------------------------------
// DMP variables
// ------------------------------------------------------------

bool DMPReady = false;

uint8_t devStatus;
uint8_t MPUIntStatus;

uint16_t packetSize;

uint8_t FIFOBuffer[64];

// ------------------------------------------------------------
// Motion data
// ------------------------------------------------------------

// Orientation
Quaternion q;

// Raw accelerometer from DMP packet
VectorInt16 aa;

// Gravity-compensated acceleration
VectorInt16 aaLinear;

// Gyroscope
VectorInt16 gg;

// Gravity vector calculated from quaternion
VectorFloat gravity;

// Yaw, pitch, roll
float ypr[3];

// ------------------------------------------------------------

void setup()
{
  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("========================================");
  Serial.println("HW-123 / MPU6050 DMP Test");
  Serial.println("========================================");

  // ----------------------------------------------------------
  // Start I2C
  // ----------------------------------------------------------

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  delay(100);

  Serial.println();
  Serial.println("Initializing MPU...");

  mpu.initialize();

  // ----------------------------------------------------------
  // Read device identification
  // ----------------------------------------------------------

  uint8_t deviceID = mpu.getDeviceID();

  Serial.print("Library Device ID: 0x");

  if (deviceID < 0x10)
    Serial.print("0");

  Serial.println(deviceID, HEX);

  // Read raw WHO_AM_I register directly
  Wire.beginTransmission(MPU_ADDRESS);
  Wire.write(0x75);

  uint8_t i2cStatus = Wire.endTransmission(false);

  if (i2cStatus == 0)
  {
    Wire.requestFrom(MPU_ADDRESS, 1);

    if (Wire.available())
    {
      uint8_t whoAmI = Wire.read();

      Serial.print("Raw WHO_AM_I:     0x");

      if (whoAmI < 0x10)
        Serial.print("0");

      Serial.println(whoAmI, HEX);
    }
  }
  else
  {
    Serial.println("ERROR: Could not read WHO_AM_I.");
  }

  // ----------------------------------------------------------
  // Library connection test
  //
  // Your clone reports an unsupported ID, so failure here
  // is treated only as a warning.
  // ----------------------------------------------------------

  if (mpu.testConnection())
  {
    Serial.println("MPU testConnection(): PASS");
  }
  else
  {
    Serial.println("MPU testConnection(): FAIL");
    Serial.println("WARNING: Continuing because this board");
    Serial.println("appears to use MPU6050-compatible clone silicon.");
  }

  // ----------------------------------------------------------
  // Initialize DMP
  // ----------------------------------------------------------

  Serial.println();
  Serial.println("Initializing DMP...");

  devStatus = mpu.dmpInitialize();

  if (devStatus != 0)
  {
    Serial.print("ERROR: DMP initialization failed. Code: ");
    Serial.println(devStatus);

    Serial.println("Halting.");

    while (true)
    {
      delay(1000);
    }
  }

  Serial.println("DMP initialization successful.");

  // ----------------------------------------------------------
  // Reset offsets before calibration
  // ----------------------------------------------------------

  mpu.setXGyroOffset(0);
  mpu.setYGyroOffset(0);
  mpu.setZGyroOffset(0);

  // mpu.setXAccelOffset(0);
  // mpu.setYAccelOffset(0);
  // mpu.setZAccelOffset(0);

  // ----------------------------------------------------------
  // Calibration
  //
  // KEEP THE SENSOR COMPLETELY STILL HERE.
  // ----------------------------------------------------------

  Serial.println();
  Serial.println("Calibrating.");
  Serial.println("KEEP THE SENSOR COMPLETELY STILL...");

  delay(1000);

  // mpu.CalibrateAccel(6);
  mpu.CalibrateGyro(6);

  Serial.println();
  Serial.println("Calibration complete.");
  Serial.println("Active offsets:");

  mpu.PrintActiveOffsets();

  // ----------------------------------------------------------
  // Enable DMP
  // ----------------------------------------------------------

  Serial.println();
  Serial.println("Enabling DMP...");

  mpu.setDMPEnabled(true);

  MPUIntStatus = mpu.getIntStatus();

  packetSize = mpu.dmpGetFIFOPacketSize();

  Serial.print("DMP packet size: ");
  Serial.println(packetSize);

  DMPReady = true;

  Serial.println();
  Serial.println("DMP READY");
  Serial.println();
}

// ------------------------------------------------------------

void loop()
{
  if (!DMPReady)
    return;

  // Get most recent complete DMP packet
  if (mpu.dmpGetCurrentFIFOPacket(FIFOBuffer))
  {
    // ========================================================
    // QUATERNION
    // ========================================================

    mpu.dmpGetQuaternion(&q, FIFOBuffer);

    // ========================================================
    // GRAVITY VECTOR
    // ========================================================

    mpu.dmpGetGravity(&gravity, &q);

    // ========================================================
    // LINEAR ACCELERATION
    //
    // aa       = measured acceleration including gravity
    // aaLinear = gravity removed
    //
    // This remains in the SENSOR / BODY frame.
    // ========================================================

    mpu.dmpGetAccel(&aa, FIFOBuffer);

    mpu.dmpGetLinearAccel(
      &aaLinear,
      &aa,
      &gravity
    );

    float ax =
      aaLinear.x *
      mpu.get_acce_resolution() *
      EARTH_GRAVITY_MS2;

    float ay =
      aaLinear.y *
      mpu.get_acce_resolution() *
      EARTH_GRAVITY_MS2;

    float az =
      aaLinear.z *
      mpu.get_acce_resolution() *
      EARTH_GRAVITY_MS2;

    // ========================================================
    // ANGULAR VELOCITY
    //
    // Keep gyro in SENSOR / BODY frame.
    // Convert degrees/sec -> radians/sec.
    // ========================================================

    mpu.dmpGetGyro(&gg, FIFOBuffer);

    float wx =
      gg.x *
      mpu.get_gyro_resolution() *
      DEG_TO_RAD;

    float wy =
      gg.y *
      mpu.get_gyro_resolution() *
      DEG_TO_RAD;

    float wz =
      gg.z *
      mpu.get_gyro_resolution() *
      DEG_TO_RAD;

    // ========================================================
    // YAW / PITCH / ROLL
    //
    // Mainly useful for debugging / visualization.
    //
    // Yaw will drift because there is no magnetometer.
    // ========================================================

    mpu.dmpGetYawPitchRoll(
      ypr,
      &q,
      &gravity
    );

    float yaw =
      ypr[0] * RAD_TO_DEG;

    float pitch =
      ypr[1] * RAD_TO_DEG;

    float roll =
      ypr[2] * RAD_TO_DEG;

    // ========================================================
    // SERIAL OUTPUT
    // ========================================================

    Serial.print("QUAT\t");

    Serial.print(q.w, 6);
    Serial.print("\t");

    Serial.print(q.x, 6);
    Serial.print("\t");

    Serial.print(q.y, 6);
    Serial.print("\t");

    Serial.println(q.z, 6);


    Serial.print("GYRO\t");

    Serial.print(wx, 4);
    Serial.print("\t");

    Serial.print(wy, 4);
    Serial.print("\t");

    Serial.println(wz, 4);


    Serial.print("LIN_ACC\t");

    Serial.print(ax, 4);
    Serial.print("\t");

    Serial.print(ay, 4);
    Serial.print("\t");

    Serial.println(az, 4);


    Serial.print("YPR\t");

    Serial.print(yaw, 2);
    Serial.print("\t");

    Serial.print(pitch, 2);
    Serial.print("\t");

    Serial.println(roll, 2);


    Serial.println();

    // ~20 Hz serial display.
    // The DMP itself can operate considerably faster.
    delay(50);
  }
}