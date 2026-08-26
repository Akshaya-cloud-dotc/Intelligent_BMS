/*
  AI-PBMS Arduino Uno R4 WiFi Hardware Watchdog
  --------------------------------------------
  This sketch runs on the Arduino Uno R4 WiFi connected via USB to the Raspberry Pi.
  It uses the onboard 12x8 LED Matrix to display the state of the Pi:
  - ECG Waveform (STATE_RUN)      -> Pi is healthy, Flask server is active, and Bluetooth BMS is connected.
  - Scrolling "HOLD" (STATE_HOLD) -> Pi is healthy and Flask is running, but Bluetooth BMS is disconnected.
  - Flatline (STATE_OFFLINE)      -> Heartbeat missing, software crashed, or PI_OFFLINE sent. Triggers reset.
  - Centered Blink (STATE_WAITING_BOOT) -> Waiting for initial Pi heartbeat after boot.
  
  Wiring Required:
  1. Connect Arduino Pin 7 (RESET_PIN) to the Raspberry Pi's J2 / PWR_BTN pads (Pin 1).
  2. Connect Arduino GND to one of the Raspberry Pi's GND pins.
*/

#include "Arduino_LED_Matrix.h"
#include "WDT.h"

// Define Pins and Timeouts
const int RESET_PIN = 7;                 // Set to 7 to enable reset, or -1 to disable for testing
const unsigned long TIMEOUT_MS = 10000;     // 10 seconds timeout before triggering reset
const unsigned long HEARTBEAT_MS = 2000;    // Send heartbeat every 2 seconds
const unsigned long BOOT_WAIT_MS = 45000;   // Wait 45 seconds for Pi to boot up after reset

ArduinoLEDMatrix matrix;

enum SystemState {
  STATE_WAITING_BOOT,
  STATE_RUN,
  STATE_HOLD,
  STATE_OFFLINE
};

SystemState currentState = STATE_WAITING_BOOT;
unsigned long lastPiHeartbeat = 0;
unsigned long lastSentHeartbeat = 0;
unsigned long lastDisplayUpdate = 0;
const unsigned long DISPLAY_INTERVAL = 100; // Update display every 100ms
int displayShift = 0;
bool piAlive = false;
bool watchdogActive = true; // Actively monitor Pi boot right from power-on

// ECG pattern vertical position data (row 0 to 7) for 12 columns
const int ecgData[12] = {4, 4, 3, 4, 5, 1, 6, 4, 3, 4, 4, 4}; // baseline on row 4

// 8x18 bitmap of "HOLD" text with some trailing spacing
const byte holdBitmap[8][18] = {
  {0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0},
  {1,0,1,0, 1,1,1,0, 1,0,0,0, 1,1,0,0, 0,0}, // H, O, L, D
  {1,0,1,0, 1,0,1,0, 1,0,0,0, 1,0,1,0, 0,0},
  {1,1,1,0, 1,0,1,0, 1,0,0,0, 1,0,1,0, 0,0},
  {1,0,1,0, 1,0,1,0, 1,0,0,0, 1,0,1,0, 0,0},
  {1,0,1,0, 1,1,1,0, 1,1,1,0, 1,1,0,0, 0,0},
  {0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0},
  {0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0}
};

void setup() {
  Serial.begin(9600);   // USB Serial connection to PC (for local debugging)
  Serial1.begin(9600);  // Hardware Serial connection to Raspberry Pi (over Pins 0/1)
  
  matrix.begin(); // Initialize the 12x8 LED Matrix
  
  // Start with Reset Pin as INPUT (floating) so we don't trigger reset
  if (RESET_PIN != -1) {
    pinMode(RESET_PIN, INPUT); 
  }
  
  lastPiHeartbeat = millis();

  // Initialize hardware watchdog timer (WDT) on Uno R4 WiFi
  if (!WDT.begin(5000)) {
    Serial.println("Error: Failed to initialize hardware WDT!");
  } else {
    WDT.refresh();
    Serial.println("Hardware WDT initialized successfully.");
  }
}

void loop() {
  WDT.refresh(); // Refresh Arduino internal watchdog timer
  unsigned long now = millis();
  
  // 1. Send heartbeat to Pi
  if (now - lastSentHeartbeat >= HEARTBEAT_MS) {
    Serial1.println("ARDUINO_ALIVE");
    Serial.println("Sent heartbeat: ARDUINO_ALIVE"); // debug to PC
    lastSentHeartbeat = now;
  }
  
  // 2. Read heartbeat and state from Pi
  while (Serial1.available() > 0) {
    String line = Serial1.readStringUntil('\n');
    line.trim();
    
    Serial.print("Received from Pi: "); // debug to PC
    Serial.println(line);
    
    if (line == "PI_RUN") {
      lastPiHeartbeat = now; // Reset timeout
      if (currentState == STATE_WAITING_BOOT || currentState == STATE_OFFLINE || currentState == STATE_HOLD) {
        currentState = STATE_RUN;
        piAlive = true;
        if (RESET_PIN != -1) {
          pinMode(RESET_PIN, INPUT); // Ensure reset pin is floating
        }
      }
      if (!watchdogActive) {
        watchdogActive = true;
        Serial1.println("WATCHDOG_ACTIVATED");
        Serial.println("Watchdog activated acknowledgment sent to Pi.");
      }
    } 
    else if (line == "PI_HOLD") {
      lastPiHeartbeat = now; // Reset timeout
      if (currentState == STATE_WAITING_BOOT || currentState == STATE_OFFLINE || currentState == STATE_RUN) {
        currentState = STATE_HOLD;
        piAlive = true;
        if (RESET_PIN != -1) {
          pinMode(RESET_PIN, INPUT); // Ensure reset pin is floating
        }
      }
      if (!watchdogActive) {
        watchdogActive = true;
        Serial1.println("WATCHDOG_ACTIVATED");
        Serial.println("Watchdog activated acknowledgment sent to Pi.");
      }
    } 
    else if (line == "PI_OFFLINE") {
      currentState = STATE_OFFLINE;
      piAlive = false;
      // Loop execution will immediately catch this and trigger the reset below
    }
  }
  
  // 3. Check for Pi Timeout & Trigger Hardware Reset (if watchdog is activated)
  if (watchdogActive) {
    unsigned long currentTimeout = (currentState == STATE_WAITING_BOOT) ? BOOT_WAIT_MS : TIMEOUT_MS;
    if (currentState == STATE_OFFLINE || (now - lastPiHeartbeat > currentTimeout)) {
      currentState = STATE_OFFLINE;
      piAlive = false;
      
      Serial.println("PI_CRASH_DETECTED_TRIGGERING_RESET");
      Serial1.println("PI_RESET_TRIGGERED"); // notify Pi
      
      // --- RASPBERRY PI 5 POWER BUTTON CYCLE ---
      if (RESET_PIN != -1) {
        Serial.println("FORCE SHUTDOWN: Holding power pin LOW for 5.5 seconds...");
        pinMode(RESET_PIN, OUTPUT);
        digitalWrite(RESET_PIN, LOW); 
        
        // Hold LOW for 5.5 seconds to force hard shutdown
        unsigned long shutdownStart = millis();
        while (millis() - shutdownStart < 5500) {
          WDT.refresh(); // Keep Arduino watchdog fed during wait
          delay(10);
        }
        
        // Release pin to float high for 1.5 seconds
        pinMode(RESET_PIN, INPUT);
        unsigned long releaseStart = millis();
        while (millis() - releaseStart < 1500) {
          WDT.refresh();
          delay(10);
        }
        
        // Pulse LOW for 200ms to boot the Pi back up
        Serial.println("BOOT UP: Pulsing power pin LOW for 200ms...");
        pinMode(RESET_PIN, OUTPUT);
        digitalWrite(RESET_PIN, LOW);
        delay(200);
        pinMode(RESET_PIN, INPUT); // Release to let it boot
      } else {
        Serial.println("RESET PIN IS DISABLED (RESET_PIN = -1). NO HARDWARE TRIGGER SENT.");
      }
      
      // Wait for the Pi to boot back up (displaying slow blink, or breaking early on heartbeat)
      currentState = STATE_WAITING_BOOT;
      unsigned long bootStart = millis();
      bool bootedEarly = false;
      while (millis() - bootStart < BOOT_WAIT_MS) {
        WDT.refresh(); // Refresh Arduino watchdog timer inside the blocking boot loop!
        unsigned long nowFlash = millis();
        drawWaitingBoot(nowFlash);
        
        // Check if Pi sent an early heartbeat during boot sequence
        while (Serial1.available() > 0) {
          String line = Serial1.readStringUntil('\n');
          line.trim();
          if (line == "PI_RUN" || line == "PI_HOLD") {
            bootedEarly = true;
            if (line == "PI_RUN") {
              currentState = STATE_RUN;
            } else {
              currentState = STATE_HOLD;
            }
            Serial.print("Pi booted early! Interrupted wait. State: ");
            Serial.println(line);
            break;
          }
        }
        if (bootedEarly) break;
        delay(10);
      }
      
      // Reset timeout timer after boot wait completes
      lastPiHeartbeat = millis();
    }
  }
  
  // 4. Update the 12x8 LED Matrix Display (Non-blocking)
  if (now - lastDisplayUpdate >= DISPLAY_INTERVAL) {
    lastDisplayUpdate = now;
    displayShift++;
    
    switch (currentState) {
      case STATE_WAITING_BOOT:
        drawWaitingBoot(now);
        break;
      case STATE_RUN:
        drawECG(displayShift);
        break;
      case STATE_HOLD:
        drawHold(displayShift);
        break;
      case STATE_OFFLINE:
        drawFlatline();
        break;
    }
  }
}

// Display helper: Centered slow blink
void drawWaitingBoot(unsigned long now) {
  byte frame[8][12] = {0};
  if ((now % 1200) < 600) {
    frame[3][5] = 1; frame[3][6] = 1;
    frame[4][5] = 1; frame[4][6] = 1;
  }
  matrix.renderBitmap(frame, 8, 12);
}

// Display helper: Scrolling ECG Waveform
void drawECG(int shift) {
  byte frame[8][12] = {0};
  for (int col = 0; col < 12; col++) {
    int dataIdx = (col + shift) % 12;
    int row = ecgData[dataIdx];
    frame[row][col] = 1;
    
    // Connect columns vertically to make a solid wave line
    if (col > 0) {
      int prevDataIdx = (col - 1 + shift) % 12;
      int prevRow = ecgData[prevDataIdx];
      int rStart = min(prevRow, row);
      int rEnd = max(prevRow, row);
      for (int r = rStart; r <= rEnd; r++) {
        frame[r][col] = 1;
      }
    }
  }
  matrix.renderBitmap(frame, 8, 12);
}

// Display helper: Scrolling "HOLD" text
void drawHold(int shift) {
  byte frame[8][12] = {0};
  for (int r = 0; r < 8; r++) {
    for (int c = 0; c < 12; c++) {
      int bitmapCol = (c + shift) % 24; // repeat every 24 columns for scrolling pause
      if (bitmapCol < 18) {
        frame[r][c] = holdBitmap[r][bitmapCol];
      } else {
        frame[r][c] = 0;
      }
    }
  }
  matrix.renderBitmap(frame, 8, 12);
}

// Display helper: Flatline (crashed state)
void drawFlatline() {
  byte frame[8][12] = {0};
  for (int col = 0; col < 12; col++) {
    frame[4][col] = 1; // Row 4 is baseline
  }
  matrix.renderBitmap(frame, 8, 12);
}