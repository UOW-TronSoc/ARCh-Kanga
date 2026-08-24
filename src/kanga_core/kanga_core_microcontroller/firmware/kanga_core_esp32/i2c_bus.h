#pragma once

// Shared I2C bus for the MPU6050 and AS5600. Both FreeRTOS tasks run on core 1
// and must take the bus lock around Wire transactions.

void i2cBusBegin();
bool i2cBusConfigured();
void i2cBusLock();
void i2cBusUnlock();

class I2cBusLock
{
public:
  I2cBusLock()
  {
    i2cBusLock();
  }

  ~I2cBusLock()
  {
    i2cBusUnlock();
  }

  I2cBusLock(const I2cBusLock &) = delete;
  I2cBusLock &operator=(const I2cBusLock &) = delete;
};
