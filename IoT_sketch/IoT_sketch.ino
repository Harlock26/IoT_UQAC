#define btnPin 0
#define Vibration 1
#define heartratePin A2

#include <ArduinoMqttClient.h>
#include <WiFiNINA.h>
#include "arduino_secrets.h"
#include "DFRobot_Heartrate.h"
#include "DFRobot_RGBLCD1602.h"
#include <DFRobot_LIS2DH12.h>
#include <TimeLib.h>

extern "C" {
  #include "ecdh.h"
}

///////please enter your sensitive data in the Secret tab/arduino_secrets.h
char ssid[] = SECRET_SSID;        // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)

WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);
DFRobot_Heartrate heartrate(ANALOG_MODE);
DFRobot_LIS2DH12 acce(&Wire,0x18);
DFRobot_RGBLCD1602 lcd(/*RGBAddr*/0x60 ,/*lcdCols*/16,/*lcdRows*/2);  //16 characters and 2 lines of show

const char broker[] = "test.mosquitto.org";
int        port     = 1883;
const char topic[]  = "acceleration";
const char topic2[] = "heartrate";
const char topic3[] = "heartrate/bpm";
const char topic4[] = "dh/arduino"; // For secret exchange over Diffie Hellman, messages sent by arduino card
const char topic5[] = "dh/ihm";     // Messages sent from HMI


//set interval for sending messages (milliseconds)
const long interval = 200;
unsigned long previousMillis = 0;
unsigned long previousMillisBpm = 0;
bool lastButtonState = HIGH;

int count = 0;
String bpm;

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

void setup() {
  //Initialize serial and wait for port to open:
  Serial.begin(9600);

  pinMode(btnPin,INPUT_PULLUP); //pinMode(btnPin,INPUT);
  pinMode(Vibration,OUTPUT);
  pinMode(heartratePin,INPUT);
  lcd.init();
  lcd.setBacklight(false);
  while(!acce.begin()){
     Serial.println("Initialization failed, please check the connection and I2C address settings");
     delay(1000);
  }
  //Get chip id
  Serial.print("chip id : ");
  Serial.println(acce.getID(),HEX);
  
  /**
    set range:Range(g)
              eLIS2DH12_2g,/< ±2g>/
              eLIS2DH12_4g,/< ±4g>/
              eLIS2DH12_8g,/< ±8g>/
              eLIS2DH12_16g,/< ±16g>/
  */
  acce.setRange(/*Range = */DFRobot_LIS2DH12::eLIS2DH12_4g);

  /**
    Set data measurement rate：
      ePowerDown_0Hz 
      eLowPower_1Hz 
      eLowPower_10Hz 
      eLowPower_25Hz 
      eLowPower_50Hz 
      eLowPower_100Hz
      eLowPower_200Hz
      eLowPower_400Hz
  */
  acce.setAcquireRate(/*Rate = */DFRobot_LIS2DH12::eLowPower_10Hz);
  delay(1000);

  lcd.setCursor(0,0);
  lcd.print("Connect to WiFi");
  // attempt to connect to Wifi network:
  Serial.print("Attempting to connect to WPA SSID: ");
  Serial.println(ssid);
  while (WiFi.begin(ssid, pass) != WL_CONNECTED) {
    // failed, retry
    Serial.print(".");
    delay(5000);
  }

  Serial.println("You're connected to the network");
  Serial.println();
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("WiFi OK");

  Serial.print("Attempting to connect to the MQTT broker: ");
  Serial.println(broker);

  if (!mqttClient.connect(broker, port)) {
    Serial.print("MQTT connection failed! Error code = ");
    Serial.println(mqttClient.connectError());

    while (1);
  }
  Serial.println("You're connected to the MQTT broker!");
  Serial.println();
  
  mqttClient.onMessage(onMqttMessage);

  Serial.print("Subscribing to topic: ");
  Serial.println(topic3);
  
  mqttClient.subscribe(topic3);

  Serial.print("Subscribing to topic: ");
  Serial.println(topic5);

  mqttClient.subscribe(topic5);

  lcd.setCursor(0,1);
  lcd.print("MQTT broker OK");

  // Arduino is the initiator of the Diffie-Hellman exchange
  startDiffieHellman();
  Serial.println("DH done");
  /*
  if (sizeof(dh_shared_secret) > 0){
    Serial.print("Diffie-Hellman done, shared secret is : ");
    for(int i = 0; i <= sizeof(dh_shared_secret); i++){
      Serial.println(dh_shared_secret[i]);
    }
  }*/
  
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("ECDH OK");
  delay(1000);
  lcd.clear();
}

void loop() {
  bool buttonState = digitalRead(btnPin);

  if (buttonState != lastButtonState) {
    if (buttonState == HIGH) {
      lcd.setBacklight(true);   // button pressed
    } else {
      lcd.setBacklight(false);  // button released
    }
    lastButtonState = buttonState;
  }
  // call poll() regularly to allow the library to send MQTT keep alive which
  // avoids being disconnected by the broker
  mqttClient.poll();

  unsigned long currentMillis = millis();

  // Resend our public key periodically until the HMI has answered
  if (!dh_established && dh_started && (currentMillis - dh_lastSent >= dh_retryInterval)) {
    dh_lastSent = currentMillis;
    Serial.println("ECDH: no answer yet from HMI, resending public key");
    mqttClient.beginMessage(topic4);
    mqttClient.print(bytesToHex(dh_public_key, ECC_PUB_KEY_SIZE));
    mqttClient.endMessage();
  }

  

  // Things done only every interval (0.2) seconds, and only once DH is established
  if (dh_established && currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis; // save the last time a message was sent

    // Refresh the display
    digitalClockDisplay(-4);
    bpmDisplay();

    // Sends heart sensor & acceleromter data to mqtt broker every interval time
    lcd.setCursor(1, 0);
    lcd.print(" ");
    lcd.setCursor(2, 0);
    lcd.print(" ");
    long ax,ay,az;
    ax = acce.readAccX();//Get the acceleration in the x direction
    ay = acce.readAccY();//Get the acceleration in the y direction
    az = acce.readAccZ();//Get the acceleration in the z direction
    long acc[3] = {ax,ay,az};

    String json = "[";
    for (int i = 0; i < 3; i++) {
      json += String(acc[i]);
    if (i < 2) json += ",";
    }
    json += "]";

    uint8_t rateValue;
    uint8_t heartratePinValue;
    heartratePinValue = heartrate.getValue(heartratePin);

    // send message, the Print interface can be used to set the message contents
    mqttClient.beginMessage(topic);
    mqttClient.print(json);
    mqttClient.endMessage();

    mqttClient.beginMessage(topic2);
    mqttClient.print(String(heartratePinValue));
    mqttClient.endMessage();
  }
}

void digitalClockDisplay(int timeZone){
  // digital clock display of the time
  lcd.setCursor(0, 1);
  time_t t = WiFi.getTime()+3600*timeZone;
  String h = String(hour(t));
  String m = String(minute(t));
  String s = String(second(t));
  if (m=="0" && s=="0"){
    analogWrite(Vibration, 220);
  }
  else {
    analogWrite(Vibration, 0);
  }
  lcd.print(h);
  m = formatDigits(m);
  lcd.print(m);
  s = formatDigits(s);
  lcd.print(s);
}

void bpmDisplay(){
  lcd.setCursor(6, 0); // pixels (2,0) and (3,0) don't work anymore, I shifted the display
  lcd.print(formatBpm(bpm));
  Serial.println(formatBpm(bpm));
}

String formatDigits(String input){
  if (input.length()==1){
    input = "0"+input;
  }
  return (":"+input);
}

String formatBpm(String input){
  if (input.length()<1 or input.length()>4){
    input = "err";
  }
  for (int i=0;i<(4-input.length());i++){
    input = " " + input;
  }
  return (input + " bpm");
}

/*
String replace_dots(String str) {
    for (int i = 0; i < str.length(); i++) {
        if (str[i] == '.')
            str[i] = ',';
    }
    return str;
} */

void onMqttMessage(int messageSize){
  // we received a message, print out the topic and contents
  String incomingTopic = mqttClient.messageTopic();
  Serial.print("Received a message with topic ");
  Serial.print(incomingTopic);
  Serial.print(", length ");
  Serial.print(messageSize);
  Serial.print(", bytes:");
  String incoming = "";
  // use the Stream interface to print the contents
  while (mqttClient.available()) {
    incoming += (char)mqttClient.read();
  }
  Serial.println(incoming);

  if (incomingTopic == topic5) {
    // Message coming from the HMI on dh/ihm -> contains its ECDH public key
    handleIhmPublicKey(incoming);
    return;
  }

  if (incomingTopic == topic3) {
    // convert the incoming string to an int so you can use it:
    bpm = incoming;
  }
  // unsigned long currentMillis = millis();
  // if (currentMillis - previousMillisBpm >= 1000){ //update display only every second
  //   bpm = formatBpm(String(result));
  //   lcd.setCursor(0, 0);
  //   lcd.print(bpm);
  // }
}
