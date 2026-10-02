// Israa_Arduino
// Basic starter sketch: blinks the built-in LED and prints to Serial.

const unsigned long BLINK_INTERVAL_MS = 1000;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
  Serial.println("Israa_Arduino started");
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(BLINK_INTERVAL_MS);
  digitalWrite(LED_BUILTIN, LOW);
  delay(BLINK_INTERVAL_MS);
}
