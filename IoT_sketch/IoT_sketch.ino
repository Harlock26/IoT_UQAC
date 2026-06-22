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
const char topic2[]  = "heartrate";
const char topic3[] = "heartrate/bpm";

//set interval for sending messages (milliseconds)
const long interval = 200;
unsigned long previousMillis = 0;
unsigned long previousMillisBpm = 0;
bool lastButtonState = HIGH;

int count = 0;
String bpm;

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
  Serial.println();
  
  mqttClient.subscribe(topic3);
  lcd.setCursor(0,5);
  // lcd.print("bpm");
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

  

  // Things done only every interval (0.2) seconds
  if (currentMillis - previousMillis >= interval) {
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
  Serial.println("Received a message with topic ");
  Serial.print(mqttClient.messageTopic());
  Serial.print(", length ");
  Serial.print(messageSize);
  Serial.println(" bytes:");
  String incoming = "";
  // use the Stream interface to print the contents
  while (mqttClient.available()) {
    incoming += (char)mqttClient.read();
  }
  // convert the incoming string to an int so you can use it:
  bpm = incoming;
  // print the result:
  Serial.println(bpm);
  // unsigned long currentMillis = millis();
  // if (currentMillis - previousMillisBpm >= 1000){ //update display only every second
  //   bpm = formatBpm(String(result));
  //   lcd.setCursor(0, 0);
  //   lcd.print(bpm);
  // }
}
