import viz
import vizfx
import vizact
import viztask

import os
import time
import random
import xml.etree.ElementTree as xmle

from distutils.dist import warnings

import threading
import socket

import numpy as np
import constants as ct

from delivery import HomeTargetQueue


"""Replaces vizfx.addAvatar -> use extended Avatar class"""
def addAvatar(filename, parent = viz.WORLD, scene = viz.MainScene, flags=0, **kw):
    """vizfx: Add an avatar to the scene"""    
    model = VizAvatar(viz._ipcSend(viz._VIZ_ADDAVATAR, viz._sceneID(scene), int(parent), filename, flags, 0.0, 0.0, 0.0),**kw)
    
    if model:
        if model.getAsyncStatus() == viz.ASYNC_LOADING:
            vizact.onAsyncLoad(model, vizfx._modelAsyncLoad, viz.EFFECTGEN_DEFAULT, vizfx.getComposer(vizfx.DEFAULT_COMPOSER))
        else:
            model.generateEffects(viz.EFFECTGEN_DEFAULT, vizfx.getComposer(vizfx.DEFAULT_COMPOSER))

    return model



"""Extend VizAvatar and add avID"""
class VizAvatar(viz.VizAvatar):
    def __init__(self, id, **kw):
        self.avType   = 'walker'
        self.avID     = None
        self.avCtx    = None # context 1 or 2
        self.charName = None
        
        self.actionCtr = 0
        
        self.cActionT0 = -1
        
        # visible won't return anything
        # -> set manual visibility flag
        self.isVisible = 1
        
        viz.VizAvatar.__init__(self, id, **kw)
    
    def addAction(self, cAction, t0=-1):
        self.cAction   = cAction
        self.cActionT0 = t0
        
        self.actionCtr = self.actionCtr + 1
        
        # run parent method
        viz.VizAvatar.addAction(self, cAction)
    
    def isActionReady(self):
        
        # is there any action running
        # that should be continued?
        if self.cActionT0 > 0:
        
            if viz.tick() > self.cActionT0 + ct.MIN_ANIMATION_DUR:
                self.cActionT0 = -1
                return 1
            else:
                # repeat last action
                viz.VizAvatar.addAction(self, self.cAction)
                return 0
        
        # currently there is no action
        # that needs to be repeated
        # always return 1
        else:
            return 1
        
    
    def setAvID(self, aId, charName=None):
        self.avID = aId
        if charName:
            self.charName = charName
    
    def getAvType(self):
        return self.avType
        
    def getAvID(self):
        return self.avID
                
    def setCtx(self, ctx):
        self.avCtx = ctx
        
    def setAvType(self, avtType):
        self.avType = avtType
        
    def getCtx(self):
        return self.avCtx
   
    def getCharName(self):
        return self.charName
    
    def getActionCtr(self):
        return self.actionCtr
    
    
    """override copy method to enable vizfx effects on copied avatar"""
    def copy(self, **kw):
        avCopy = viz.VizAvatar.copy(self, **kw)            
        
        # copy position and orientation
        avCopy.setMatrix( self.getMatrix() )
        
        # start walk animation
        avCopy.state(1)
        
        avCopy.isVisible = 1
        
        avCopy.hasArrived = 0
        avCopy.isInHouse  = 0
        
        # copy id
        avCopy.setAvID( self.getAvID() )
        
        # add field where path will be stored in
        avCopy.path = None
        
        # copy ctx
        avCopy.setCtx( self.getCtx() )
        
        # copy position
        #avCopy.setPosition( self.getPosition() )
        
        # activate vizfx effects
        avCopy.generateEffects(viz.EFFECTGEN_DEFAULT, vizfx.getComposer(vizfx.DEFAULT_COMPOSER))
        
        return avCopy


    
"""Add and move avatars"""
class CrowdManager(viz.EventClass):
    
    """Open socket, init avatars"""
    def __init__(self, UDPmanHdl, SceneDefHdl, DeliveryHdl, oneCtx=0):
        # run super constructor
        viz.EventClass.__init__(self)
        
        # one context flag for control condition
        self.oneCtx = oneCtx
        
        if self.oneCtx:
            self.condStr = "oneContext"
        else:
            self.condStr = "twoContexts"
        
        self.callback(viz.ACTION_END_EVENT, self.updateWalkTarget)            
        
        # save handles
        self.UDPmanHdl   = UDPmanHdl
        self.sceneDefHdl = SceneDefHdl
        self.deliveryHdl = DeliveryHdl

        # create background process to calculate
        # closest distances from avPos to house
        # entrance within same context
        self.homeTargetFinder = HomeTargetQueue( DeliveryHdl.grid, oneCtx )
        
        # add pickup zone targets                            
        self.homeTargetFinder.addTargets( [pZ.getZoneXYZ() for pZ in self.deliveryHdl.pZones],  [pZ.getCtx() for pZ in self.deliveryHdl.pZones] )
        viztask.schedule( self.homeTargetFinder.checkQueue() ) # start queue
        
        # overall number of avatars walking around
        # first half belongs to context 1
        # second half belongs to context 2
        self.nAvtrs = len(SceneDefHdl.agents)
                                    
        # list with avatars
        self.avatars = []

        # avatrs that do random actions according to their context
        # will contain copied avatar objects
        self.actors = []

        self.avCtr = [0, 0]

        # get number of different characters that will
        # appear in our scene.
        self.charNames  = os.listdir(ct.AVATAR_PATH) # each folder corresponds to one character
        self.nChars     = len(self.charNames)
        
        # add avatars and tell them first wp
        for avInd in range( len(self.UDPmanHdl.agentPos) ):
            self.routeAvatar(avInd)
        
        # define log files for avatar and subject position
        self.avPosLogFile   = "%s_%s_%s"%(ct.SUBJECT_NAME, self.condStr, time.strftime('avPos_%d-%m-%y_%H-%M.txt'))
        self.subjPosLogFile = "%s_%s_%s"%(ct.SUBJECT_NAME, self.condStr, time.strftime('subjPos_%d-%m-%y_%H-%M.txt'))
        
        # log avatar position every 5 seconds to text file
        vizact.ontimer(5, self.logAvatarPos)
                
    """Check avatar ID"""
    def getAvatarInd(self, aId):
        i=0;
        if len(self.avatars) > 0:
            for av in self.avatars:
                if av.getAvID() == aId:
                    # return avatar object
                    return i
                    
                i=i+1;
        
        # no avatar found
        return -1
        

    """Add avatar"""
    def addNewAvatar(self, aId, x, y):
                
        # add red avatar
        if aId < self.nAvtrs/2: # id starts with 0
            ctxID = 1            
            cCharName  = self.charNames[self.avCtr[0]]
            cCharInCtx = cCharName+'Red.cfg'
            self.avatars.append( addAvatar(os.path.join(ct.AVATAR_PATH, cCharName, cCharInCtx), pos=[x,0,y]) )
            self.avCtr[0] = self.avCtr[0]+1
            
            if self.avCtr[0] > self.nChars-1:
                self.avCtr[0] = 0 # reset avtr ctr
            
            
        # add blue avatar
        else:
            ctxID = 2
            cCharName  = self.charNames[self.avCtr[1]]
            cCharInCtx = cCharName+'Blue.cfg'
            self.avatars.append( addAvatar(os.path.join(ct.AVATAR_PATH, cCharName, cCharInCtx), pos=[x,0,y]) )
            self.avCtr[1] = self.avCtr[1]+1
            
            if self.avCtr[1] > self.nChars-1:
                self.avCtr[1] = 0 # reset avtr ctr
                        
                
        # assign context and agent id to current avt
        self.avatars[-1].setCtx(ctxID)
        self.avatars[-1].setAvID(aId, cCharInCtx)
        
        # start walk animation
        self.avatars[-1].state(2)
        
        return len(self.avatars)-1
    
    
    """Called when an avatar reached walking target"""
    def updateWalkTarget(self, evtData):
        # this function will be called after any action is finished
        # however: only update avatars
        if isinstance(evtData.object, VizAvatar):
            
            # if avatar is walker
            if evtData.object.getAvType() == 'walker':
                
                # if there is less than X clones around                
                if len(self.actors) < ct.N_CLONES:
                    
                    # if we need a clone of this context
                    if len([cl.getCtx() for cl in self.actors if cl.getCtx() == evtData.object.getCtx()]) < ct.N_CLONES/2:
                    
                        # if this walker has not a clone already
                        if not evtData.object.getAvID() in [cl.getAvID() for cl in self.actors]:
                                            
                            # copy avatar to clone and assign orig ID
                            cClone = evtData.object.copy()
                            cClone.setAvType('clone')
                            
                            # DEBUGGING -> set clone to transparent
                            #cClone.alpha(0.5)
                            
                            # set walker avatar to invisible
                            # -> allows to continue walking
                            evtData.object.visible(viz.OFF)
                            evtData.object.isVisible = 0
                                  
                            # queue process to look for path to closest entrance
                            self.homeTargetFinder.findPath( evtData.object.getPosition(), cClone.getCtx(), cClone.getAvID() )
                            
                            # assign animation
                            if not self.oneCtx:
                                do   = vizact.animation( random.randint(6,10) )
                            else:
                                # draw from all animations
                                anInds = [6, 7, 8, 9, 10, 14, 15, 16, 17, 18]
                                random.shuffle(anInds)
                                do   = vizact.animation(anInds[0])
                            cClone.addAction(do, viz.tick()) # override addAction
                            
                            # save this clone in list
                            self.actors.append( cClone )
                                            
                            #print "Orig: ", evtData.object.getAvID()
                            #print "Clone: ", cClone.getAvID()
                                    
                # assign next routing point to orig avatar
                self.routeAvatar(evtData.object.getAvID())
                
            
            # if avatar is clone
            elif evtData.object.getAvType() == 'clone':

                cClone = evtData.object
                
                # did clone complete current action?
                if cClone.isActionReady():
                
                    # if clone arrived at pZone
                    if cClone.hasArrived:
                            
                        # we are reaching our destination
                        if cClone.isInHouse:
                            
                            # remove clone, update clone list
                            cClone.pZone.pNode.setAnimationState( viz.STOP, node='door' )
                            
                            # set walker to visible
                            for cA in self.avatars:
                                if cA.getAvID() == cClone.getAvID():
                                    cA.visible(viz.ON)                                    
                                    cA.isVisible = 1
                                    # DEBUGGING: set to transparent
                                    #cA.alpha(0.5)
                                    break
                            
                            # remove clone node from scene and actors list
                            cClone.remove()
                            self.actors = [cl for cl in self.actors if cl.getAvID() is not cA.getAvID()]
                            
                            #print "actors: ", self.actors
                            
                            return
                        
                        else:
                            # walk in house
                            dX, dY, dZ = cClone.pZone.getDoorXYZ()
                            walk = viz.ActionData()                        
                            walk.data = [dX, dY, dZ, viz.AUTO_COMPUTE, None, vizact.ROTATION_SPEED] # prevents animation from resetting
                            walk.verb = 'walk'
                            walk.turnInPlace = False
                            walk.actionclass = vizact.VizWalkRotAction
                            # add walk action                        
                            cClone.addAction(walk)
                            cClone.isInHouse = 1                            
                            return
                        
                        
                    # check whether this clone has been assigned to a path already
                    # returns [] if not ready yet
                    if not cClone.path:
                        # poll queue
                        pData = self.homeTargetFinder.getTarget( cClone.getAvID() )
                        
                        # if path is ready
                        if pData:
                            #print pData
                            cClone.path      = pData["path"]                        
                            cClone.pZone     = self.deliveryHdl.pZones[pData["targetInd"]]
                            
                            cClone.nPathSteps = len(cClone.path)
                            cClone.cPathStep  = 0
                            
                            # start walk animation
                            cClone.state(2)
                        
                     
                    # walk!
                    if cClone.path:
    
                        # increase pathstep
                        cClone.cPathStep = cClone.cPathStep + 1                    
    
                        # if we reached middle of path -> stay a while and do an animation
                        if cClone.cPathStep == round( cClone.nPathSteps/2.0 ):
                            # assign animation
                            if not self.oneCtx:
                                do   = vizact.animation( random.randint(6,10) )
                            else:
                                # draw from all animations
                                anInds = [6, 7, 8, 9, 10, 14, 15, 16, 17, 18]
                                random.shuffle(anInds)
                                do   = vizact.animation(anInds[0])
                                
                            cClone.addAction(do, viz.tick())
                        
                        # walk
                        else:
                            # if this is the last waypoint
                            if len(cClone.path) == 1:
                                
                                # open door
                                cClone.pZone.pNode.setAnimationState( viz.STOP, node='door' )
                                cClone.pZone.pNode.setAnimationSpeed( 2,        node='door' )
                                cClone.pZone.pNode.setAnimationState( viz.PLAY, node='door' )
                                
                                cClone.hasArrived = 1
                                                        
                            # walk                                                                                                    
                            wp   = cClone.path.pop(0)
                            walk = viz.ActionData()
                            # flip y coord to get to world space
                            walk.data = [wp[0], 0, wp[1], viz.AUTO_COMPUTE, None, vizact.ROTATION_SPEED] # prevents animation from resetting
                            walk.verb = 'walk'
                            walk.turnInPlace = False
                            walk.actionclass = vizact.VizWalkRotAction
                            
                            # add walk action
                            cClone.addAction(walk)                    
                        
                    else:
                        # assign animation
                        if not self.oneCtx:
                            do   = vizact.animation( random.randint(6,10) )
                        else:
                            # draw from all animations
                            anInds = [6, 7, 8, 9, 10, 14, 15, 16, 17, 18]
                            random.shuffle(anInds)
                            do   = vizact.animation(anInds[0])
                                
                        cClone.addAction(do, viz.tick())
                

    """Move avatar"""
    def routeAvatar(self, aId):
        
        # assign new waypoint            
        wp = self.UDPmanHdl.getAgentPos(aId)
        
        # get avatar by index
        # return -1 if this avaar has not been added yet
        avInd = self.getAvatarInd(aId)
                    
        if avInd == -1:
            avInd = self.addNewAvatar(aId, wp[0], wp[1])
            wp    = self.UDPmanHdl.getAgentPos(aId)
        
        if not self.oneCtx:
            if self.avatars[aId].getCtx() == 1:
                if self.sceneDefHdl.bbCtx2.isPinObst( np.array([wp[0], wp[1]]), 'world' ):
                    self.avatars[aId].visible(viz.OFF)
                    self.avatars[aId].isVisible = 0
                    warnings.warn("A red avatar (# %d) tried to enter the blue zone! (# action: %d)"%(aId, self.avatars[aId].getActionCtr()) )                
                            
            if self.avatars[aId].getCtx() == 2:
                if self.sceneDefHdl.bbCtx1.isPinObst( np.array([wp[0], wp[1]]), 'world' ):
                    self.avatars[aId].visible(viz.OFF)                
                    self.avatars[aId].isVisible = 0
                    warnings.warn("A blue avatar (# %d) tried to enter the red zone! (# action: %d)"%(aId, self.avatars[aId].getActionCtr()) )                
                
                
        if isinstance(wp, tuple):
            
            # define walking action
            walk = viz.ActionData()
            
            #walk.data = [wp[0], 0, wp[1], viz.AUTO_COMPUTE, viz.AUTO_COMPUTE, vizact.ROTATION_SPEED]
            walk.data = [wp[0], 0, wp[1], viz.AUTO_COMPUTE, None, vizact.ROTATION_SPEED] # prevents animation from resetting
            
            walk.verb  = 'walk'
        
            walk.turnInPlace = False
            walk.actionclass = vizact.VizWalkRotAction                                
        
            # add walk action
            self.avatars[avInd].addAction(walk)
            
        else:
            warnings.warn("Could not assign waypoint to %d"%aId)
                

        
    """Take snapshot of all avatars' positions and append to file"""
    def logAvatarPos(self):
        # function is called every 5 seconds
        
        # get timestamp
        cTstamp = viz.tick()
        
        # concat log file
        logFile = os.path.join(ct.PATH_TO_LOGFILE, self.avPosLogFile)
        
        # log avatar context once
        if not os.path.exists(logFile):
            f = open(logFile, 'w')
            charNameLine = ''
            ctxLine      = ''
            for cAv in self.avatars:                                
                charNameLine = charNameLine + "%s "%( cAv.getCharName() )
                ctxLine      = ctxLine      + "%s "%( cAv.getCtx() )
            
            # add eol string            
            charNameLine = charNameLine + '\n'
            ctxLine = ctxLine + '\n'
            
            # write to file
            f.write(charNameLine)
            f.write(ctxLine)
            f.close()
        
        # loop over avatars
        str2write = ''
        for cAv in self.avatars:
            
            if cAv.isVisible:            
                x, _, z = cAv.getPosition()
                #print "context: ",  cAv.getCtx()
            else:                            
                # avatar is invisible
                # -> get its clone's pos
                for cCl in self.actors:
                    if cCl.getAvID() == cAv.getAvID():
                        x, _, z = cCl.getPosition()
                        break
                                    
            str2write = str2write + "%s %s "%( round(x,2), round(z,2) )
        
        # add timestamp and new line string
        str2write = "%s "%round(cTstamp,2) + str2write + '\n'
        
        # write to file
        f = open(logFile, 'a')
        f.write(str2write)
        f.close()
    
        # finally log subject's position
        self.logSubjpos()
    
    """Log subject's position"""
    def logSubjpos(self):
        
        # concat log file
        logFile = os.path.join(ct.PATH_TO_LOGFILE, self.subjPosLogFile)
        
        # create file if non existent
        if not os.path.exists(logFile):
            f = open(logFile, 'w')
        else:
            f = open(logFile, 'a')
                        
        # get current time stamp
        cTstamp = viz.tick()
        
        # get current pos
        cSubjPos = viz.Vector(viz.MainView.getPosition())
        
        str2write = "%s %s "%( round(cSubjPos.x, 2), round(cSubjPos.z ,2) )
        
        # add timestamp and new line string
        str2write = "%s "%round(cTstamp,2) + str2write + '\n'
        
        # write to file        
        f.write(str2write)
        f.close()
        
        
      
"""Read pedSim data"""
class UDPlistener(threading.Thread):
    UDP_IP = "127.0.0.1"
    UDP_PORT = 2222

    sock     = []
    agentPos = [[]]
    
    """init UDP socket """
    def __init__(self):

        threading.Thread.__init__(self)
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        self.sock.bind((self.UDP_IP, self.UDP_PORT))

        # event for stopping UDP listener
        self._stopEvent = threading.Event()

        # stop UDP listener on exit
        vizact.onexit( self.stop )

    """stop thread"""
    def stop(self):
        self._stopEvent.set() 

    """Save avatar positions"""
    def saveAgentPos(self, x, y, aId):
                
        if len(self.agentPos) == 0:
            self.agentPos = [[]]
        else:
            if len(self.agentPos) < (aId+1):
                tmp = [[]]*(aId+1)
                tmp[0:len(self.agentPos)] = self.agentPos
                self.agentPos = tmp
        
        #self.agentPos[aId].append(np.array([x,y]))
        self.agentPos[aId].append( (x,y) )
        #print "saved: ", x, y
        #print self.agentPos[aId]
        
    """Parse XML data from UDP"""
    def parseUDP(self, data):
        tmpElement = xmle.fromstring(data)
        tmpPos = tmpElement.find('position')
        if tmpPos != None:
            tmp = tmpPos.items()
            if tmp[2][1] == "agent":
                #print "id: ", tmp[3][1], "Pos: x=", tmp[1][1], "y=", tmp[0][1]
                x   =  tmp[1][1]
                y   =  tmp[0][1] 
                aId =  tmp[3][1]
                # flip y axis as we go from pedSim to WorldViz coords
                return self.saveAgentPos(round(float(x),2), -round(float(y),2), int(aId))
    
    """Listen to UDP port"""
    def run(self):
        
        #while len(self.agentPos[-1]) < 10000:
        while not self._stopEvent.isSet():
            data, addr = self.sock.recvfrom(1024) # buffer size is 1024 bytes @UnusedVariable
            self.parseUDP(data)
            #print data
        
        # close UDP socket
        self.sock.close()
        print "UDP listener stopped!" 
        
    def getAgentPos(self, aId):
        if len(self.agentPos[aId]) > 0:        
            return self.agentPos[aId].pop(0)
        else:
            warnings.warn("No waypint for avatar %d"%aId)
            return 0
    
    def countWPs(self, aId):        
        if len(self.agentPos) < aId+1:
            return 0
        else:
            nWPs = len(self.agentPos[aId])
            #print "%d waypoints for avId %d"%(nWPs, aId)
            return nWPs
    