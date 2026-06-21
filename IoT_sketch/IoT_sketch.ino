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
bool lastButtonState = HIGH;

int count = 0;

void setup() {
  //Initialize serial and wait for port to open:
  Serial.begin(9600);
  /*
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }*/
  pinMode(btnPin,INPUT_PULLUP); //pinMode(btnPin,INPUT);
  pinMode(Vibration,OUTPUT);
  pinMode(heartratePin,INPUT);
  lcd.init();
  lcd.setBacklight(false);
  //lcd.setRGB(255, 255, 255);
  while(!acce.begin()){
     //Serial.println("Initialization failed, please check the connection and I2C address settings");
     delay(1000);
  }
  //Get chip id
  //Serial.print("chip id : ");
  //Serial.println(acce.getID(),HEX);
  
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
  //Serial.print("Acceleration:\n");
  delay(1000);
  // attempt to connect to Wifi network:
  //Serial.print("Attempting to connect to WPA SSID: ");
  //Serial.println(ssid);
  while (WiFi.begin(ssid, pass) != WL_CONNECTED) {
    // failed, retry
    //Serial.print(".");
    delay(5000);
  }

  //Serial.println("You're connected to the network");
  //Serial.println();

  //Serial.print("Attempting to connect to the MQTT broker: ");
  //Serial.println(broker);

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
}

void loop() {
  digitalClockDisplay(-4);
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
  
  if (currentMillis - previousMillis >= interval) {
    // save the last time a message was sent
    previousMillis = currentMillis;
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
    heartratePinValue = heartrate.getValue(heartratePin); ///< A1 foot sampled values
    rateValue = heartrate.getRate(); ///< Get heart rate value
    if(rateValue)  {
      Serial.println(rateValue);
    }
    //lcd.setCursor(0,0);
    //String bpmDisplay;
    //bpmDisplay = formatBpm(String(mqttClient.read()));
    //formatBpm(String(heartratePinValue));
    //lcd.print(bpmDisplay);
    /*
    Serial.print("Sending message to topic: ");
    Serial.println(topic);
    Serial.println(json);

    Serial.print("Sending message to topic: ");
    Serial.println(topic2);
    Serial.println(rateValue);
    */
    /*
    Serial.print("rateValue = ");
    Serial.println(rateValue);
    Serial.print("heartratePinValue = ");
    Serial.println(heartratePinValue);
    */
    // send message, the Print interface can be used to set the message contents
    mqttClient.beginMessage(topic);
    mqttClient.print(json);
    mqttClient.endMessage();

    mqttClient.beginMessage(topic2);
    mqttClient.print(String(heartratePinValue));
    mqttClient.endMessage();
  
    //Serial.println();
  }
  //lcd.setCursor(0,1);
  //lcd.print("        ");
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

String formatDigits(String input){
  if (input.length()==1){
    input = "0"+input;
  }
  return (":"+input);
}

String formatBpm(String input){
  if (input.length()<1 or input.length()>3){
    input = "err";
  }
  for (int i=0;i<(3-input.length());i++){
    input = " " + input;
  }
  return (input + " bpm");
}

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
  int result = incoming.toInt();
  // print the result:
  Serial.println(result);
  String bpm;
  bpm = formatBpm(String(result));
  lcd.setCursor(0, 0);
  lcd.print(bpm);
  //delay(100);
}
