# -*- coding: utf-8 -*-
import viz
import vizfx
import vizact
import vizinfo
import viztask
import vizmat
import vizcam
import vizproximity

import os
import re
import glob
import random
import codecs
import textwrap

import vizmultiprocess

import numpy as np
from collections import deque

from shapely.geometry import Polygon
from shapely.geometry import Point
from shapely.geometry import mapping

import constants  as ct
import pathfinder as pf
import logger     as log

from distutils.dist import warnings



"""Handles HUD"""
class ParcelMsg:
    def __init__(self, mTitle = ''):
        
        # read in text files containing
        # task instructions and feedback
        # return a dict containing lists for pickup and drop (fast, slow, late)
        #txtFiles     = ['pickup', 'dropFast', 'dropSlow', 'dropLate', 'targetInfoSame', 'targetInfoCross', 'dropShortDist', 'dropLongDist']
        txtFiles     = ['pickup', 'dropFast', 'dropLate', 'targetInfoSame', 'targetInfoCross']
        self.msgs    = {}
        self.msgs["nice"]  =  self.readInMsgs(txtFiles, ctxMood="Nice" )
        self.msgs["angry"] =  self.readInMsgs(txtFiles, ctxMood="Angry")
                                
        # add info panel
        #self.panel = vizinfo.InfoPanel('')
        self.panel = vizinfo.InfoPanel('', align=viz.ALIGN_CENTER_TOP)
        self.panel.visible(viz.OFF)

        self.themes  = {}
        
        # add separator
        self.panel.addSeparator()
        
        # used for distance tracking
        self.lastPos            = None
        self.distTravelled      = 0        
        
        # set standard panel theme
        stdTh = viz.Theme()
        stdTh.borderColor       = ( 0.0, 0.5, 0.0 )
        stdTh.backColor         = ( 1.0, 1.0, 1.0 )
        stdTh.highBackColor     = ( 0.5, 0.5, 0.5 )
        stdTh.highTextColor     = ( 0.0, 0.0, 0.0 )
        stdTh.textColor         = ( 0.0, 0.0, 0.0 )
        self.themes["standard"] = stdTh
        
        # set green panel theme
        greenTh = viz.Theme()                
        greenTh.borderColor    = ( 0.0, 0.5, 0.0 )
        greenTh.highBackColor  = ( 0.0, 1.0, 0.0 )
        greenTh.highTextColor  = ( 0.0, 0.0, 0.0 )
        greenTh.textColor      = ( 0.0, 0.0, 0.0 )
        self.themes["green"]   = greenTh
        
        # set yellow panel theme
        yellowTh = viz.Theme()
        yellowTh.borderColor    = ( 0.0 ,0.5, 0.0 )        
        yellowTh.highBackColor  = ( 1.0 ,1.0, 0.0 )
        yellowTh.highTextColor  = ( 0.0, 0.0, 0.0 )
        yellowTh.textColor      = ( 0.0, 0.0, 0.0 )
        self.themes["yellow"]   = yellowTh
        
        # set red panel theme
        redTh = viz.Theme()
        redTh.borderColor    = ( 0.0 ,0.5, 0.0 )
        redTh.highBackColor  = ( 1.0 ,0.0, 0.0 )
        redTh.highTextColor  = ( 0.0, 0.0, 0.0 )
        redTh.textColor      = ( 0.0, 0.0, 0.0 )
        self.themes["red"]   = redTh
                
        # start with green theme
        self.panel.getPanel().setTheme(self.themes["standard"])        
        
        # add text        
        self.line1 = self.panel.addItem(viz.addText(' '))
        self.line1.setEncoding(viz.ENCODING_UTF8)
        
        self.line2 = self.panel.addItem(viz.addText(' '))
        self.line2.setEncoding(viz.ENCODING_UTF8)
        
        # add progress bar to show time elapsing for current order
        # add separator
        self.panel.addSeparator()
        self.progBar       = self.panel.addItem(viz.addProgressBar(''))
        self.progBar.scale(0,0)
        self.progBar.visible(viz.OFF)
        self.progBarEvtHdl = None # handle to progress bar update event
        self.tEst          = None # estimated time to get parcel
                
        # get icon images
        self.iconTxs = {}
        iconFiles = glob.glob( os.path.join(ct.PATH_TO_ICONS, '*.jpg') ) # each folder corresponds to one character
        p = re.compile(r"_[a-z]*\d_") # e.g. look for .*_bakery1_.*
        for cTex in iconFiles:
            m    = p.search(cTex)
            iKey = cTex[m.span(0)[0]+1 : m.span(0)[1]-1] # take only bakery1 as key
            self.iconTxs[iKey] = viz.addTexture(cTex)
    
        # add quad
        self.texQuad = viz.addTexQuad(size=0)
        self.qNode   = self.panel.addItem(self.texQuad) # add quad to panel
        #self.qNode   = self.panel.addItem('Delivery Target', self.texQuad) # add quad to panel        
        self.line3   = self.panel.addItem(viz.addText(' '))
        self.line3.setEncoding(viz.ENCODING_UTF8)
        
    
    """Read in instructions / feedback from txt file"""
    def readInMsgs(self, txtFiles, ctxMood):
        msgDict = {}
        for cFile in txtFiles:
            
            # concat current txt file
            cFullFile = "%s%s.txt"%(cFile, ctxMood)
            cFullFile = os.path.join(ct.PATH_TO_TEXT, cFullFile)
                        
            with codecs.open(cFullFile, encoding='utf-8') as f:
                content = f.readlines()
                # you may also want to remove whitespace characters like `\n` at the end of each line
                content = [textwrap.fill(x.strip(), 40) for x in content]                
                
            # save to dict 
            msgDict[cFile] = content            
            
        return msgDict
    
    """Called to update time bar"""
    def updateTimeBar(self, t0):
        t = viz.tick()

        if not self.tEst:
            print "WARNING: No time estimate set!"
            return

        if t-t0 < self.tEst:
            cStep = 1-(t-t0)/self.tEst
            self.progBar.set(cStep)
            
            # how much time is left?
            if 1 >= cStep >= 0.75:
                cTheme = self.themes["green"] 
                self.line2.message('Plenty of time!')
            elif 0.75 > cStep >= 0.5:
                cTheme = self.themes["yellow"]
                self.line2.message('Keep it going!')
            else:
                cTheme = self.themes["red"]
                self.line2.message('Hurry up!')
                        
            # change color of time bar
            if not viz.getTheme() == cTheme:
                self.panel.getPanel().setTheme(cTheme)
                self.line1.color(self.l1col)
                self.line2.color(self.l2col)
                self.line3.color(self.l3col)
        
        # stop event handler
        else:
            self.progBarEvtHdl.setEnabled(viz.OFF)
    
    """Update distance bar for distance task"""
    def updateDistBar(self, xyzP, xyzD):
        xP, _, zP = xyzP
        startVec = viz.Vector(xP, 0, zP)
        
        xD, _, zD = xyzD
        goalVec = viz.Vector(xD, 0, zD)
        
        xV, _, zV = viz.Vector(viz.MainView.getPosition(viz.ABS_GLOBAL))
        viewVec = (xV, 0, zV)
        
        # get goal distance between start and goal
        goalDist = (goalVec - startVec).length()
        
        # get goal distance from current viewPoint
        cGoalDist = (goalVec - viewVec).length()
                    
        # compare current and last distance to goal
        if self.lastPos:
            lastGoalDist = (self.lastPos - goalVec).length()
            if cGoalDist <= lastGoalDist:
                self.progBar.message('Getting closer!')
            else:
                self.progBar.message('Wrong direction!')
            
            # get overall distance travelled
            self.distTravelled = self.distTravelled + (self.lastPos - viewVec).length()
        else:
            # on first update: reset distance travelled
            self.distTravelled = 0
        
        # save this view pos for next update
        self.lastPos = viz.Vector(viewVec)
        
        # normalise distance by initial goal distance
        distVal = (goalDist - cGoalDist)/goalDist
        self.progBar.set(distVal)
        
        # while we haven't reached goal
        if cGoalDist > 1:
            # how close are we to the goal?
            if 1 >= distVal >= 0.75:
                cTheme = self.themes["green"]
            elif 0.75 > distVal >= 0.5:
                cTheme = self.themes["yellow"]
            else:
                cTheme = self.themes["red"]
                        
            # change color of time bar
            if not viz.getTheme() == cTheme:
                self.panel.getPanel().setTheme(cTheme)                
                self.line1.color(self.l1col)
                self.line2.color(self.l2col)
                self.line3.color(self.l3col)
                
        # stop event handler
        else:                                        
            print "Unset EvtHandle"
            self.progBarEvtHdl.setEnabled(viz.OFF)
            self.lastPos = None
                        
        
        
    """Set path distance"""
    def setEstT(self, tEst):
        self.tEst = tEst
            
    """Show new pickup info"""
    def showPickupInfo(self, cTrial, cTrialNr, nTrials):
        # start from clear panel
        self.resetMsg()
        self.panel.getPanel().setTheme(self.themes["standard"])
        
        if self.progBarEvtHdl:
            self.resetProgBar()
                
        # show incoming message
        if cTrial.getCtx("pickup") == 1:
            if ct.LANGUAGE == 'EN':
                mStr = "New order from a red resident! (%d of %d)"%(cTrialNr, nTrials)
            elif ct.LANGUAGE == 'DE':
                mStr = "Neuer Auftrag von rotem Bewohner! (%d von %d)"%(cTrialNr, nTrials)                
            self.line1.color(viz.RED)
            
        elif cTrial.getCtx("pickup") == 2:
            if ct.LANGUAGE == 'EN':
                mStr = "New order from a blue resident! (%d of %d)"%(cTrialNr, nTrials)
            elif ct.LANGUAGE == 'DE':
                mStr = "Neuer Auftrag von blauem Bewohner! (%d von %d)"%(cTrialNr, nTrials)
            self.line1.color(viz.BLUE)
            
        # write pickup message in first line of panel
        self.line1.message(mStr)
        self.line1.fontSize(20)
        self.panel.visible(viz.ON)
        
    
    """Show target information"""
    def showTargetInfo(self, taskType, cTrial):
                        
        # start from clear panel
        self.resetMsg()
        self.panel.getPanel().setTheme(self.themes["standard"])
        
        # get random pickup message
        msg = random.choice( self.msgs[cTrial.getMood("pickup")]['pickup'] )
        self.line1.message(msg)
        self.line1.fontSize(20)
        self.l1col = viz.BLACK
        #self.line1.color(viz.BLACK)
        
        # for within context delivery
        if cTrial.getCtx("pickup") == cTrial.getCtx("drop"):
            msg = random.choice( self.msgs[cTrial.getMood("pickup")]['targetInfoSame'] )
             
        # for across context delivery
        else:
            msg = random.choice( self.msgs[cTrial.getMood("pickup")]['targetInfoCross'] )
        
        # get context color and drop target name
        if ct.LANGUAGE == 'EN':
            cols  = ["red", "blue"]
            cTargetName = cTrial.dZone.name[0:-1]                        
        elif ct.LANGUAGE == 'DE':
            cols  = ["rot", "blau"]
            cTargetName = ct.DROP_DICT[ cTrial.dZone.name[0:-1] ]
                                                                    
        cCol  = cols[cTrial.getCtx("drop")-1]
        msg = msg.replace('|TARGET|',  cTargetName)    
        msg = msg.replace('|CONTEXT|', cCol)
        msg = textwrap.fill(msg, 40)
        self.line2.message(msg)
        self.line2.fontSize(20)
        self.l2col = viz.BLACK
        #self.line2.color(viz.BLACK)
        
        # show target icon
        self.texQuad.texture(self.iconTxs[cTrial.dZone.name])
        self.qNode.setSize(100)
        self.qNode.visible(viz.ON)
        
        # show target name in context color        
        if   cTrial.getCtx("drop") == 1:            
            #self.l3col = viz.RED
            self.l3col = viz.BLACK
            if ct.LANGUAGE == 'EN':
                #msg = "%s%s with red owner"%(cTargetName[0].upper(), cTargetName[1:])
                msg = "%s%s"%(cTargetName[0].upper(), cTargetName[1:])
            elif ct.LANGUAGE == 'DE':
                #msg = "%s%s mit rotem Besitzer"%(cTargetName[0].upper(), cTargetName[1:])                
                msg = "%s%s"%(cTargetName[0].upper(), cTargetName[1:])                
        elif cTrial.getCtx("drop") == 2:
            #self.l3col = viz.BLUE
            self.l3col = viz.BLACK
            if ct.LANGUAGE == 'EN':
                #msg = "%s%s with blue owner"%(cTargetName[0].upper(), cTargetName[1:])
                msg = "%s%s"%(cTargetName[0].upper(), cTargetName[1:])
            elif ct.LANGUAGE == 'DE':
                #msg = "%s%s mit blauem Besitzer"%(cTargetName[0].upper(), cTargetName[1:])
                msg = "%s%s"%(cTargetName[0].upper(), cTargetName[1:])
        self.line3.message(msg)
        
        # show progress bar
        self.progBar.visible(viz.ON)
        self.progBar.scale(1,1)
            
        # register to update event
        # disable user movement until user is ready
        vizcam.WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=0, turnScale=0.0)
        
        # move viewpoint to watch avatar
        x,_,z = cTrial.pZone.getViewXYZ()
        viz.MainView.setPosition(x, 0, z)
        _,_,_,degs = cTrial.pZone.pNode.getAxisAngle()
        viz.MainView.setAxisAngle(0, 1, 0, degs)
        
        viztask.schedule( self.startTask() )
    
        # show panel
        self.panel.visible(viz.ON)
    
    """Wait for key press to start time task"""
    def startTask(self):
        self.line3.color(self.l3col)
        yield viztask.waitKeyDown('e')
        
        # re-assign walknav and start task
        vizcam.WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=ct.MOVE_SPEED, turnScale=1.0)
        if ct.TASK_TYPE == "distance":
            self.progBarEvtHdl = vizact.onupdate(0, self.updateDistBar,  viz.tick())
        elif ct.TASK_TYPE == "time":
            self.progBarEvtHdl = vizact.onupdate(0, self.updateTimeBar,  viz.tick())
        else:            
            warnings.warn("taskType must be either \'timeTask\' or \'distTask\'")
    
    """Wait for key press to finish task"""
    def finishTask(self):
        yield viztask.waitKeyDown('e')
        
        # re-assign walknav and start task
        vizcam.WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=ct.MOVE_SPEED, turnScale=1.0)
        
    """Show success"""
    def showSuccess(self, cTrial, pDistAstar, taskPerf):
                        
        self.panel.getPanel().setTheme(self.themes["standard"])
                        
        if ct.TASK_TYPE == "distance":
            # gets 1 if dist travelled == goal dist
            relDistTravelled = self.distTravelled/pDistAstar            
            taskPerf.addTrial(relDistTravelled)            
            if relDistTravelled < 1.5:
                msgKey = 'dropShortDist'
            else:
                msgKey = 'dropLongDist'
            distInfo = "You travelled %d%s of optimal distance (mean performance: %d) "%(round(relDistTravelled*100), "%", round(taskPerf.getMeanPerf()*100))
            perf = relDistTravelled
                
        elif ct.TASK_TYPE == "time":
            # any time left?
            perf = self.progBar.get()
            taskPerf.addTrial(perf)            
            if round(perf*100) == 0:
                msgKey = 'dropLate'
                if ct.LANGUAGE == 'EN':
                    distInfo = "You ran out of time! (mean time saved: %d %s)"%(round(taskPerf.getMeanPerf()*100), "%")
                elif ct.LANGUAGE == 'DE':
                    distInfo = "Die Zeit ist abgelaufen! (Zeit gespart im Mittel: %d %s)"%(round(taskPerf.getMeanPerf()*100), "%")
            else:
                msgKey = 'dropFast'
                if ct.LANGUAGE == 'EN':
                    distInfo = "You delivered in time! (time saved: this trial %d %s mean: %d %s)"%(round(perf*100), "%", round(taskPerf.getMeanPerf()*100), "%")
                if ct.LANGUAGE == 'DE':
                    distInfo = "Du hast rechtzeitig geliefert! (gesparte Zeit: %d %s; Zeit gespart im Mittel: %d %s)"%(round(perf*100), "%", round(taskPerf.getMeanPerf()*100), "%")
                
        
        # disable user movement until user is ready
        vizcam.WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=0, turnScale=0.0)
        
        # move viewpoint to watch avatar
        x,_,z = cTrial.dZone.getViewXYZ()
        viz.MainView.setPosition(x, 0, z)
        _,_,_,degs = cTrial.dZone.pNode.getAxisAngle()
        viz.MainView.setAxisAngle(0, 1, 0, degs)
        
        viztask.schedule( self.finishTask() )
                              
        # get messages
        msg = random.choice( self.msgs[cTrial.getMood("drop")][msgKey] )
                        
        self.line1.message(msg)
        self.line2.message(distInfo)
        self.line2.fontSize(15)
        self.panel.visible(viz.ON)
        
        # reset progbar
        self.resetProgBar()
        self.progBar.visible(viz.OFF)
        self.progBar.scale(0,0)
        
        # reset dist vars        
        self.lastPos = None
        
        return        
    
        
    """Reset panel"""
    def resetMsg(self):
        # delete text
        self.panel.setText('')
        self.line1.message('')
        self.line2.message('')
        self.line3.message('')
        
        # reset text color to black        
        self.line1.color(viz.BLACK)
        self.line2.color(viz.BLACK)
        self.line3.color(viz.BLACK)
        
        # hide panel
        self.panel.visible(viz.OFF)
        
    """Reset icon"""
    def resetIcon(self):
        self.qNode.setSize(0)
        self.qNode.visible(viz.OFF)

    """Reset progress bar"""
    def resetProgBar(self):
        # unregister update event        
        if self.progBarEvtHdl.getEnabled():
            self.progBarEvtHdl.setEnabled(viz.OFF) # unregister event

        self.progBar.set(1)


"""Subclass of  pathfinder's grid class. Handles grid of town scene"""
class TownGrid(pf.GridWithWeights):
    def __init__(self, xMin, xMax, zMin, zMax, gStep):
        
        width  = int( round(( abs(xMin - xMax) )/gStep ) )
        height = int( round(( abs(zMin - zMax) )/gStep ) )            
        
        pf.GridWithWeights.__init__(self, width, height)
    
        self.width  = width
        self.height = height
        self.gStep  = gStep
        
        self.xMinBB = xMin
        self.xMaxBB = xMax
        self.zMinBB = zMin
        self.zMaxBB = zMax
        
        self.recPath  = []        
        self.pathNode = []
        
        
    """Add walls to grid"""
    def addObstacle(self, oPoly):
        crns = mapping(oPoly)
        crns = np.squeeze(np.array(crns["coordinates"]))
                
        # get xz coords    
        xMin = crns[:,0].min()
        xMax = crns[:,0].max()
        
        zMin = crns[:,1].min()
        zMax = crns[:,1].max()

        #print "x min / max: ", xMin, " " ,xMax
        #print "z min / max: ", zMin, " " ,zMax

        #print "---"
        #print crns

        # map to node space
        xStart = np.ceil(( xMin + np.abs(self.xMinBB)) / self.gStep) -1
        xStop  = np.ceil(( xMax + np.abs(self.xMinBB)) / self.gStep) +1
                                
        zStart = np.ceil(( zMin + np.abs(self.zMinBB)) / self.gStep) -1
        zStop  = np.ceil(( zMax + np.abs(self.zMinBB)) / self.gStep) +1

        # check which nodes fall in current obstacle        
        for cX in np.arange(xStart, xStop):
            
            for cZ in np.arange(zStart, zStop):
                
                x2check = (cX*self.gStep) - abs(self.xMinBB)
                z2check = (cZ*self.gStep) - abs(self.zMinBB)
                
                if oPoly.contains( Point(x2check, z2check) ):
                    #self.walls.append( (cX-1, cZ-1) )                    
                    self.walls.append( (cX-1, cZ-1) )
                    
        #pf.draw_grid(self.grid)
        
    """Searches for passable point closest in grid to x,z world coords"""
    def findPassablePoint(self, x, z):
        
        # get row/col grid coords of x/z real world coords
        iP = int( round( ( x + abs(self.xMinBB)) / self.gStep ) )
        jP = int( round( (-z + abs(self.zMinBB)) / self.gStep ) ) # flip z axis: world -> A*
        
        # while p is not passable -> look for closest neighbor
        cIt       = 1
        cXoffsets = [] 
        cZoffsets = []
        while 1:
                
            P = (iP, jP)
            if self.passable(P):
                return P
            
            print "Looking for neighbor -> iteration: %d"%cIt
            
            cXoffsets = [0,        0,       0.1*cIt, -0.1*cIt] 
            cZoffsets = [0.1*cIt, -0.1*cIt, 0,        0,     ]
            
            for i in range(len(cXoffsets)):                
                iP = int( round( ( x + abs(self.xMinBB  + cXoffsets[i])) / self.gStep ) )
                jP = int( round( (-z + abs(self.zMinBB  + cZoffsets[i])) / self.gStep ) ) # flip z axis: world -> A*
                
                P = (iP, jP)
                if self.passable(P):
                    return P

            cIt = cIt+1        
    
    """Get best path from pStart to pGoal using A* algorithm"""
    def findPath(self, pStart, pGoal):
        
        print "Searching best path ..."
        
        if len(pStart) == 2:
            xS, zS = pStart            
        elif len(pStart) == 3:
            xS, _, zS = pStart
            
        if len(pGoal) == 2:    
            xG, zG = pGoal
        elif len(pGoal) == 3:
            xG, _, zG = pGoal

        # get passable start and goal points in grid from x,z world coords
        S = self.findPassablePoint(xS, zS)
        G = self.findPassablePoint(xG, zG)
                
        # get best path
        cameFrom, _ = pf.a_star_search(self, S, G)
        
        # reconstruct path        
        self.recPath = pf.reconstruct_path(cameFrom, start=S, goal=G)
        
        # DEBUGGING: draw grid
        #pf.draw_grid(self, width=2, path=self.recPath)
        
        return self.recPath
    
    """Draw path in worldviz space"""
    def getPathDist(self, path=[], drawPath=0):
        viz.startLayer(viz.LINE_STRIP)
        viz.lineWidth(10)
        viz.vertexColor(1,0,0)
        
        # if not path was submitted use property var
        if not path:
            path = self.recPath
        
        prevV    = []
        pathDist = 0
        pathXZ   = []        
        for cN in path:
            i, j = cN
            x = (i*self.gStep)-abs(self.xMinBB)
            z = (j*self.gStep)-abs(self.zMinBB)
                                    
            # get distance
            if prevV:
                pathDist = pathDist+vizmat.Distance( prevV, (x,0,z)  )
            
            prevV = [x, 0, z]                            
                            
            # flip z-axis: grid -> world
            viz.vertex(x, 1, -z) # Vertices are split into pairs.
            pathXZ.append( (x,-z) ) # save xz sequence for logging
        
        # remove previous path
        if self.pathNode:
            self.pathNode.remove()
        
        # draw path
        if drawPath:
            self.pathNode = viz.endLayer()
        
        # DEBUGGING
        #print "PathDist: ",  pathDist
        
        return pathDist, pathXZ



"""Defines parcel pickup and drop zones"""
class ParcelZone(vizproximity.Sensor):
    def __init__(self, name, pNode, ctx):
        
        # get entrance                                
        sCtr = np.array(pNode.getMatrix(viz.ABS_LOCAL, node='entrance').getPosition())
        bbL  = pNode.getBoundingBox(mode=viz.ABS_LOCAL)
        sBox = 3 # box size of zone
        
        self.name     = name
        self.ctx      = ctx
        self.avLoc    = [sCtr[0], 0, sCtr[2]-0.5] # ABS_LOCAL
        self.arLoc    = [0, bbL.ymax+0.5, 0]      # ABS_PARENT
        self.paLoc    = [sCtr[0], .5, sCtr[2]-2 ] # ABS_LOCAL
        self.viewLoc  = [sCtr[0], .5, sCtr[2]-5 ] # ABS_LOCAL
        self.pNode    = pNode
        self.status   = 0

        # define shapely objects                
        # flip z-axis: world -> grid
        cCrns  = self.getParentCorners('grid')
        self.shPoly = Polygon(cCrns)

        # call parent constructor and create actual sensor
        vizproximity.Sensor.__init__(self, vizproximity.Box([sBox,sBox,sBox], center=[sCtr[0], sBox/2.0, sCtr[2]-sBox/2.0]), source=pNode)
    
    """Return this zone's parent node name"""
    def getHouseName(self):
        return self.name
    
    """Return this zone's context"""
    def getCtx(self):
        return self.ctx
    
    """gets global xy coords of pickup and drop zones"""
    def getZoneXYZ(self, reFrame=viz.ABS_GLOBAL):
        # temporarily add vertex to track parcel pos in abs coords
        viz.startLayer(viz.POINTS)
        viz.vertexColor(1,0,0)
        viz.pointSize(30)
        viz.vertex(0,0,0)
        cV = viz.endLayer()
        cV.setParent(self.pNode)                                    
        cV.setPosition(self.paLoc, mode=viz.ABS_LOCAL)
        cV.visible(viz.OFF)
        zoneXYZ = cV.getPosition(mode=reFrame)                        
        cV.remove()
        
        return zoneXYZ  
    
    """gets global xy coords of pickup and drop zones"""
    def getViewXYZ(self, reFrame=viz.ABS_GLOBAL):
        # temporarily add vertex to track parcel pos in abs coords
        viz.startLayer(viz.POINTS)
        viz.vertexColor(1,0,0)
        viz.pointSize(30)
        viz.vertex(0,0,0)
        cV = viz.endLayer()
        cV.setParent(self.pNode)                                    
        cV.setPosition(self.viewLoc, mode=viz.ABS_LOCAL)
        cV.visible(viz.OFF)
        zoneXYZ = cV.getPosition(mode=reFrame)                        
        cV.remove()
        
        return zoneXYZ
    
    
    """Get pos bahind door"""
    def getDoorXYZ(self, refFrame=viz.ABS_GLOBAL):
        x,y,z = np.array(self.pNode.getMatrix(refFrame, node='behindDoor').getPosition())
                        
        if (x,y,z) == (0,0,0):
            print "Could not find \'behindDoor\' child node"
            return -1
        
        return (x,y,z)
    
    """Get polygon corners of parent node"""
    def getParentCorners(self, quSpace):
        nBox = self.pNode.getBoundingBox(viz.ABS_LOCAL)
        
        cCrns         = [ (nBox.xmin, 0, nBox.zmin), (nBox.xmin, 0, nBox.zmax), (nBox.xmax, 0, nBox.zmax), (nBox.xmax, 0, nBox.zmin) ]
        globalCrns    = []        
        
        singleVertChildren = []
        for c in self.pNode.getChildren():
            if c.__class__ == viz.VizPrimitive:
                singleVertChildren.append( c )
                        
        i = 0    
        for cC in cCrns:        

            # add helper vertices if this node does not contain
            # four children -> heuristic
            if not len(singleVertChildren) == 4:
                # create vertex
                viz.startLayer(viz.POINTS)
                viz.vertexColor(1,0,0)
                viz.pointSize(30)
                viz.vertex(0,0,0)
                cV = viz.endLayer()
                
                # set obst as parent
                cV.setParent(self.pNode)
                
                # move to parent's corner
                x,y,z = cC
                cV.setPosition(x, y, z, viz.ABS_PARENT)
                
            else:
                cV = singleVertChildren[i]
            
            # get global coords
            x,y,z = cV.getPosition(viz.ABS_GLOBAL)
            
            # flip z axis to get from world to grid space
            if quSpace == 'grid':
                z=-z
                
            globalCrns.append( (x,z) )
                            
            # remove this vertex
            #cV.remove()
            
            i=i+1
        
        #print "grid obst: ", globalCrns
        return globalCrns



"""Computes shortest path between two points using the A* algorithm
does it in the background using 'vizmultiprocess' """
class PathQueue:        
    def __init__(self, sXYs, gXYs, tGrid):
        
        self.pollMsg    = "Polling ..."
        self.queueMsg   = "nPaths in queue ..."
                
        self.tGrid      = tGrid # town grid handle
        
        self.qSize      = ct.N_MAX_PATHS_IN_QUEUE
        
        self.sXYs       = deque(sXYs) # deque with start coords
        self.gXYs       = deque(gXYs) # deque with goal  coords
 
        # stores list indices of drop and pickup zones and paths in queue
        self.qStartInds = deque()
        self.qGoalInds  = deque()
        self.qPaths     = deque()
                 
               
    """Check order queue"""
    def checkQueue(self):
        # check queue
        while 1:
            
            # if start and goal coords are defined
            if self.sXYs and self.gXYs:
                
                # if queue is not full
                if len(self.qPaths) < self.qSize:
                    print self.queueMsg, len(self.qPaths)
                    
                    # prepare fillQueue params
                    startPos, goalPos, optDict = self.prepareFilling()
                    
                    # fill queue
                    pathData = yield vizmultiprocess.waitCallProcess(self.fillQueue, startPos, goalPos, optDict)
            
                    # save results
                    if pathData:
                        self.assignResults(pathData)
                    else:
                        print "No valid path found!"
                
                else:
                    # poll every 5 seconds
                    print self.pollMsg
                    yield viztask.waitTime(5)
            else:
                    # poll every 1 seconds
                    print "Waiting for next task ..."
                    yield viztask.waitTime(1)
    
    """assign results from parallel process"""
    def assignResults(self, pData):
        # override to your needs
        return 0
    
    """called before fillQueue"""
    def prepareFilling(self):
        return 0
        
                    
    """update queue constantly"""
    def fillQueue(self):
        # override according to your needs
        return 0


"""Handles Orders -> Inherits from PathQueue. Searches for best path between pickup and drop zones"""
class OrderQueue( PathQueue ):
    def __init__(self, pZxys, dZxys, tGrid, **kw):
        PathQueue.__init__(self, pZxys, dZxys, tGrid, **kw)
        
        # track trials
        self.trialNr = -1
        self.qTrialNrs = deque() # save trial nrs
        
        self.pollMsg  = "Polling delivery queue -> full ..."
        self.queueMsg = "n paths in delivery queue" 
    
    """called on new round"""
    def refreshQeue(self, sXYs, gXYs):
        self.trialNr   = -1
        self.sXYs      = deque(sXYs) # deque with start coords
        self.gXYs      = deque(gXYs) # deque with goal  coords             
        self.qPaths    = deque()
        
    """update queue constantly"""
    def fillQueue(self, S, G, optDict):      
        # get shortest route between S and G        
        cPath = self.tGrid.findPath(S, G)        
        
        resDict = optDict.copy()
        resDict.update( {"path" : cPath} )
        
        return resDict

    """Get random start, goal targets"""
    def prepareFilling(self):
        
        # start and goal coords of this trial
        S = self.sXYs.popleft()
        G = self.gXYs.popleft()            
                
        self.trialNr = self.trialNr+1

        return S, G, {"trialNr" : self.trialNr}

    """assign results"""
    def assignResults(self, pData):
        # save results        
        self.qTrialNrs.appendleft(pData.returnValue["trialNr"])
        self.qPaths.appendleft(pData.returnValue["path"])

    """child method to get next order from queue"""
    def getOrder(self):
        if len(self.qPaths) > 0:        
            return {"trialNr" : self.qTrialNrs.pop(), "path" : self.qPaths.pop()}
        else:
            return 0


"""Calculates closest path to next building"""
class HomeTargetQueue( PathQueue ):
    def __init__(self, tGrid, oneCtx=0, **kw):
        PathQueue.__init__(self, [], [], tGrid, **kw)
        
        self.pollMsg  = "Polling target queue -> full ..."
        self.queueMsg = "n paths in target queue" 
        
        self.oneCtx = oneCtx
        
        self.targetXYZ = []
        self.ctx       = []        
        self.results   = []
        
        # used to link orders and distances
        self.taskIDs   = deque()
        
        # save index to pickup zone
        self.targetInd = deque()

    """add targets with context"""
    def addTargets(self, targList, ctxList):
        self.targetXYZ = targList
        self.ctx       = ctxList

    """find closest target between xyz and house entrance
    puts start and end coords to cue which will the trigger path search algorithm"""
    def findPath(self, xyz, ctx, cloneID):
        # get euclidean distances between current pos and all entrances
        cDists = [Point(xyz).distance( Point(cT) ) for cT in self.targetXYZ]
        
        # find closest point in same context
        foundMin = 0
        while not foundMin:
            cMin = min(cDists)
            cInd = cDists.index(cMin)
            
            # check for context
            if not self.oneCtx:            
                if self.ctx[cInd] == ctx:
                    foundMin = 1
                else:
                    cDists[cInd] = max(cDists)+1
                    
            # take closest house of any context
            else:                
                foundMin = 1            
                 
        
        # put closest point to queue
        self.sXYs.appendleft(xyz)
        self.gXYs.appendleft(self.targetXYZ[cInd])
        
        # used to link task and clone via cloneID
        self.taskIDs.appendleft(cloneID)
        
        # store pickup zone index
        self.targetInd.appendleft(cInd)
    
    """Called before fillQueue"""
    def prepareFilling(self):
        # get next start and stop pos from queue
        S          = self.sXYs.pop()
        G          = self.gXYs.pop()
        taskID     = self.taskIDs.pop()
        cTargetInd = self.targetInd.pop()
        
        #debugging
        #G = (0,0)
        
        return S, G, {"taskID" : taskID, "targetInd" : cTargetInd}
               
    """Fill queue"""
    def fillQueue(self, S, G, optDict):
        
        # get shortest route between S and G        
        cPath = self.tGrid.findPath(S, G)
        
        resDict = optDict.copy()
        resDict.update( {"path" : cPath} )
                    
        return resDict
        
    """assign results"""
    def assignResults(self, pData):
        # save results
        cResults = pData.returnValue
        
        _, pathXZ = self.tGrid.getPathDist(path=cResults["path"], drawPath=0)
        cResults["path"] = pathXZ         
        self.results.append(cResults)
    
    """get results"""
    def getTarget(self, taskID):       
        # get result                    
        cResult = False
        
        if self.results:
            #print self.results        
            #print  "para = ", taskID, "vars ", [r["path"] for r in self.results]
            
            # delete from list
            if self.results:
                                
                cResult = [d for d in self.results if d["taskID"] == taskID]
                if len(cResult) == 1:
                    cResult = cResult[0]
                elif len(cResult) > 1:
                    warnings.warn("Found double entry of taskID!")
                    return False                                    
                
                if cResult:
                    self.results[:] = [d for d in self.results if d["taskID"] != taskID]
                
        return cResult
        

"""Replaces vizfx.addAvatar -> use extended Avatar class"""
def addHouseResident(ctx, parent = viz.WORLD, scene = viz.MainScene, flags=0, **kw):
    """vizfx: Add an avatar to the scene"""
     
    # get number of different characters that will
    # appear in our scene.
    charNames  = os.listdir(ct.AVATAR_PATH) # each folder corresponds to one character
    nChars     = len(charNames)
     
    # get random character
    cCharName = charNames[random.randint(0, nChars-1)]
     
    if ctx == 1:
        cCharInCtx = cCharName+'Red.cfg'
    elif ctx == 2:
        cCharInCtx = cCharName+'Blue.cfg'
    else:
        print "Context must be either 1 or 2"
     
    # concat filename
    filename = os.path.join(ct.AVATAR_PATH, cCharName, cCharInCtx)    
    
    # get resident
    model = HouseResident(viz._ipcSend(viz._VIZ_ADDAVATAR, viz._sceneID(scene), int(parent), filename, flags, 0.0, 0.0, 0.0),**kw)
            
    if model:
        if model.getAsyncStatus() == viz.ASYNC_LOADING:
            vizact.onAsyncLoad(model, vizfx._modelAsyncLoad, viz.EFFECTGEN_DEFAULT, vizfx.getComposer(vizfx.DEFAULT_COMPOSER))
        else:
            model.generateEffects(viz.EFFECTGEN_DEFAULT, vizfx.getComposer(vizfx.DEFAULT_COMPOSER))
 
    # rotate by 180 degree
    model.setAxisAngle(0, 1, 0, 180)
    model.state(1)    
    
    return model

"""Controls behaviour of house residents"""
class HouseResident( viz.VizAvatar ):
    def __init__(self, id, **kw):  # @ReservedAssignment
        viz.VizAvatar.__init__(self, id, **kw)        
   
        # set avatar type to prevent automatic
        # action updating
        self.avType      = 'houseResident'
        self.activeTasks = []
    
        self.avID     = None
        self.avCtx    = None # context 1 or 2
        self.charName = None
    
        # pickup / drop zones
        self.dZone = None
        self.pZone = None
    
    def setID(self, aId, charName=None):
        self.avID = aId
        if charName:
            self.charName = charName
    
    def getAvType(self):
        return self.avType
        
    def getID(self):
        return self.avID
                
    def setCtx(self, ctx):
        self.avCtx = ctx
        
    def setAvType(self, avtType):
        self.avType = avtType
        
    def getCtx(self):
        return self.avCtx
   
    def getCharName(self):
        return self.charName 
    
    
    """Kill running tasks"""
    def killTasks(self):
        for cTask in self.activeTasks:
            cTask.kill()
    
    """store task in list to delete them later on"""
    def addTask(self, task):
        self.activeTasks.append( task )
                        
    """Show receive parcel action sequence""" 
    def receiveParcel(self, cTrial, oneCtx=0):
        
        # save for later use
        self.dZone = cTrial.dZone
        
        # open door
        self.dZone.pNode.setAnimationState( viz.STOP, node='door' )
        self.dZone.pNode.setAnimationSpeed( 2,        node='door' )
        self.dZone.pNode.setAnimationState( viz.PLAY, node='door' )
        
        # place avatar behind door
        avPos = self.dZone.getDoorXYZ(viz.ABS_LOCAL)
        self.setPosition(avPos, mode=viz.ABS_PARENT)
        
        # two contexts
        if not oneCtx:
            # chose only animations within this context
            do   = vizact.animation( random.randint(6,10) )
            
        # one context
        else:
            # select animation based on av's mood
            if cTrial.getCtx("drop") == 1:
                if cTrial.getMood("drop") == "nice":
                    do = vizact.animation( random.randint(6,10) )
                else:
                    do = vizact.animation( random.randint(14,18) )
            elif cTrial.getCtx("drop") == 2:
                if cTrial.getMood("drop") == "angry":
                    do = vizact.animation( random.randint(6,10) )
                else:
                    do = vizact.animation( random.randint(14,18) )            
            
        x, _, z = self.dZone.avLoc # get parent pos of vertex = building
        walk = vizact.walkTo([x, 0, z])
        
        # walk to parcel
        yield viztask.addAction(self, walk)
        
        # do receive action
        t0 = viz.tick()
        playAnimation = 1
        while playAnimation:
            yield viztask.addAction(self, do)
            if viz.tick() >= t0 + ct.MIN_ANIMATION_DUR:
                playAnimation = 0
                                                    
        # walk back to house
        walk = vizact.walkTo(avPos, turnInPlace = False)
        yield viztask.addAction(self, walk)
        
        # close door
        #dZone.pNode.setAnimationSpeed( -2,       node='door' )
        #dZone.pNode.setAnimationState( viz.PLAY, node='door' )
        self.dZone.pNode.setAnimationState( viz.STOP, node='door' )
        
        yield viztask.addAction( self, vizact.fadeTo(0,time=4), 1 ) # fade out                            
        self.remove() # remove resident

"""Tracks task performance across trials within round"""
class TaskPerformance():
    def __init__(self, taskType):
        self.taskType   = taskType
        self.trialPerfs = np.array([])
        
    def addTrial(self, cPerf):
        self.trialPerfs = np.append(self.trialPerfs, cPerf)
        
    def getMeanPerf(self):
        if self.trialPerfs.size > 0:
            return np.mean(self.trialPerfs)
        else:
            return -1
        
    def getLastPerf(self):
        # get last trial's performance
        return self.trialPerfs[-1]
    
"""Container for pickup and drop details of a trial"""
class ParcelTrial():
    def __init__(self, pZone, dZone, pCtx=None, dCtx=None, randMoods=0):
        self.pZone = pZone
        
        if pCtx:
            # specify custom context (ctrl cond)
            self.pCtx  = pCtx            
        else:            
            self.pCtx = pZone.getCtx()
        
        self.dZone = dZone
        if dCtx:
            # specify custom context (ctrl cond)
            self.dCtx = dCtx
        else:
            self.dCtx = dZone.getCtx()
        
        moods = ["nice", "angry"]
        if not randMoods:
            self.pMood = moods[self.pCtx-1]
            self.dMood = moods[self.dCtx-1]
        else:
            self.pMood = random.choice(moods)
            self.dMood = random.choice(moods)
                
        
    def getMood(self, zoneStr):    
        if zoneStr == "pickup":
            return self.pMood        
        elif zoneStr == "drop":
            return self.dMood
        else:
            warnings.warn("zone string must be either \'pickup\' or \'drop\'")
            return -1

    def getHouseName(self, zoneStr):
        if zoneStr == "pickup":
            return self.pZone.getHouseName()        
        elif zoneStr == "drop":
            return self.dZone.getHouseName()
        else:
            warnings.warn("zone string must be either \'pickup\' or \'drop\'")
            return -1
    
    def getCtx(self, zoneStr):
        if zoneStr == "pickup":
            return self.pCtx        
        elif zoneStr == "drop":
            return self.dCtx
        else:
            warnings.warn("zone string must be either \'pickup\' or \'drop\'")
            return -1

    def getXYZ(self, zoneStr):
        if zoneStr == "pickup":
            return self.pZone.getZoneXYZ()        
        elif zoneStr == "drop":
            return self.dZone.getZoneXYZ()
        else:
            warnings.warn("zone string must be either \'pickup\' or \'drop\'")
            return -1
        
"""Controls parcel deliveries"""    
class ParcelDelivery(viz.EventClass):
    def __init__(self, wCrns, gStep, mvSpeed, oneCtx=0):
        
        # world corners
        self.wCrns   = wCrns
        self.mvSpeed = mvSpeed
        
        # one or two contexts?
        self.oneCtx  = oneCtx
        
        if self.oneCtx:
            self.condStr = "oneContext"
        else:
            self.condStr = "twoContexts"
        
        self.orderQueue = None
        self.pDistAstar = 0
        self.pXZaStar   = []
        
        # will store grid
        self.grid = TownGrid(wCrns[:,0].min(), wCrns[:,0].max(), wCrns[:,1].min(), wCrns[:,1].max(), gStep)
                
        # add parcel node
        self.fadingPrclHdl = None # handle to parcel's action
        self.parcel = viz.add(os.path.join(ct.PATH_TO_OSGB, 'parcel.osgb'))
        self.parcel.visible(viz.OFF)
        parcelSpin = vizact.spin(0,1,0,120)
        self.parcel.addAction(parcelSpin)

        # stores handle to order task
        self.prepOrderTask = None
        
        # add & hide arrow node
        self.arrow = viz.add(os.path.join(ct.PATH_TO_OSGB, 'arrow.osgb'))
        self.arrow.visible(viz.OFF)
        arrowSpin = vizact.spin(0,1,0,90)
        self.arrow.addAction(arrowSpin)
        
        # node vars for pickup and drop avatars
        self.pAv = None
        self.dAv = None
                        
        #Create proximity manager
        self.manager = vizproximity.Manager()
            
        self.pZones = [] # list of pickup zones
        self.dZones = [] # list of drop zones
             
        # register info panel for messages
        self.info = ParcelMsg()
        
        # add main viewpoint as proximity target
        vPtarget = vizproximity.Target(viz.MainView)
        self.manager.addTarget(vPtarget)

        # toggle debug shapes with keypress
        vizact.onkeydown('f', self.manager.setDebug, viz.TOGGLE)
    
        # register event timer to track subject
        self.trackingHdl = vizact.onupdate(0, self.trackSubj)
        self.trackingHdl.setEnabled(False)
        self.trackIntvls = (0.01, 0.1) # get distance / get xz pos
        self.lastPosPoll = [] # corresponding time stamps
        self.lastSubjPos = viz.Vector() # will be set to (0,0,0)        
        self.pDistSubj   =  0
        self.pXZsubj     = []
        
        # Register callback for p/d zone entering
        self.manager.onEnter(None, self.onZoneEnter)
            
        # tracks number of trials
        self.cRound   = 0 # counter
        self.trialCtr = None
        self.cTrial   = None # will store handle to current trial object
        self.trials   = []
        
        # contains data of active trial
        # cleared after every trial!
        self.trialData = {}
        
        # init new task perf instance
        self.taskPerf = TaskPerformance(ct.TASK_TYPE)
        
        # set variable for event logger
        self.fields2log = {'trialNr' : 'i8', 'trialType' : 'S20', 'trialPerf' : 'f4', 'trialOnset' : 'f8', 'pickupXZ' : [('x', 'f4'), ('z', 'f4')], 'dropXZ' : [('x', 'f4'), ('z', 'f4')], 'pCtxt' : 'S1', 'dCtxt' :'S1', 'pMood' : 'S10', 'dMood' : 'S10', 'pickupHouse' : 'S20', 'dropHouse' : 'S20', 'tPickup' : 'f8', 'tDrop' : 'f8', 'pDistAstar' : 'f4', 'pDistSubj' : 'f4', 'pXZsubj' : 'list', 'pXZaStar' : 'list'}
        self.logHdl = log.LogData(self.fields2log)
        
        # init webserver to enable online control
        # of subject's performance
        self.webHdl = log.WebServer({'set_startStr' : None, 'set_trialCtr' : None, 'set_trialPerf' : None, 'set_meanPerf' : None})

        
        # save log file on exit
        vizact.onexit( self.saveOnExit )
        
        # close parallel computing pool
        vizact.onexit( vizmultiprocess.closePools )
    
    """Called on exit"""
    def saveOnExit(self):
        self.logHdl.saveLogs( ("%d_%s_%s_saveOnExit")%(self.cRound, ct.SUBJECT_NAME, self.condStr) )
    
    """Adds parcel pickup and drop zones"""
    def addBuilding(self, building, name, zType, ctx):
        entr = building.getChild('entrance')
        
        # does this building have an entrance child?
        if entr == viz.VizChild(-1):
            print 'Building does not have an entrance!'
            return
        
        # create new sensor
        cZone = ParcelZone(name, building, ctx)
                
        # drop zone or pickup zone?
        if zType == 'pickup':
            self.pZones.append(cZone)
            
        elif zType == 'drop':
            self.dZones.append(cZone)
                        
        else:   
            print 'Zone type must be either \"pickup\" or \"drop\"'
            return
        
        # add sensor    
        self.manager.addSensor(cZone)
    
        # add zone's parent node as an obstacle to grid
        self.grid.addObstacle(cZone.shPoly)            
    
    """Starts background process to precompute routes between pickup and drop zones"""
    def startOrderQueue(self):
        
        pXYs = map(lambda cTr: cTr.getXYZ("pickup"), self.trials)
        dXYs = map(lambda cTr: cTr.getXYZ("drop"),   self.trials)
        
        if not self.orderQueue:
            print "Starting order queue ..."
            self.orderQueue = OrderQueue(pXYs, dXYs, self.grid)
            viztask.schedule( self.orderQueue.checkQueue() )    
        else:
            print "Refreshing order queue ..."
            self.orderQueue.refreshQeue(pXYs, dXYs)

        return


    """Starts new round involving n trials"""
    def startNewRound(self):
                
        self.cRound   = self.cRound+1
        self.trials   = []
        self.trialCtr = 0
                
        # init new task perf instance
        self.taskPerf = TaskPerformance(ct.TASK_TYPE)
        
        # reset event logger
        self.logHdl.initData(self.fields2log)
                
        # get random permutation of all 20 pZones
        allPzones = random.sample(self.pZones, len(self.pZones))
        
        # two context paradigm:
        #
        # define all pickup / drop combinations here
        # make sure the following criteria are met:
        #
        # One round contains 20 trials: 
        #            
        # -> Each building of interest is visited twice.
        #    Once from a same once from an different context pickup zone
        # -> Each filler house (i.e. pickup zone) is visited once within a round
        #    (= 20 houses for both contexts)
        if not self.oneCtx:
                            
            # cycle twice through all 10 drop zones
            for i in range(2):
                
                # get a pickup zone for every drop zone            
                for cDrop in self.dZones:
                    for pInd, _ in enumerate(allPzones):
                        # get pZone of same context as dZone
                        if i == 0:
                            if allPzones[pInd].getCtx() == cDrop.getCtx():
                                cPickup = allPzones.pop(pInd) # pick pZone and delete from list
                                break
                        # get pZone of different context as dZone                            
                        elif i == 1:
                            if not allPzones[pInd].getCtx() == cDrop.getCtx():
                                cPickup = allPzones.pop(pInd) # pick pZone and delete from list
                                break
                    
                    # append this trial
                    self.trials.append( ParcelTrial(cPickup, cDrop) )
        
        # one context control condition
        #
        # define all pickup / drop combinations here
        # make sure the following criteria are met:
        #
        # One round contains 20 trials: 
        #
        # -> As above: Each building of interest is visited twice.
        #    Once from same once from different context pickup zone            
        # -> However: The context of each building changes on every visit
        # -> Each filler house (i.e. pickup zone) is visited once within a round
        #    (= 20 houses for both contexts)
        # -> Context of filler houses is random and changes every round
        #    Amount of houses run by red / blue people is constant (10 blue / 10 red)  
        else:

            # cycle twice through all 10 drop zones
            for i in range(2):
                
                # get a pickup zone for every drop zone                
                for dCtr, cDrop in enumerate(self.dZones, start=i+1):
                    dCtx=i+1
                    
                    # assign same context
                    if dCtr % 2 == 0:
                        pCtx=dCtx
                        
                    # assign different ctx
                    else:
                        if dCtx == 1:
                            pCtx=2
                        else:
                            pCtx=1
                    
                    #DEBUGGING
                    #print "dCtx %d, pCtx %d"%(dCtx, pCtx)
                                                                                                        
                    cPickup = allPzones.pop(0) # pick pZone and delete from list
                    
                    # append this trial and assign custom contexts
                    # to pickup and drop zones                    
                    self.trials.append( ParcelTrial(cPickup, cDrop, pCtx, dCtx, randMoods=1) )
        
        # shuffle trials and save
        # remember shuffle works "in place" and returns None
        random.shuffle(self.trials)
        
        # DEBUGGING: take subset of samples
        #self.trials = self.trials[0:4]
        
        # start order queue
        self.startOrderQueue()
        
        # start first order
        self.prepOrderTask = viztask.schedule( self.wait4nextOrder() )
        
        # send message to user
        if self.cRound > 1:
            viz.message('Round %d'%(self.cRound))


    """called on update: starts new order as soon as it is available"""
    def wait4nextOrder(self):
        while 1:
            # wait ct.T_TO_NEXT_ORDER in seconds
            yield viztask.waitTime(ct.T_TO_NEXT_ORDER)
            
            # try to start new order
            if self.placeOrder():
                # if successfully started -> exit loop
                break
    
    """Starts new order"""
    def placeOrder(self):
        
        # did we start a new round?
        if not self.cRound:
            print "Please start new round!"
            return 0
        
        # did we reach last trial of this round?
        if self.trialCtr == len(self.trials):
            
            # save log file of last round
            savePrefix = ("%d_%s_%s")%(self.cRound, ct.SUBJECT_NAME, self.condStr)
            self.logHdl.saveLogs(savePrefix)
            
            # start new round
            self.startNewRound()
            
            # leave active wait for new order task
            return 1
                                                        
        # already any order in queue?
        cOrder = self.orderQueue.getOrder()
        #print cOrder
        if not cOrder:
            print "Order queue is empty -> filling ..."
            return 0
        
        
        # send info to webserver
        if not self.oneCtx:
            evtData = viz.Data( startStr = "Two-Context Condition -> %s-task (round %d)"%(ct.TASK_TYPE, self.cRound) ) 
        else:
            evtData = viz.Data( startStr = "One-Context Control Condition -> %s-task (round %d)"%(ct.TASK_TYPE, self.cRound) )            
        self.webHdl.updateServer('set_startStr', evtData)
        
        self.pDistAstar = 0
        
        # get current trial
        self.cTrial   = self.trials[cOrder["trialNr"]]
        self.trialCtr = self.trialCtr+1
        
        # update webserver
        evtData = viz.Data( trialCtr = "Trial %d of %d"%(self.trialCtr, len(self.trials)) )
        self.webHdl.updateServer("set_trialCtr", evtData)
                     
        # reset zones
        self.resetZones()
            
        # draw path & get path distance from A* algorithm
        self.pDistAstar, self.pXZaStar = self.grid.getPathDist(cOrder["path"], drawPath=0)
        
        # remove previous avatar if still exists
        if hasattr(self.pAv, 'id') and self.pAv.id > -1:
            self.pAv.killTasks()
            self.pAv.remove()
            
        # add pickup avatar            
        self.pAv = addHouseResident(self.cTrial.getCtx("pickup"), parent=self.cTrial.pZone.pNode)        
        self.pAv.setPosition(self.cTrial.pZone.avLoc, mode=viz.ABS_LOCAL)
        
        # two contexts
        if not self.oneCtx:
            self.pAv.state( random.randint(3,4) )
            
        # one context
        else:
            # select animation based on av's mood
            if self.cTrial.getCtx("pickup") == 1:
                if self.cTrial.getMood("pickup") == "nice":
                    anInds = [3, 4]
                else:
                    anInds = [11, 12]
            else:
                if self.cTrial.getMood("pickup") == "angry":
                    anInds = [3, 4]
                else:
                    anInds = [11, 12]
            
            random.shuffle(anInds)
            self.pAv.state( anInds[0] )
                     
        # kill parcel's fading task/action if still alive from last order
        if self.fadingPrclHdl:
            if self.fadingPrclHdl.alive():                
                self.fadingPrclHdl.kill()
                self.parcel.clearActions(1)
        
        # place parcel in pickup zone
        self.parcel.setParent(self.cTrial.pZone.pNode)
        self.parcel.setPosition(self.cTrial.pZone.paLoc, mode=viz.ABS_LOCAL)
        self.parcel.alpha(1) # set to opaque
        self.parcel.visible(viz.ON)
         
        # place green arrow on top of house to mark new order
        self.arrow.setParent(self.cTrial.pZone.pNode)
        self.arrow.setPosition(self.cTrial.pZone.arLoc, mode=viz.ABS_PARENT)
        self.arrow.visible(viz.ON)
         
        # set zone status to pickup (1 -> pickup / 2 -> drop)
        self.cTrial.pZone.status = 1
         
        # show pickup notice, submit estimated path distance
        self.info.setEstT( self.pDistAstar/(ct.MOVE_SPEED_CONST*self.mvSpeed) ) # set estimated duration to arrive at target
        self.info.showPickupInfo(self.cTrial, self.trialCtr, len(self.trials))
    
        
        # ----- log trial data -----
        
        # reset log dict
        self.trialData.clear()
        
        self.trialData['trialNr']    = self.trialCtr
        self.trialData['trialType']  = ct.TASK_TYPE        
        self.trialData['trialOnset'] = viz.tick()
        
        pX, _, pZ = self.cTrial.getXYZ("pickup")
        self.trialData['pickupXZ']    = (pX, pZ)
        self.trialData['pickupHouse'] = self.cTrial.getHouseName("pickup")                        
        
        dX, _, dZ = self.cTrial.getXYZ("drop") 
        self.trialData['dropXZ']     = (dX, dZ)
        self.trialData['dropHouse']  = self.cTrial.getHouseName("drop")
        
        self.trialData['pCtxt']      = self.cTrial.getCtx("pickup")
        self.trialData['dCtxt']      = self.cTrial.getCtx("drop")
        
        self.trialData['pMood']      = self.cTrial.getMood("pickup")
        self.trialData['dMood']      = self.cTrial.getMood("drop")
        
        return 1
            
    """Track subject to get travelled distance"""
    def trackSubj(self):
        
        # get current time stamp
        cTstamp = viz.tick()
        
        # get current pos
        cSubjPos = viz.Vector(viz.MainView.getPosition())
        
        # skip for 1st poll -> do this for 2nd to last poll
        if self.lastPosPoll:
                               
            # get dist
            if cTstamp - self.lastPosPoll[0] > self.trackIntvls[0]:
                # get distance between this and last pos                
                self.pDistSubj      = self.pDistSubj + (self.lastSubjPos - cSubjPos).length()
                self.lastPosPoll[0] = cTstamp
            
            # save path
            if cTstamp - self.lastPosPoll[1] > self.trackIntvls[1]:
                self.pXZsubj.append( ( int(round(cSubjPos.x)), int(round(cSubjPos.z))) )
                self.lastPosPoll[1] = cTstamp
        
        # first poll -> only assign time stamps
        else:            
            # get current time stamp for both intervals            
            self.lastPosPoll[0:1] = [viz.tick()]*2
    
        # save last subj pos 
        self.lastSubjPos      = cSubjPos
    
    
    """Reset tracking vars for next trial"""
    def resetSubjTracking(self):
        self.trackingHdl.setEnabled(False)
        self.lastSubjPos    = viz.Vector() # will be set to (0,0,0)
        self.lastPosPoll[:] = []        
        self.pXZsubj        = []
        self.pDistSubj      = 0
    
    
    """Sets status of all zones to 0"""
    def resetZones(self):
        for cZ in self.dZones:
            cZ.status = 0
        for cZ in self.pZones:
            cZ.status = 0
            
    
    """Called when parcel has been delivered"""
    def fadeOutParcel(self):        
        yield viztask.addAction( self.parcel, vizact.fadeTo(0,time=5), 1 ) # fade out rotating parcel                    
        self.parcel.visible(viz.OFF)
    
    """Callback function, triggered when zones are entered"""
    def onZoneEnter(self, evObj):        
        
        # is this an active pickup zone?
        if evObj.sensor.status == 1:
                        
            # two contexts
            if not self.oneCtx:
                self.pAv.state(5)
            
            # one context
            else:
                # select animation based on av's mood
                if self.cTrial.getCtx("pickup") == 1:
                    if self.cTrial.getMood("pickup") == "nice":
                        anInd = 5
                    else:
                        anInd = 13
                else:
                    if self.cTrial.getMood("pickup") == "angry":
                        anInd = 5
                    else:
                        anInd = 13
            
                self.pAv.state(anInd)
                            
                                        
            # show target info
            self.info.resetMsg()
            #self.info.showTargetInfo('timeTask', self.dZones[self.cDind])
            self.info.showTargetInfo('distTask', self.cTrial)
            
            # hide arrow
            self.arrow.visible(viz.OFF)
            
            # reset pickup zone's status
            evObj.sensor.status = 0
            self.parcel.visible(viz.OFF)
            
            # enable drop zone
            self.cTrial.dZone.status = 2

            # get pickup time stamp
            self.trialData['tPickup'] = viz.tick()

            # enable subject position tracking
            self.resetSubjTracking()
            self.trackingHdl.setEnabled(True)
        
        # is this an active drop zone?
        elif evObj.sensor.status == 2:
            self.info.resetMsg()
            self.info.resetIcon()                        
            
            # show dropped parcel in drop zone
            self.parcel.setParent(evObj.sensor.pNode)
            self.parcel.setPosition(evObj.sensor.paLoc, mode=viz.ABS_LOCAL)
            self.parcel.visible(viz.ON)
            self.fadingPrclHdl = viztask.schedule(self.fadeOutParcel())
            
            # remove previous avatar if still exists
            if hasattr(self.dAv, 'id') and self.dAv.id > -1:
                self.dAv.killTasks()
                self.dAv.remove()
            
            # place avatar in door close to drop zone
            self.dAv = addHouseResident(self.cTrial.getCtx("drop"), parent=self.cTrial.dZone.pNode)
            
            # schedule avatar task
            if not self.oneCtx:
                # only play within context animations
                self.dAv.addTask( viztask.schedule(self.dAv.receiveParcel(self.cTrial)) )
            else:
                # chose from all animations
                self.dAv.addTask( viztask.schedule(self.dAv.receiveParcel(self.cTrial, oneCtx=1)) )
                                                                 
            # show drop message, return performance measure: i.e. rel time / distance needed to reach goal
            self.info.showSuccess(self.cTrial, self.pDistAstar, self.taskPerf)            
            evObj.sensor.status = 0
                                    
            # get drop time stamp
            self.trialData['tDrop'] = viz.tick()
            
            # stop subject tracking
            self.trackingHdl.setEnabled(False)
            
            # --- log path length and coords ---
            self.trialData['pDistAstar'] = self.pDistAstar
            self.trialData['pDistSubj']  = self.pDistSubj
            self.trialData['pXZaStar']   = self.pXZaStar
            self.trialData['pXZsubj']    = self.pXZsubj
            
            self.trialData['trialPerf']  = self.taskPerf.getLastPerf()
            
            # update webserver
            evtData = viz.Data( trialPerf = round(self.taskPerf.getLastPerf(),2) )
            self.webHdl.updateServer("set_trialPerf", evtData)
            
            evtData = viz.Data( meanPerf = round(self.taskPerf.getMeanPerf(),2) )
            self.webHdl.updateServer("set_meanPerf", evtData)
            
            
            # log this trial
            self.logHdl.logDictData(self.trialData)
            
            # reset subject tracking
            self.resetSubjTracking()
            
            # reset zones
            self.resetZones()
            
            # reset subject tracking
            self.resetSubjTracking()
            
            # start next order
            self.prepOrderTask = viztask.schedule( self.wait4nextOrder() )
            