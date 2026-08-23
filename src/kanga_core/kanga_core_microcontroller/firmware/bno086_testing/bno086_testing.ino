#include <Wire.h>

// Change these if you are using non-default ESP32 I2C pins
#define SDA_PIN 21
#define SCL_PIN 22

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("I2C Scanner");

    Wire.begin(SDA_PIN, SCL_PIN);
}

void loop()
{
    byte error;
    byte address;
    int devices = 0;

    Serial.println("Scanning...");

    for (address = 1; address < 127; address++)
    {
        Wire.beginTransmission(address);
        error = Wire.endTransmission();

        if (error == 0)
        {
            Serial.print("I2C device found at address 0x");

            if (address < 16)
                Serial.print("0");

            Serial.println(address, HEX);
            devices++;
        }
        else if (error == 4)
        {
            Serial.print("Unknown error at address 0x");

            if (address < 16)
                Serial.print("0");

            Serial.println(address, HEX);
        }
    }

    if (devices == 0)
        Serial.println("No I2C devices found.");
    else
        Serial.println("Scan complete.");

    Serial.println();

    delay(2000);
}