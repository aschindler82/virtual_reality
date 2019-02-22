# -*- coding: utf-8 -*-
import os

SUBJECT_NAME = "TEST"

# distance / time
TASK_TYPE = "time"

CONTEXT_ANGLE = 15

# defines move speed
MOVE_SPEED = 3

# time in secs to next order
# i.e. the time the subjects has to read the success text
T_TO_NEXT_ORDER = 10

# set move speed costant used for time paradigm
# in delivery
# -> reference time = pDistAstar/(MOVE_SPEED_CONST * MOVE_SPEED)
MOVE_SPEED_CONST = 1#2

# set paradigm's language DE / EN
LANGUAGE = "EN"

DROP_DICT = { "bakery"   : "Bäcker".encode("utf-8"), "butchery" : "Metzger".encode("utf-8"), "cafe"     : "Cafe".encode("utf-8"), "hotel"    : "Hotel".encode("utf-8"), "winery"   : "Weingeschäft".encode("utf-8") }

# number of residents in town per context
N_RESIDENTS = 100

# number of actors in game MUST BE EVEN!
# -> randomly chosen avatars that perform actions
# in the environment
# this number corresponds to all actors across context
# i.e. 2 means 1 red + 1 blue actors
N_CLONES = 20

# minimal animation period
# any random animation will last at least n seconds
MIN_ANIMATION_DUR = 5

# maximal number of paths in queue
N_MAX_PATHS_IN_QUEUE = 10

# home office
if os.environ['COMPUTERNAME'] == 'ANDREAS-PC':
    ROOT_PATH   = 'E:/owncloud_dahoam/documents'
    
# CIN PC
elif os.environ['COMPUTERNAME'] == 'AS-PC':
    ROOT_PATH   = 'C:/Users/as/ownCloud/documents'    

# ALIENWARE LAPTOP
elif os.environ['COMPUTERNAME'] == 'DESKTOP-CV028BR':
    ROOT_PATH   = 'C:/Users/as/ownCloud/documents'

# STIMULUS SETUP VISION LAB
elif os.environ['COMPUTERNAME'] == '0917-5988-02':
    ROOT_PATH   = 'C:/Users/lab/ownCloud'


EYE_HEIGHT      = 1.7

PATH_TO_AVTRWALK = os.path.join(ROOT_PATH, 'Davis/cpp/avtrWalk/Debug')

AVATAR_PATH     = os.path.join(ROOT_PATH, 'Davis/OFFICE_CHARS/CAL3D')

XML_PATH        = os.path.join(ROOT_PATH, 'Davis/cpp/avtrWalk/Debug')
HTML_PATH       = os.path.join(ROOT_PATH, 'Davis/pyDev/src/html') # store html file for webserver

PATH_TO_OSGB    = os.path.join(ROOT_PATH, 'Davis/memSpaceMods/OSGB')

PATH_TO_IMGS    = os.path.join(ROOT_PATH, 'Davis/pyDev/src/imgs')
PATH_TO_ICONS   = os.path.join(ROOT_PATH, PATH_TO_IMGS, 'icons')
PATH_TO_TEXT    = os.path.join(ROOT_PATH, 'Davis/pyDev/src/txt', LANGUAGE)

PATH_TO_LOGFILE = os.path.join(ROOT_PATH, 'Davis/pyDev/src/logs')

