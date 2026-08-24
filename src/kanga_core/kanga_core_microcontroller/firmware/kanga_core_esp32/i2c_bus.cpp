#include "i2c_bus.h"

#include <Arduino.h>
#include <Wire.h>

#include "pin_config.h"

namespace
{

SemaphoreHandle_t gI2cMutex = nullptr;
bool gBegun = false;

}  // namespace

bool i2cBusConfigured()
{
  return kI2cSdaPin >= 0 && kI2cSclPin >= 0;
}

void i2cBusBegin()
{
  if (gI2cMutex == nullptr)
  {
    gI2cMutex = xSemaphoreCreateMutex();
  }

  if (!i2cBusConfigured() || gBegun)
  {
    return;
  }

  Wire.begin(kI2cSdaPin, kI2cSclPin);
  Wire.setClock(400000);
  delay(100);
  gBegun = true;
}

void i2cBusLock()
{
  if (gI2cMutex != nullptr)
  {
    xSemaphoreTake(gI2cMutex, portMAX_DELAY);
  }
}

void i2cBusUnlock()
{
  if (gI2cMutex != nullptr)
  {
    xSemaphoreGive(gI2cMutex);
  }
}
