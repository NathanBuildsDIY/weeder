#How to call: C:\Users\naNU\AppData\Local\Programs\Python\Python310\python.exe C:\Users\naNU\Desktop\weeder_lexar\DivideImage_sort_win_v2.py

# import the necessary packages
import numpy as np
import os
import imutils
import cv2
import matplotlib.pylab as plt
from glob import glob

crop_size = 224

os.chdir("C:\\Users\\naNU\\Desktop\\weeder_lexar\\03_30_02_11_00_PM_235773\\")
images_path = glob("*jpg")
for img in images_path:
  print("Working on image: ",img)
  image = cv2.imread(img) #pull up image
  cv2.imshow("Whole",image)
  height = image.shape[0]
  width = image.shape[1]
  for x in range(0, height // crop_size):
    #note // is floor division
    for y in range(0, width // crop_size):
      crop=image[(x*crop_size):((x+1)*crop_size),(y*crop_size):((y+1)*crop_size)]
      cv2.imshow(str(x) + "_" + str(y),crop)
      folder = chr(cv2.waitKey(0))
      print("this is the folder: ",folder)
      #plt.imshow(crop)
      #plt.axis('off')
      #plt.title("crop, X: "+str(x*crop_size)+":"+str((x+1)*crop_size)+" Y: "+str(y*crop_size)+":"+str((y+1)*crop_size))
      #plt.show()
      
      #folder = input("Classify folder name:\n")
      isExist = os.path.exists(str("C:\\Users\\naNU\\Desktop\\weeder_lexar\\sorted_v2\\"+folder))
      if not isExist:
        # Create a new directory because it does not exist
        os.makedirs("C:\\Users\\naNU\\Desktop\\weeder\\train\\sorted_v2\\"+folder)
      filename = "C:\\Users\\naNU\\Desktop\\weeder_lexar\\sorted_v2\\"+folder+"\\"+str(x) + "_" + str(y) + "_" + img
      #cv2.imwrite(filename,crop)
      if not cv2.imwrite(filename, crop):
        raise Exception("Could not write image: ",filename)
      cv2.destroyAllWindows()
