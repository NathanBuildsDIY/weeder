# Run on startup command in crontab
# @reboot python3 /home/nanu/Desktop/weeder/WeedKiller_v4.py > /home/nanu/Desktop/weeder/$(date +"%m_%d_%I_%M_%S_%p").out 2>&1
#TO DO: Check the selected cropped images to analyze are really the center of the sun targeting array
#TO DO: Test/improve move to weed
#TO DO: Know actual zaxis height. Raise/lower based on initial tilt/roll from suntracker to get things close before zaxis moves
#       Somehow ignore bright areas outside the shadow of the lens.  
#TO DO: redo script to adjust what qualifies as a "weed" via command line
#TO DO: improve image classification. normalize images - divide by std deviation. Scale - 0 to 1 value. Need to do in image classification too?
#TO DO: speed up - less writing to disk. Less time.sleep function call
#Note: images are upside down (if standing behind robot)
#Note: camera width at 200mm height, flat is 225mm across.  180 top to bottom. 1600x1200. Divide into 0-6 (width), 0-4 (height). Center is actually 50/50 (3 width, 2 height)
#Note: When swing 0 = right or 180 = left (when standing behind robot) the 50% target in Y direction changes becasue of rotation of lens on swing. 
#      Center is at crop 3 height, up from 2 Because Height increases from 0 at top of image to 4 on bottom image and image is upside down (so 0 is far from robot, 4 is next to robot wheels)
#Note: each block is 30mm width x 45mm height (approx). That's around 1.5x1.5 inches.

# import the necessary packages
#import argparse
#parser = argparse.ArgumentParser()
#parser.add_argument("--mode", help="Operational mode. Choose test-<motor>, test-full, photo, capture, run",
#                    type=str, choices=["test-swing","test-tilt","test-roll","test-lid","test-zaxis","test-wheel","test-suntracker","test-full","photo","capture","run"], default="run")
#parser.add_argument("--length", help="Distance in feet for weeder to travel forwad and back (int). Only used in capture and run modes. Default 50",
#                    type=int, default="50")
#parser.add_argument("--width", help="Distance in feet for weeder to travel from side to side (int). Only used in capture and run modes. Default, 2",
#                    type=int, default="1")
#parser.add_argument("--weeds", help="Comma separated list of weeds to check for and kill",
#                    type=str, choices=['l','c','l,c'], default="l,c")
#args = parser.parse_args()
#print("Weeder will operate in mode: ", args.mode)
#print("Weeder will travel foward/backward (in ft): ", args.length)
#print("Weeder will move sideways (in ft, each pass covers width of 1 ft, so this is also # of passes): ",args.width)
#weedArray=args.weeds.split(",")
#print("List of weeds to kill is: ",str(weedArray))
import numpy as np
import math
from tflite_support.task import core
from tflite_support.task import processor
from tflite_support.task import vision
import cv2
import imutils
import os
#import psutil
from glob import glob
import time
from datetime import datetime
import libcamera
from picamera2 import Picamera2, Preview
from datetime import datetime
from gpiozero import Device, PhaseEnableMotor, Robot, PhaseEnableRobot, LED, Servo, AngularServo, Button
#Need this to eliminate servo jitter
from gpiozero.pins.pigpio import PiGPIOFactory
#make the web app work
from flask import Flask, render_template, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import (IntegerField, SelectField, RadioField)
from wtforms import widgets, SelectMultipleField
from wtforms.validators import InputRequired, Length
from flask_autoindex import AutoIndex

#define wheels of robot and raise/lower of robot zaxis motors
robot = PhaseEnableRobot(left=(14, 15), right=(17, 4)) #pi zero 2
zaxis = PhaseEnableRobot(left=(18, 23), right=(16,12))  #forward = up, backwards = down
#pigpiod startup command was here but now should already be running, part of startup
factory = PiGPIOFactory()
#define servos
lid = AngularServo(10, initial_angle=180, min_angle=0, max_angle=180, min_pulse_width=14/10000, max_pulse_width=28/10000,pin_factory=factory)
  #note we actually control the min/max with the pulse widths. The angles listed are just for our convenience.
  #0 is fully rotated clockwise, 270 is counterclockwise, max/min seems to be 4/10000 and 28/10000
tilt = AngularServo(22, initial_angle=110, min_angle=0, max_angle=180, min_pulse_width=9/10000, max_pulse_width=28/10000,pin_factory=factory) #180 is up, 0 is down
roll = AngularServo(27, initial_angle=90, min_angle=0, max_angle=180, min_pulse_width=9/10000, max_pulse_width=14/10000,pin_factory=factory) #180 is right, 0 is left
swing = AngularServo(9, initial_angle=90, min_angle=0, max_angle=180, min_pulse_width=12/10000, max_pulse_width=17/10000,pin_factory=factory) #0 right. 180 left
#define variables to track current value of servos
swingVal = 90;
rollVal = 90;
tiltVal = 90;
lidVal = 180;

# The purpose of this is to use photoresistors on digital on/off threshold circuits
# and isloated into quadrants by sun blocking shields to orient towards the sun
# in a coarse manner by testing which are on/off at a given position
#              tilt down
#              q2 | q3
# roll left  --------- roll right
#              q1 | q4
#              tilt up
#             robot body
#set up sun tracker
quad1 = Button(6)
quad2 = Button(0)
quad3 = Button(13)
quad4 = Button(5)
viz1=0;viz2=0;viz3=0;viz4=0 #used to draw the state of teh sun tracker

#create run directory to save photos and go there
weederdir = os.path.expanduser("~/weeder/log/")
date = datetime.now().strftime("%m_%d_%I_%M_%S_%p_%f")
rundir = weederdir+date
os.makedirs(rundir)
os.chdir(rundir)

#camera setup
camwidth = 1600 
camheight = 1200 
Xtarget = camwidth*.5 #where we want the center of bright targeting array to end up
Ytarget = camheight*.5
CloseEnough = 100 #number of pixels we'll allow to be "off" between true center and center of target array
#create camera 
picam = Picamera2()
config = picam.create_preview_configuration(main={"size": (camwidth, camheight)})
config["transform"] = libcamera.Transform(hflip=1, vflip=1)
picam.configure(config)
picam.start()

# Visualization parameters for text on classification images
_ROW_SIZE = 10  # pixels
_LEFT_MARGIN = 10  # pixels
_TEXT_COLOR = (0, 0, 255)  # red
_FONT_SIZE = 0.5
_FONT_THICKNESS = 1
_FPS_AVERAGE_FRAME_COUNT = 10
# Initialize the image classification model. This is the custom trained model based on mobilenet
base_options = core.BaseOptions(
  file_name=os.path.expanduser('~/weeder/model_int8.tflite'), use_coral=False, num_threads=4)
# Enable Coral by this setting
classification_options = processor.ClassificationOptions(
  max_results=2, score_threshold=0.0)
options = vision.ImageClassifierOptions(
  base_options=base_options, classification_options=classification_options)
classifier = vision.ImageClassifier.create_from_options(options)
  
# Various useful functions
def takePhoto(prepend):
  time.sleep(.5) #let things settle before we snap a photo. hopefully we get clearer images this way
  #snapshot from camera and save. assumes we're already in correct directory
  date = datetime.now().strftime("%m_%d_%I_%M_%S_%p_%f") #note: keep it short and don't allow : in filename - error
  photo_name = prepend + "_" + date + ".jpg"
  picam.capture_file(photo_name)
  image = cv2.imread(photo_name) #pull up image and get shape
  camheight = image.shape[0]
  camwidth = image.shape[1]
  return photo_name,image,camheight,camwidth
def moveMotor(motor,currentAngle,targetAngle):
  #move servos gradually to avoid jerking the robot to pieces
  minorAdjust=0
  if targetAngle-currentAngle > 0:
    minorAdjust=1
  else:
    minorAdjust=-1
  while abs(targetAngle-currentAngle)>0 and 0<=currentAngle<=180:
    currentAngle=currentAngle+minorAdjust
    motor.angle=currentAngle
    time.sleep(0.02)
  if 180 < currentAngle or currentAngle < 0:
    print("motor must move between 0 and 180, trying to move to:, ",targetAngle," failed.")
  return currentAngle
def sunTracker(tiltVal,rollVal):
  sunTracker=0
  while sunTracker==0:
    viz1=1 if quad1.is_pressed else 0
    viz2=1 if quad2.is_pressed else 0
    viz3=1 if quad3.is_pressed else 0
    viz4=1 if quad4.is_pressed else 0
    #take action
    if (viz1==0 or viz4==0) and (viz2==1 and viz3==1):
      #tilt down
      tiltVal=moveMotor(tilt,tiltVal,tiltVal-10)
    if (viz2==0 or viz3==0) and (viz1==1 and viz4==1):
      #tilt peak
      tiltVal=moveMotor(tilt,tiltVal,tiltVal+10)
    if (viz1==0 or viz2==0) and (viz3==1 and viz4==1):
      #roll right
      rollVal=moveMotor(roll,rollVal,rollVal+10)
    if (viz3==0 or viz4==0) and (viz1==1 and viz2==1):
      #roll left
      rollVal=moveMotor(roll,rollVal,rollVal-10)
    if viz1 == 1 and (viz2 == 0 and viz3 == 0 and viz4 == 0):
      #roll left and tilt up
      tiltVal=moveMotor(tilt,tiltVal,tiltVal+10)
      rollVal=moveMotor(roll,rollVal,rollVal-10)
    if viz2 == 1 and (viz1 == 0 and viz3 == 0 and viz4 == 0):
      #roll left and tilt down
      tiltVal=moveMotor(tilt,tiltVal,tiltVal-10)
      rollVal=moveMotor(roll,rollVal,rollVal-10)
    if viz3 == 1 and (viz2 == 0 and viz1 == 0 and viz4 == 0):
      #roll right and tilt down
      tiltVal=moveMotor(tilt,tiltVal,tiltVal-10)
      rollVal=moveMotor(roll,rollVal,rollVal+10)
    if viz4 == 1 and (viz2 == 0 and viz3 == 0 and viz4 == 1):
      #roll right and tilt up
      tiltVal=moveMotor(tilt,tiltVal,tiltVal+10)
      rollVal=moveMotor(roll,rollVal,rollVal+10)
    if viz1+viz2+viz3+viz4>3:
      print("quadrant summary, viz1: ",viz1," viz2: ",viz2," viz3: ",viz3," viz4: ",viz4)
      print("close enough, stopping")
      sunTracker=1
    if viz1+viz2+viz3+viz4<1:
      print("not enough sun, taking a quick break")
      print("quadrant summary, viz1: ",viz1," viz2: ",viz2," viz3: ",viz3," viz4: ",viz4)
      time.sleep(1)
    print("  ",viz2," | ",viz3)
    print("----------")
    print("  ",viz1," | ",viz4)
    print("")
  #we're now facing teh sun. Give it an extra 10 degrees.  The tracking photoresistors tend to turn on just a bit before we're really facing the sun
  if tiltVal > 90:
    tiltVal=moveMotor(tilt,tiltVal,tiltVal+10)
  if tiltVal < 90:
    tiltVal=moveMotor(tilt,tiltVal,tiltVal-10)
  if rollVal > 90:
    rollVal=moveMotor(roll,rollVal,rollVal+10)
  if rollVal < 90:
    rollVal=moveMotor(roll,rollVal,rollVal-10)
  return tiltVal,rollVal
def drawimage(c,cX,cY,text,image):
  #add text and contour to image
  cv2.drawContours(image, [c], -1, (0, 255, 0), 2)
  cv2.circle(image, (cX, cY), 7, (255, 255, 255), -1)
  cv2.putText(image, text, (cX - 20, cY - 20),
  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
def drawtext(cX,cY,text,image):
  #add only text to image
  cv2.putText(image, text, (cX, cY),
  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
  print(text)
def categorizeImage(crop_image,crop_name):
  # Convert the image from BGR to RGB as required by the TFLite model.
  rgb_image = cv2.cvtColor(crop_image, cv2.COLOR_BGR2RGB)
  re_size = (224,224)
  rgb_image=cv2.resize(rgb_image,re_size)
  # Return variables
  returnPlant = "dirt"
  returnScore = 0.0
  firstScore = ""
  firstPlant = ""
  secondScore = ""
  secondPlant = ""
  # Create TensorImage from the RGB image
  tensor_image = vision.TensorImage.create_from_array(rgb_image)
  #tensor_image = vision.TensorImage.create_from_array(image)
  # List classification results
  categories = classifier.classify(tensor_image)

  # Show classification results on the image
  for idx, category in enumerate(categories.classifications[0].categories):
    category_name = category.category_name
    score = round(category.score, 2)
    result_text = category_name + ' (' + str(score) + ')'
    text_location = (_LEFT_MARGIN, (idx + 2) * _ROW_SIZE)
    cv2.putText(crop_image, result_text, text_location, cv2.FONT_HERSHEY_PLAIN,
                _FONT_SIZE, _TEXT_COLOR, _FONT_THICKNESS)
    #Let's get 2 results and if one is a weed, bias towards action. Still return category name if dirt or non-weed are present though
    if category_name.startswith("weed") and score > 2.0 and returnPlant == "dirt":
      returnPlant = category_name
      returnScore = score
    if returnScore == 0.0:
      returnPlant = category_name
      returnScore = score
    if idx == 0:
      firstScore = score
      firstPlant = category_name
    if idx == 1:
      secondScore = score
      secondPlant = category_name
  #write out the marked up, classified image to filesystem
  cv2.imwrite(firstPlant+"_"+str(firstScore)+"_"+secondPlant+"_"+str(secondScore)+"_"+crop_name,crop_image)
  return returnPlant,returnScore
def orientToSun(tiltVal,rollVal):
  # The purpose of this is to fine adjust orientation so the target array is pointed directly at the xTarget yTarget coordinates
  # It assumes coarse orientation ( via sunTracker ) is already done so bright spots in targeting array are in camera view
  # It works by finding the bright spots of the "target array" and then tries to center target x and y on that.
  centered = 0 #are bright spots centered on center x y?
  focused = 0 #is the span of bright spots small enough (focused?)
  orientToSunCount = 0 #counts attmpts to center bright spots
  focusAttempts = 0 #counts attempts to focus the bright spots
  initialTilt = tiltVal #ensure we don't go more than 60 degrees from this. if so, fail.
  initialRoll = rollVal #ensure we don't go more than 60 degrees from this. if so, fail.
  previousFocusSpan = [0,0] #track how large the span of bright spots is
  previousZAxisDir = "up"
  while orientToSunCount < 6 and focused == 0 and focusAttempts < 10:
    #snapshot from camera. assumes we're already in correct directory
    img_name,image,camheight,camwidth = takePhoto("center")
    print("Working on image: ",img_name)
    drawtext(10,10,"Image dimensions are: "+str(int(camheight))+", "+str(int(camcamwidth)),image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) #color to gray
    gray_equ = cv2.equalizeHist(gray) #equalize it to spread out histogram of intensity more evenly
    blurred = cv2.GaussianBlur(gray_equ, (21, 21), 0) #blur it a bit
    
    #figure out high and low thresh for comparing bright spots
    hist = cv2.calcHist([blurred], [0], None, [256], [0, 256]).flatten()
    total_count = camheight * camwidth  # height * width
    high_pixelBrightness_cutoff = .98 * total_count
    low_pixelBrightness_cutoff = .4 * total_count
    summed = 0
    high_threshold = 250
    low_threshold = 180
    for i in range(0, 255, 1):
      summed += int(hist[i])
      if low_pixelBrightness_cutoff >= summed:
        low_threshold = i #this stops incrementing the low threshold when we've counted the cutoff number of pixels
      if high_pixelBrightness_cutoff >= summed:
        high_threshold = i #this increments the threshold from 1->255 until we count the cutoff # of pixels
    drawtext(10,30,"low_threshold: "+str(int(low_threshold))+" high_threshold: "+str(int(high_threshold)),image)
    thresh = cv2.threshold(blurred, high_threshold, 255, cv2.THRESH_BINARY)[1] #threshold
    thresh = cv2.erode(thresh, None, iterations=2) #get rid of random extras
    thresh = cv2.dilate(thresh, None, iterations=4)
    
    #find contours of bright spots
    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    spotsArray = []
    idx = 0
    
    for c in cnts:
      M=cv2.moments(c)
      area = cv2.contourArea(c)
      if(2000<area<60000):
        #between 200 and 60000 (target arrays sizes)
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])
        #drawimage(c,cX,cY,"test",image)
        #print("X: ",cX, " Y: ",cY," area: ",area)
        drawimage(c,cX,cY,"light",image)
        #drawtext(10,180+idx*40,"Keeper.  X_dark: "+str(int(cX_dark))+ " Y_dark: "+str(int(cY_dark))+" area: "+str(int(area_dark)),image)
        drawtext(10,200+idx*40,"Keeper.  X: "+str(int(cX))+" Y: "+str(int(cY))+" area: "+str(int(area)),image)
        # Add this point to spots array
        spotsArray.append([])
        spotsArray[idx].append(cX)
        spotsArray[idx].append(cY)
        idx = idx + 1 #increment index until we find next "keeper" spot
    
    if centered == 0:
      orientToSunCount = orientToSunCount + 1
      #record all the results and adjust as needed
      if spotsArray == []:
        #If there are no contours (no bright spots), we must have a cloud passing? or other problem note it
        print("no bright spots found in fine adjust orientation to sun")
        addText = "No Bright Spots Found."
        drawtext(10,130,addText,image)
        #It's possible there's no sun because we need to turn further towards it OR because we're too low. Try to fix both.
        if tiltVal > 90:
          tiltVal=moveMotor(tilt,tiltVal,tiltVal+10)
        if tiltVal < 90:
          tiltVal=moveMotor(tilt,tiltVal,tiltVal-10)
        if rollVal > 90:
          rollVal=moveMotor(roll,rollVal,rollVal+10)
        if rollVal < 90:
          rollVal=moveMotor(roll,rollVal,rollVal-10)
        zaxis.forward(.25); time.sleep(.5); zaxis.stop(); #go up
      else:
        #We've got bright spots, so stop coarse scan, fine adjust to center
        drawtext(10,50,"Spots array is: "+str(spotsArray),image)
        centerSpot = np.mean(spotsArray, axis = 0)
        #print("center spot is: ",centerSpot) #Get the center of the bright spots
        #print("Xtarget (width*.4): ",Xtarget," Ytarget (height*.5): ",Ytarget) 
        if idx < 3:
          #only 2 bright spots, very likely not seeing everything. Move up more
          zaxis.forward(.25); time.sleep(1); zaxis.stop(); #go up
        if ((Xtarget-CloseEnough)<=centerSpot[0]<=(Xtarget+CloseEnough)) and ((Ytarget-CloseEnough)<=centerSpot[1]<=(Ytarget+CloseEnough)):
          addText = "We're centered, centerX: "+str(int(centerSpot[0]))+" centerY: "+str(int(centerSpot[1]))
          drawtext(10,70,addText,image)
          centered = 1
        else:
          #display the work so far on the images
          cv2.circle(image, (int(centerSpot[0]), int(centerSpot[1])), 15, (255, 255, 255), -1) #drop on center of spots
          cv2.circle(image, (int(Xtarget), int(Ytarget)), 15, (255, 255, 255), -1) #Circle the target
          addText = "old roll: "+str(rollVal)+" old tilt: "+str(tiltVal)
          drawtext(10,90,addText,image)
          #Move motor to center spot
          Xadjust = 0
          Yadjust = 0
          if (centerSpot[1]<(Ytarget-CloseEnough)) or (centerSpot[1]>(Ytarget+CloseEnough)):
            #less than y target - roll left, camera looks right, y value down the screen (larger y) - Yadjust < 0 = roll left
            #greater than y target - roll right, camera looks left, y value up the screen (smaller y) - Yadjust > 0 = roll right
            Yadjust = round(((centerSpot[1] - Ytarget) / 15), 0)
            addText = "tilt Yadjust: "+str(Yadjust)+" + tilt up/peak, - tilt down/away, centerSpot[1]-Ytarget = "+str(centerSpot[1]-Ytarget)
            drawtext(10,110,addText,image)
            tiltVal=moveMotor(tilt,tiltVal,tiltVal+Yadjust)
          if (centerSpot[0]>(Xtarget+CloseEnough)) or (centerSpot[0]<(Xtarget-CloseEnough)):
            #tilt away from peak of machine, camera looks inward, moves blips left, make x of array smaller - xAdjust > 0
            #tilt toward peak of machine, camera looks out, moves blips right, make x of array bigger - xAdjust < 0
            Xadjust = round(((centerSpot[0] - Xtarget) / 15), 0)
            addText = "roll Xadjust: "+str(Xadjust)+" - roll left, + roll right, centerSpot[0]-Xtarget = "+str(centerSpot[0]-Xtarget)
            drawtext(10,130,addText,image)
            rollVal=moveMotor(roll,rollVal,rollVal+Xadjust)
          addText = "Xadjust: "+str(Xadjust)+" Yadjust: "+str(Yadjust)+" centerX: "+str(int(centerSpot[0]))+" centerY: "+str(int(centerSpot[1]))+"new roll: "+str(rollVal)+"new tilt: "+str(tiltVal)
          drawtext(10,150,addText,image)
          if abs(rollVal - initialRoll) > 60:
            print("Moved greater than 60 degrees roll from initial value entering orientToSun. Ending")
            orientToSunCount = orientToSunCount + 100
          if abs(tiltVal - initialTilt) > 60:
            print("Moved greater than 60 degrees tilt from initial value entering orientToSun. Ending")
            orientToSunCount = orientToSunCount + 100
    if focused == 0 and centered == 1:
      #we centered the bright spots. now move up/down until they're focused (in a small circle of light)
      addText = "Focus attempt: " + str(focusAttempts)
      drawtext(10,150,addText,image)
      focusAttempts = focusAttempts + 1
      brightSpan = np.max(spotsArray, axis = 0) - np.min(spotsArray,axis = 0)
      if previousFocusSpan[0] == 0 and previousFocusSpan[1] == 0:
        #first run, go up a bit and rerun to compare
        zaxis.forward(.25); time.sleep(.25); zaxis.stop(); #go up
      else:
        if brightSpan[0] < CloseEnough * 3 and brightSpan[1] < CloseEnough * 3:
          #focused area of brightness is small enough. we're done
          addText = "Focused area is small enough, setting focused to 1 and returning from calibration. brightSpan = " + str(brightSpan)
          print(addText)
          drawtext(10,200,addText,image)
          focused = 1
        else:
          if (previousFocusSpan[0] + previousFocusSpan[1]) - (brightSpan[0] + brightSpan[1]) > 0:
            # focus is smaller than before. Do that direction again
            if previousZAxisDir == "up": 
              zaxis.forward(.25); time.sleep(1); zaxis.stop(); #go up
              previousZAxisDir = "up"
            if previousZAxisDir == "down":
              zaxis.backward(.25); time.sleep(1); zaxis.stop(); #go up
              previousZAxisDir = "down"
          else:
            #focus direction was wrong, focus area go bigger. go opposite direction
            if previousZAxisDir == "up":
              zaxis.backward(.25); time.sleep(1); zaxis.stop(); #go up
              previousZAxisDir = "down"
            else:
              zaxis.forward(.25); time.sleep(1); zaxis.stop(); #go up
              previousZAxisDir = "up"
      addText = "bright Span: " + str(brightSpan) + " previousFocusSpan: " + str(previousFocusSpan) + " previousZAxisDir " + str(previousZAxisDir)
      drawtext(10,170,addText,image)
      previousFocusSpan[0] = brightSpan[0]; previousFocusSpan[1] = brightSpan[1]
    #write out the image to filesystem
    cv2.imwrite(img_name,image)
  return tiltVal,rollVal,centered,focused
def moveToWeed(x,swingVal,rollVal,tiltVal):
  # The purpose of this module is to calculate the "best guess" motor values (roll, tilt, swing)
  # values to center the targeting array over an identified weed given that weeds coordinates in x y photo grid
  # theory - if sun is directly overhead (roll/tilt are centered) then no adjusts are needed, just move swing
  # if roll/tilt aren't centered then
    #1 we are already directed at the sun 
    #2 we swing to the new location based on x value in the photo (left right). Then we must adjust tilt/roll to still face sun
    #  if rolled right (+) and swing left (+), must tilt up (+), roll less (a bit left (-)). if rolled left (-) and swing left (+), must tilt down (-), roll less (a bit right (+)).
    #  if tilted up (+), and swing left (+), then roll left (-), tilt less (down a bit (-)).  If tilted down (-), and swing left (+), then roll right (+), tilt less (a bit up (+)).
    #Assume we're already adjusted in Z direction (focused), don't think any of these moves change the focal length, so no need to go up/down
  swingVal=moveMotor(swing,swingVal,swingVal+(3-x)*29) #move left when x is 0,1,2 b/c + adjust = move left.  move right (towards swing = 0 degrees) for 4,5,6. No change for 3.
  rollAdjust = -(((rollVal - 90) * (3-x)) / 10) - (((tiltVal - 90) * (3-x)) / 10)
  tiltAdjust = (((rollVal - 90) * (3-x)) / 10) + (((tiltVal - 90) * (3-x)) / 10)
  print("Moving to weed. SwingVal: "+str(swingVal+(3-x)*29)+" rollAdjust: "+str(rollAdjust)+" rollVal: ",str(rollVal)+" tiltAdjust: "+str(tiltAdjust)+" tiltVal: "+str(tiltVal))
  rollVal=moveMotor(roll,rollVal,rollVal+int(rollAdjust))
  tiltVal=moveMotor(tilt,tiltVal,tiltVal+int(tiltAdjust))
  #rollAdjust = 0; tiltAdjust = 0; #start assuming no adjust and calculate any adjusts below
  #if 3-x < 0:
  #  #swing right
  #  if rollVal > 90:
  #    #rolled right
  #  if rollVal < 90:
  #    #rolled left
  #  if tiltVal > 90:
  #    #tilted up
  #  if tiltVal < 90:
  #    #tilted down
  #if 3-x > 0:
  #  #swing left
  #  if rollVal > 90:
  #    #rolled right
  #    rollAdjust = -(((rollVal - 90) * (3-x)) / 10) + rollAdjust
  #    tiltAdjust = (((rollVal - 90) * (3-x)) / 10) + tiltAdjust
  #  if rollVal < 90:
  #    #rolled left
  #    rollAdjust = -(((rollVal - 90) * (3-x)) / 10) + rollAdjust
  #    tiltAdjust = (((rollVal - 90) * (3-x)) / 10) + tiltAdjust
  #  if tiltVal > 90:
  #    #tilted up
  #    rollAdjust = -(((tiltVal - 90) * (3-x)) / 10) + rollAdjust
  #    tiltAdjust = (((tiltVal - 90) * (3-x)) / 10) + tiltAdjust
  #  if tiltVal < 90:
  #    #tilted down
  #    rollAdjust = -(((tiltVal - 90) * (3-x)) / 10) + rollAdjust
  #    tiltAdjust = (((tiltVal - 90) * (3-x)) / 10) + tiltAdjust
  return swingVal,rollVal,tiltVal
def killWeed(swingVal,lidVal):
  # We're oriented, open the lid and wiggle around to kill the weed
  lidVal=moveMotor(lid,lidVal,0)
  for s in [10,10,10,-30]:
    #adjust swing by 10 degrees + (total of 30) then back 30 to the original value
    swingVal=moveMotor(swing,swingVal,swingVal+s)
    robot.forward(.25); time.sleep(2); robot.stop(); #go forward
    zaxis.forward(.25); time.sleep(2); zaxis.stop(); #go up
    robot.backward(.25); time.sleep(2); robot.stop() #go backward
    zaxis.backward(.25); time.sleep(2); zaxis.stop(); #go down
  lidVal=moveMotor(lid,lidVal,180) #close the lid.
def findAWeed(weedArray):
  weedX=-1
  #take a photo, search it for weeds in the reachable quadrants. When you find a weed, send back the X value
  #you can only see photos in a single Y line  (2,0) (3,1) (3,2) (3,3) (3,4) (3,5) (2,6)
  search_filename,search_image,camheight,camwidth = takePhoto("search_")
  print("Analyzing photo: ",search_filename)
  crop_size=224
  XYSearchPattern = [[3,3],[2,3],[4,3],[5,3],[1,3],[6,4],[0,4]]
  for searchIndex in range(len(XYSearchPattern)):
    #note cv2 crop function works image[y:y+h,x:x+i]
    cropped_image=search_image[int(XYSearchPattern[searchIndex][1]*crop_size):int((XYSearchPattern[searchIndex][1]+1)*crop_size),int(XYSearchPattern[searchIndex][0]*crop_size):int((XYSearchPattern[searchIndex][0]+1)*crop_size)]
    cropped_filename = str(XYSearchPattern[searchIndex][0])+"_"+str(XYSearchPattern[searchIndex][1])+"_"+search_filename
    plant_name,score = categorizeImage(cropped_image,cropped_filename)
    cropped_filename = str(plant_name)+"_"+str(score)+"_"+cropped_filename
    cv2.imwrite(cropped_filename,cropped_image)
    print("cropped filename: "+cropped_filename)
    for weed in weedArray:
      if plant_name == weed and score > 0.5:
        #found a weed in this location
        weedX = searchIndex
  return weedX

def runWeeder(swingVal,rollVal,tiltVal,lidVal,mode,width,length,weeds):
  #don't bother returning values. they shoudl all be neutral when we return from this
  if mode.startswith("test") and mode != "test-full":
    print("starting basic motor test")
    if mode == "test-wheel":
      robot.forward(.5); time.sleep(2); robot.backward(.5); time.sleep(2); robot.right(.5); time.sleep(2); robot.left(.5); time.sleep(2); robot.stop()
    if mode == "test-zaxis":
      zaxis.forward(.5); time.sleep(0.5); zaxis.backward(.5); time.sleep(0.6); zaxis.stop(); #forward is up, backward is down
    if mode == "test-lid":
      lidVal=moveMotor(lid,lidVal,0); lidVal=moveMotor(lid,lidVal,180) #180 is closed, 0 is open
    if mode == "test-roll":
      rollVal=moveMotor(roll,rollVal,180); rollVal=moveMotor(roll,rollVal,0); rollVal=moveMotor(roll,rollVal,90)
    if mode == "test-tilt":
      tiltVal=moveMotor(tilt,tiltVal,180); tiltVal=moveMotor(tilt,tiltVal,0); tiltVal=moveMotor(tilt,tiltVal,90)
    if mode == "test-swing":
      swingVal=moveMotor(swing,swingVal,180); swingVal=moveMotor(swing,swingVal,0); swingVal=moveMotor(swing,swingVal,90)
    if mode == "test-suntracker":
      tiltVal,rollVal=sunTracker(tiltVal,rollVal)
    print("done"); return; #exit so we only test individual exercise while tuning

  if mode == "test-full":
    print("starting full movements")
    takePhoto("testing")
    picam.close()
    robot.forward(.5); time.sleep(2); robot.backward(.5); time.sleep(2); robot.right(.5); time.sleep(2); robot.left(.5); time.sleep(2); robot.stop()
    zaxis.forward(0.25); time.sleep(1); zaxis.stop();
    for s in [180,0,90]:
      swingVal=moveMotor(swing,swingVal,s)
      for t in [180,0,90]:
        tiltVal=moveMotor(tilt,tiltVal,t)
        for r in [180,0,90]:
          rollVal=moveMotor(roll,rollVal,r)
          for l in [0,180]:
            lidVal=moveMotor(lid,lidVal,l)
    zaxis.backward(0.25); time.sleep(0.5); zaxis.stop();
    print("done"); return;

  if mode == "photo":
    print("Taking a photo at 90 degrees (neutral)")
    takePhoto("testing_90")
    swingVal=moveMotor(swing,swingVal,180); 
    print("Taking a photo at 180 degrees (left)")
    takePhoto("testing_180")
    swingVal=moveMotor(swing,swingVal,0); 
    print("Taking a photo at 0 degrees (right)")
    takePhoto("testing_0")
    swingVal=moveMotor(swing,swingVal,90)
    picam.close()
    print("done"); return;

  lengthTraveled=0
  widthTraveled=0
  previousDirectionTurned="left"
  if mode == "capture":
    print("Running capture ground photos loop. Starting sun tracker first")
    tiltVal,rollVal=sunTracker(tiltVal,rollVal)
    print("stopping sun tracker")
    while widthTraveled < int(width):
      widthTraveled = widthTraveled + 1
      while lengthTraveled < int(length):
        lengthTraveled = lengthTraveled + 1/6
        takePhoto("model")
        robot.forward(.5); time.sleep(1); robot.stop(); time.sleep(0.5)
      if previousDirectionTurned == "left":
        robot.right(.5); time.sleep(5); robot.stop(); time.sleep(0.1); robot.forward(.5); time.sleep(5); robot.right(.5); time.sleep(5); robot.stop();
        previousDirectionTurned="right"
      else:
        robot.left(.5); time.sleep(5); robot.stop(); time.sleep(0.1); robot.forward(.5); time.sleep(5); robot.left(.5); time.sleep(5); robot.stop();
        previousDirectionTurned="left"
      print("end of row of length ",str(lengthTraveled)," reached. Turned and now making pass ",widthTraveled," of ",width)
      lengthTraveled = 0
    picam.close()
    print("done"); return;

  if mode == "run":
    print("Running weeder program to kill weeds. Starting sun orientation")
    tiltVal,rollVal=sunTracker(tiltVal,rollVal)
    tiltVal,rollVal,centered,focused=orientToSun(tiltVal,rollVal)
    #centered = 1; focused = 1 #cheat around actual orientation
    if centered == 0:
      print("Unable to center bright target spots under lens in attempts allowed. Since sun is not centered and focused under the weeder, quitting")
      print("You can restart the program to reattempt orienting. Please place weeder on flat, level ground (no terrain changes under lens) to calibrate")
      print("If the sun is too low in the sky or if bright target spots can't be seen by the weeder camera, calibration will fail and weeder won't start")
      return 
    if focused == 0:
      print("Target bright spots under the lens are centered in the middle of the camera image, but were not focused properly in the time allowed")
      print("Attempting to weed anyway, but if the lens is too unfocused (the wrong distance off of the ground) the sun will not be focused enough to kill weeds")
      print("If this is the case and the sun is not low in the sky, you can manually change the weeder height and restart.")
      print("If the sun is low, weeder will not run properly, you should wait until sun is once again high enough to operate and focus")
    print("initial orientation done, neutralSwing: ",swingVal," neutralTilt: ",tiltVal," neutralRoll: ",rollVal)
    while widthTraveled < int(width):
      widthTraveled = widthTraveled + 1
      while lengthTraveled < int(length):
        lengthTraveled = lengthTraveled + 1/6
        weedX = findAWeed(weeds)
        weedX = -1
        if weedX > -1:
          #found a weed, weedX contains the X coordinate of the weed in the most recent photo
          swingKillVal,rollKillVal,tiltKillVal = moveToWeed(weedX,swingVal,rollVal,tiltVal) #move the motors to orient to the weed at the found X
          killWeed(swingKillVal,lidVal) #raise the lid and wiggle around
          #reset to neutral after killing weed
          swingVal = moveMotor(swing,swingKillVal,90)
          tiltVal = moveMotor(tilt,tiltKillVal,90)
          rollVal = moveMotor(roll,rollKillVal,90)
        robot.forward(.5); time.sleep(1); robot.stop(); time.sleep(0.5) #drive forward and start the loop over
      if previousDirectionTurned == "left":
        robot.right(.5); time.sleep(5); robot.stop(); time.sleep(0.1); robot.forward(.5); time.sleep(5); robot.right(.5); time.sleep(5); robot.stop();
        previousDirectionTurned="right"
      else:
        robot.left(.5); time.sleep(5); robot.stop(); time.sleep(0.1); robot.forward(.5); time.sleep(5); robot.left(.5); time.sleep(5); robot.stop();
        previousDirectionTurned="left"
      print("end of row of length ",str(lengthTraveled)," reached. Turned and now making pass ",widthTraveled," of ",width)
      lengthTraveled = 0
    picam.close()
    print("done");

#ppid = os.getppid() # Get parent process id
#parentCaller = psutil.Process(ppid).name()
#print(parentCaller)
#exit()
#if parentCaller == "bash":
#  runWeeder(swingVal,rollVal,tiltVal,lidVal)

SECRET_KEY = 'weederkey'
app = Flask(__name__)
app = Flask(__name__)
AutoIndex(app, browse_root=weederdir) #main page is autoindex of logs

app.config.from_object(__name__)
class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()
class weederForm(FlaskForm):
    runType = RadioField('Run Type', choices=[('run','Normal Run'),('capture','Capture Photos to Build Model'),('photo','Test Take a Photo'),('test-full','Test All Mtors'),('test-swing','Test Swing Motor'),('test-tilt','Test Tilt Motor'),('test-roll','Test Roll Motor'),('test-lid','Test Lid Motor'),('test-zaxis','Test Zaxis Motors'),('test-wheel','Test Wheels'),('test-suntracker','Test Suntracker Array')], default='run', coerce=str, validators=[InputRequired()])
    weedType = MultiCheckboxField('Label', choices=[('c','Creeping Charlie'),('l','Leaf')], default='l')
    distance = IntegerField('distance', default=10)
    rows = IntegerField('rows', default=1)

@app.route('/run',methods=['post','get'])
def run():
  form = weederForm()
  if form.validate_on_submit():
    print(form.runType.data)
    print(form.weedType.data)
    print(form.distance.data)
    print(form.rows.data)
    runWeeder(swingVal,rollVal,tiltVal,lidVal,form.runType.data,form.rows.data,form.distance.data,form.weedType.data)
  else:
    print(form.errors)
  return render_template('runType.html',form=form)

if __name__ == '__main__':
  app.run(debug=True)

