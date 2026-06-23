#include "ecdh.h"

const char broker[] = "test.mosquitto.org";
int        port     = 1883;
const char topic[]  = "acceleration";
const char topic2[] = "heartrate";
const char topic3[] = "heartrate/bpm";
const char topic4[] = "dh/arduino"; // For secret exchange over Diffie Hellman, messages sent by arduino card
const char topic5[] = "dh/ihm";     // Messages sent from HMI


// ----- Diffie-Hellman (ECDH) state -----
uint8_t  dh_private_key[ECC_PRV_KEY_SIZE];
uint8_t  dh_public_key[ECC_PUB_KEY_SIZE];
uint8_t  dh_ihm_public_key[ECC_PUB_KEY_SIZE];
uint8_t  dh_shared_secret[ECC_PUB_KEY_SIZE];
bool     dh_started     = false;  // true once we've sent our public key
bool     dh_established = false;  // true once the shared secret has been computed
unsigned long dh_lastSent = 0;
const long dh_retryInterval = 5000; // resend our public key every 5s until the IHM answers

// ----- Helpers: bytes <-> hex string, used to transport binary keys over MQTT (text) -----
String bytesToHex(const uint8_t* data, size_t len) {
  String out;
  out.reserve(len * 2);
  const char* hexChars = "0123456789abcdef";
  for (size_t i = 0; i < len; i++) {
    out += hexChars[(data[i] >> 4) & 0x0F];
    out += hexChars[data[i] & 0x0F];
  }
  return out;
}

// Returns true on success (correct length & valid hex), false otherwise
bool hexToBytes(const String& hex, uint8_t* out, size_t outLen) {
  if (hex.length() != outLen * 2) {
    return false;
  }
  for (size_t i = 0; i < outLen; i++) {
    char c1 = hex.charAt(2 * i);
    char c2 = hex.charAt(2 * i + 1);
    if (!isHexadecimalDigit(c1) || !isHexadecimalDigit(c2)) {
      return false;
    }
    out[i] = (uint8_t)((hexCharToVal(c1) << 4) | hexCharToVal(c2));
  }
  return true;
}

uint8_t hexCharToVal(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return 0;
}

// Generates the Arduino's key pair and publishes the public key on dh/arduino.
// ecdh_generate_keys() expects dh_private_key to already contain random bytes.
void startDiffieHellman() {
  randomSeed(analogRead(A3) ^ micros()); // crude entropy source, see note below
  for (size_t i = 0; i < ECC_PRV_KEY_SIZE; i++) {
    dh_private_key[i] = (uint8_t)random(0, 256);
  }

  if (!ecdh_generate_keys(dh_public_key, dh_private_key)) {
    Serial.println("ECDH: key generation failed!");
    return;
  }

  String payload = bytesToHex(dh_public_key, ECC_PUB_KEY_SIZE);

  Serial.print("ECDH: sending public key on ");
  Serial.println(topic4);
  mqttClient.beginMessage(topic4);
  mqttClient.print(payload);
  mqttClient.endMessage();

  dh_started  = true;
  dh_lastSent = millis();

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("DH: pub key sent");
}

// Called from onMqttMessage() when a message arrives on dh/ihm
void handleIhmPublicKey(const String& payload) {
  if (dh_established) {
    return; // secret already established, ignore further messages
  }

  if (!hexToBytes(payload, dh_ihm_public_key, ECC_PUB_KEY_SIZE)) {
    Serial.println("ECDH: invalid public key received from HMI");
    return;
  }

  if (!ecdh_shared_secret(dh_private_key, dh_ihm_public_key, dh_shared_secret)) {
    Serial.println("ECDH: shared secret computation failed!");
    return;
  }

  dh_established = true;

  Serial.print("ECDH: shared secret established: ");
  Serial.println(bytesToHex(dh_shared_secret, ECC_PUB_KEY_SIZE));

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("DH: secret OK");
}


void main() {
    if (!mqttClient.connect(broker, port)) {
    print("MQTT connection failed! Error code = ");
    println(mqttClient.connectError());

    while (1);
  }
  println("You're connected to the MQTT broker!");

  mqttClient.onMessage(onMqttMessage);

  Serial.print("Subscribing to topic: ");
  Serial.println(topic3);
  
  mqttClient.subscribe(topic3);

  Serial.print("Subscribing to topic: ");
  Serial.println(topic5);

  mqttClient.subscribe(topic5);

  // Arduino is the initiator of the Diffie-Hellman exchange
  startDiffieHellman();

  println("dh_shared_secret = %i", dh_shared_secret);
}