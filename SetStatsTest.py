import RPi.GPIO as GPIO
from mpu6050 import mpu6050
import threading
import logging
import time


logging.basicConfig(level=logging.INFO)

from pubnub.callbacks import SubscribeCallback
from pubnub.enums import PNStatusCategory, PNOperationType
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

pnconfig = PNConfiguration()
pnconfig.subscribe_key = "sub-c-76598f48-3f26-11ec-b886-526a8555c638"
pnconfig.publish_key = "pub-c-14d668cc-e874-4e1e-a4ab-bcf78c08744e"
pnconfig.uuid = '590f83a0-2b19-4e7f-9cef-09882f022320'
pubnub = PubNub(pnconfig)

my_channel = 'setstats-pi-channel'
sensor_list = ['coords']
data = {}
xAxis = 0
yAxis = 0

mpu = mpu6050(0x68)

GPIO.setmode(GPIO.BOARD)

TRIG = 13
ECHO = 11
BUZZER = 40

GPIO.setwarnings(False)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.output(TRIG, 0)
GPIO.setup(BUZZER, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)


beepCount = 0
rep = 0
set = 1


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def beep(repeat):
    for i in range(0, repeat):
        for pulse in range(60):
            GPIO.output(BUZZER, True)
            time.sleep(0.001)
            GPIO.output(BUZZER, False)
            time.sleep(0.001)
        time.sleep(.175)


# def led(colour):
#
#

def ultrasonic():
    # ultrasonic sensor setup
    GPIO.output(TRIG, 1)
    time.sleep(0.00001)
    GPIO.output(TRIG, 0)

    while GPIO.input(ECHO) == 0:
        pass
    start = time.time()

    while GPIO.input(ECHO) == 1:
        pass
    stop = time.time()

    return ((stop - start) * 17000)

# collects data from sensors and publishes to pubnub
def collectSensorData():
    loop = 0
    max = 0
    min = 3000
    increase = False
    global rep
    global set
    data["start"] = False
    start = time.time()
    while True:
        try:
            # tilt = mpu.get_gyro_data()['z']
            sway = mpu.get_accel_data()['z']
            height = ultrasonic()

            if loop <= 1:
                startingHeight = height
            # rep/set count
            if height > max:
                max = height
                increase = True
            if height < max:
                min = height
                increase = False

            if height <= min and increase == False and min <= startingHeight:
                rep += 1
                max = 0
                increase = True
            if rep == 12:
                set += 1
                rep = 0

            # at rest accelerometer doesnt read 0, this combats this by changing values between -0.75 and -0.95 to 0
            if(sway <= -1 and sway >=-1):
                sway = 0

            """
            When ultrasonic sensor is flush to surface, the readings are inaccurate with values such as 500cm or 2400cm. 
            This fixes the issue by setting height to 0 if accelerometer is at rest and the value being read in is less than 150.
            """

            # If the accelerometer reads higher than 15cm or less than -15cm, it's considered a fail and user is alerted.
            if (sway >= 3 or sway <= -3):
                messageColour = bcolors.FAIL
                beep(3)
            # If the accelerometer reads higher than 5 but less than 15 and vice versa, it is considered a "good" lift.
            elif (sway > 1.75 and sway < 3 or sway < -1.75 and sway < -3):
                messageColour = bcolors.WARNING
                beep(1)
            # Otherwise it is considered a "perfect" lift
            else:
                messageColour = bcolors.OKGREEN

            # print(bcolors.BOLD + f"{'{:.2f}'.format(tilt)}" + bcolors.ENDC)
            print(messageColour + f"{'{:.2f}'.format(sway)}" + "cm" + bcolors.ENDC)
            print(messageColour + f"{'{:.2f}'.format(height)}" + "cm" + bcolors.ENDC)
            print("Sets: ", set)
            print("Reps: ", rep)
            print("")
            print(startingHeight)

            current_time = (time.time() - start)
#            tilt = f"{'{:.2f}'.format(tilt)}"
            sway = f"{'{:.2f}'.format(sway)}"
            height = f"{'{:.2f}'.format(height)}"

            # Publishes coords to pubnub
            publish(my_channel, {"coordinates": {"sway":sway, "height":height}})
#            publish(my_channel, {"tilt": tilt})
            publish(my_channel, {"lift": {"set": set, "rep": rep}})
            loop+=1
            # Time between each reading
            time.sleep(.15)

        except Exception:
            print(Exception)

    end = time.time()
    print(end - start)

def publish(channel, msg):
    pubnub.publish().channel(channel).message(msg).pn_async(my_publish_callback)

def my_publish_callback(envelope, status):
    # Check whether request successfully completed or not
    if not status.is_error():
        pass  # Message successfully published to specified channel.
    else:
        pass  # Handle message publish error. Check 'category' property to find out possible issue
        # because of which request did fail.
        # Request can be resent using: [status retry];

class MySubscribeCallback(SubscribeCallback):
    def presence(self, pubnub, presence):
        pass  # handle incoming presence data

    def status(self, pubnub, status):
        if status.category == PNStatusCategory.PNUnexpectedDisconnectCategory:
            pass  # This event happens when radio / connectivity is lost

        elif status.category == PNStatusCategory.PNConnectedCategory:
            # Connect event. You can do stuff like publish, and know you'll get it.
            # Or just use the connected event to confirm you are subscribed for
            # UI / internal notifications, etc
            pubnub.publish().channel(my_channel).message('Starting...').pn_async(my_publish_callback)
        elif status.category == PNStatusCategory.PNReconnectedCategory:
            pass
            # Happens as part of our regular operation. This event happens when
            # radio / connectivity is lost, then regained.
        elif status.category == PNStatusCategory.PNDecryptionErrorCategory:
            pass
            # Handle message decryption error. Probably client configured to
            # encrypt messages and on live data feed it received plain text.

    def message(self, pubnub, message):
        # Handle new message stored in message.message
        try:
            msg = message.message
            key = list(msg.keys())
            if key[0] == "event":
                self.handle_event(msg)
        except Exception as e:
            print(message.message)
            print(e)
            pass

    def handle_event(self, msg):
        global data
        event_data = msg["event"]
        key = list(event_data.keys())
        print(key)
        print(key[0])
        if key[0] in sensor_list:
            print(event_data[key[0]])

if __name__ == '__main__':
    sensors_thread = threading.Thread(target=collectSensorData)
    sensors_thread.start()
    pubnub.add_listener(MySubscribeCallback())
    pubnub.subscribe().channels(my_channel).execute()

