
from enum import Enum
import threading
from thread_objects import *
import nav_loader 
from time import sleep
import drive as dr
#from navSystem_hall import navsystem

class State(Enum):
	TEST = 1
	STANDBY = 2
	ARM = 3

# Initialization
# Run setup and tests

hall_reader = threading.Thread(target = hall_thread, daemon = True)
nine_dof_reader = threading.Thread(target = nine_dof_thread, daemon = True)

global nav_loader
nav_loader.init()


# Go Into Operation Mode
hall_reader.start()
nine_dof_reader.start()


#Nathan's really old stuff (w/ two example functions)
from PIDcontrol import PID
from functionQueue import *

#testing PID
#controller = PID(1,1,1,.5)

#you can add functions to the queue
addToQueue((dr.drive, [1,1],[0,0]))
addToQueue((dr.drive, [0,0],[1,1]))

print("about to start queue")
sleep(5) # get some accelerometer data to avoid NaNs

#you can run the queue, it'll run
mainQueue()
