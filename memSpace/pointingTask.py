import viz
import viztask
import vizact
import vizinfo
import vizcam
import vizshape

import random
import re
import os
import glob

import numpy as np

import constants as ct

import logger as lg


"""Overrides internal WalkNavigate classs"""
class WalkNavigate( vizcam.WalkNavigate ):
    def __init__(self, **kw):
        vizcam.WalkNavigate.__init__(self, **kw)
    
    # override parent's method too limit mouse update to yaw
    def _camMouseMove(self,e):
        yaw, pitch, _ = e.view.getEuler()
        yaw += e.dx * self.__turnScale
        pitch_increment = -e.dy * self.__turnScale
        if abs(pitch + pitch_increment) > 89.0:
            pitch = viz.sign(pitch) * 89.0
        else:
            pitch += pitch_increment
        #e.view.setEuler(yaw,pitch,0.0)
        e.view.setEuler(yaw,0.0,0.0)


"""Handles HUD"""
class PointInfo:
    def __init__(self, mTitle = ''):
                
        # add info panel
        self.panel = vizinfo.InfoPanel('')
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
        
        self.line3 = self.panel.addItem(viz.addText(' '))
        self.line3.setEncoding(viz.ENCODING_UTF8)
                
        # get icon images
        self.iconTxs = {}
        iconFiles    = glob.glob( os.path.join(ct.PATH_TO_ICONS, '*.jpg') ) # each folder corresponds to one character
        p = re.compile(r"_[a-z]*\d_") # e.g. look for .*_bakery1_.*
        for cTex in iconFiles:
            m    = p.search(cTex)
            iKey = cTex[m.span(0)[0]+1 : m.span(0)[1]-1] # take only bakery1 as key
            self.iconTxs[iKey] = viz.addTexture(cTex)
    
        # add quad
        self.texQuad = viz.addTexQuad(size=0)
        self.qNode   = self.panel.addItem(self.texQuad) # add quad to panel
        #self.qNode   = self.panel.addItem('Delivery Target', self.texQuad) # add quad to panel        
         
                
        # add right panel
        self.panel2 = vizinfo.InfoPanel('', align=viz.ALIGN_RIGHT_TOP)
        self.panel2.visible(viz.OFF)

        # start with green theme
        self.panel2.getPanel().setTheme(self.themes["standard"])

        # add text to right panel
        self.line1r   = self.panel2.addItem(viz.addText(' '))
        self.line1r.setEncoding(viz.ENCODING_UTF8)
        self.texQuadR = viz.addTexQuad(size=0)
        self.qNodeR   = self.panel2.addItem(self.texQuadR) # add quad to panel
                

    """Reset panel"""
    def resetMsg(self):
        # delete text
        self.panel.setText('')
        self.line1.message('')
        self.line2.message('')
        self.line3.message('')
        
        self.panel2.setText('')
        self.line1r.message('')
        
        # reset text color to black
        self.line1.color(viz.BLACK)
        self.line2.color(viz.BLACK)
        self.line3.color(viz.BLACK)
        
        self.line1r.color(viz.BLACK)
        
        # hide panel
        self.panel.visible(viz.OFF)
        self.panel2.visible(viz.OFF)
        
    """Reset icon"""
    def resetIcon(self):
        # left panel
        self.qNode.setSize(0)
        self.qNode.visible(viz.OFF)
        
        # right panel
        self.qNodeR.setSize(0)
        self.qNodeR.visible(viz.OFF)
        
        
    def showTargetInfo(self, cTrial, nthTrial, nTrials):
                        
        # start from clear panel
        self.resetMsg()
        
        # left panel
        self.panel.getPanel().setTheme(self.themes["standard"])
        
        # get trial message        
        self.line1.message('Trial %d of %d'%(nthTrial, nTrials) )
        self.line1.fontSize(20)                                                
        self.line3.message('Please point to target:')                                          
        self.line3.fontSize(20)        
                                                                                        
        # show target icon
        self.texQuad.texture(self.iconTxs[cTrial.getName('trg')])
        self.qNode.setSize(100)
        self.qNode.visible(viz.ON)
                        
        # show panel
        self.panel.visible(viz.ON)

        # show info about source building
        self.panel2.getPanel().setTheme(self.themes["standard"])
        
        self.line1r.message('You are at:')                                          
        self.line1r.fontSize(20)        

        # show source icon
        self.texQuadR.texture(self.iconTxs[cTrial.getName('src')])
        self.qNodeR.setSize(100)
        self.qNodeR.visible(viz.ON)

        # show panel
        self.panel2.visible(viz.ON)
        

"""Defines building"""
class building():
    def __init__(self, bName, ctx, bNode):
        self.bName   = bName
        self.ctx     = ctx
        self.bNodeOp = bNode
        self.bNodeTr = bNode.copy()        
        self.bNodeTr.setMatrix( self.bNodeOp.getMatrix() ) # copy position and orientation
        self.bNodeTr.alpha(0.2, '', viz.OP_OVERRIDE)

        self.visNode = None 

        # get entrance                                
        sCtr = np.array(bNode.getMatrix(viz.ABS_LOCAL, node='entrance').getPosition())
                                        
        self.viewLocFar  = [ sCtr[0], .5, sCtr[2]-15  ] # ABS_LOCAL
        #self.viewLocFar  = [ sCtr[0], .5, sCtr[2]-1  ] # ABS_LOCAL
        self.viewLocNear = [ sCtr[0], .5, sCtr[2]- 0.5 ] # ABS_LOCAL            
        
    """gets global xy coords of viewing positions"""
    def getViewXYZ(self, dist="far", reFrame=viz.ABS_GLOBAL):
        
        # temporarily add vertex to track parcel pos in abs coords
        viz.startLayer(viz.POINTS)
        viz.vertexColor(1,0,0)
        viz.pointSize(30)
        viz.vertex(0,0,0)
        cV = viz.endLayer()
        cV.setParent(self.bNodeOp)
                
        if dist == "far":
            cV.setPosition(self.viewLocFar, mode=viz.ABS_LOCAL)
            zoneXYZ = cV.getPosition(mode=reFrame)
        elif dist == "near":
            cV.setPosition(self.viewLocNear, mode=viz.ABS_LOCAL)
            zoneXYZ = cV.getPosition(mode=reFrame)
        elif dist == 'center':
            zoneXYZ = self.bNodeOp.getPosition(mode=reFrame)
            
        cV.visible(viz.OFF)        
        cV.remove()
        
        # set y to eye height
        zoneXYZ[1] = ct.EYE_HEIGHT
        
        return zoneXYZ
    
    def getCtx(self):
        return self.ctx
        
    # prevent building from rendering
    def hide(self):
        self.bNodeOp.disable(viz.RENDERING)
        self.bNodeTr.disable(viz.RENDERING)
        self.visNode = None
    
    # enable rendering of building
    def show(self, which):                        
        if which == 'opaque':
            self.bNodeOp.enable(viz.RENDERING)
            self.visNode = self.bNodeOp
            
        elif which == 'transparent':            
            self.bNodeTr.enable(viz.RENDERING)
            self.visNode = self.bNodeTr
    
    def toggleTransp(self):
        if self.visNode:
            if self.visNode == self.bNodeOp:
                self.hide()
                self.show('transparent')
            else:
                self.hide()
                self.show('opaque')                
    
    def getName(self):
        return self.bName


"""Defines pointing trial"""
class Ptrial():
    def __init__(self, bSrc, bTrg):         
        self.src = bSrc                        
        self.trg = bTrg
        
    def getPos(self, cBld, cDist):
        if cBld == 'src':
            return self.src.getViewXYZ(cDist)            
        elif cBld == 'trg':
            return self.trg.getViewXYZ(cDist)
        
    def getAngle(self, cBld, cDist):
        if cBld == 'src':
            return self.src.bNodeOp.getAxisAngle()
        elif cBld == 'trg':
            return self.trg.bNodeOp.getAxisAngle()
    
    def getName(self, cBld):
        if cBld == 'src':
            return self.src.getName()            
        elif cBld == 'trg':
            return self.trg.getName()
    
    def getContext(self, cBld):
        if cBld == 'src':
            return self.src.getCtx()            
        elif cBld == 'trg':
            return self.trg.getCtx()
    
    def hideBuildings(self):        
        self.src.hide()
        self.trg.hide()
    
    def showBuilding(self, cBld, cType):
        if cType == 'transparent':
            if cBld == 'src':
                self.src.hide()
                self.src.show('transparent')
            elif cBld == 'trg':
                self.trg.hide()
                self.trg.show('transparent')
                
        elif cType == 'opaque':
            if cBld == 'src':
                self.src.hide()
                self.src.show('opaque')                
            elif cBld == 'trg':                
                self.trg.hide()
                self.trg.show('opaque')


"""Defines Pointing Task"""
class PointingTask():
    def __init__(self, bldList):
        
        self.info       = PointInfo()
        self.buildings  = bldList
        self.trials     = []        
        self.cTrial     = None
        self.trialCtr   = -1         
        self.trgAngle   = None
        self.hideBuildings()
        self.trialData  = {}

        # add vertex to measure true target angel
        viz.startLayer(viz.POINTS)
        viz.vertexColor(1,0,0)
        viz.pointSize(30)
        viz.vertex(0,0,0)
        self.refVert = viz.endLayer()
        self.refVert.disable(viz.RENDERING)


        # add grid to orient subject during
        # pointing
        viz.startLayer(viz.LINES)
        viz.lineWidth(6)
        viz.vertexColor(0,0.6,0)
        viz.vertex(-100, 0.01,  0)
        viz.vertex( 100, 0.01,  0)
        viz.vertex(  0, 0.01,-100)
        viz.vertex(  0, 0.01, 100)
        self.cross90 = viz.endLayer()         
        self.cross90.visible(viz.OFF)        

        self.grid = vizshape.addGrid(size=[200,200], step=10.0, boldStep=None)
        self.grid.color([0,.6,0])
        self.grid.visible(viz.OFF)

        # add logger
        self.fields2log = {'trialNr' : 'i8', 'srcBuilding' : 'S10', 'trgBuilding' : 'S10', 'refAngle' : 'f4', 'measAngle' : 'f4', 'trueAngle' : 'f4', 'trialOnset' : 'f8', 'tChoiceMade' : 'f8', 'srcXZ' : [('x', 'f4'), ('z', 'f4')], 'trgXZ' : [('x', 'f4'), ('z', 'f4')], 'srcCtxt' : 'S1', 'trgCtxt' :'S1'}
        self.logHdl     = lg.LogData(self.fields2log)

        # handle exit
        vizact.onexit( self.saveOnExit )
    
    
    """Called on exit"""
    def saveOnExit(self):
        self.logHdl.saveLogs('saveOnExit_pointingTask')
    
    """Prevent buildings from being rendered"""
    def hideBuildings(self):
        # hide all buildings
        for cB in self.buildings:
            cB.hide()
    
    """Start new round"""
    def startNewRound(self):
        self.cTrial   =  None
        self.trialCtr = -1
        
        # prepare trials
        for cS in self.buildings:
            for cT in self.buildings:
                if not cS == cT:
                    #Debugging: print src and trg
                    #print "src: %s; trg: %s"%(cS.bName, cT.bName)
                    self.trials.append( Ptrial(cS, cT) )
        
        random.shuffle(self.trials)
        
        viztask.schedule( self.startNewTrial() )
        
    
    """Start new trial"""
    def startNewTrial(self):

        # first trial: wait for space to start task
        if self.trialCtr < 0:
            text2D = viz.addText('Please press s to start', viz.SCREEN)
            text2D.setPosition(0.5,0.5,0.5)
            text2D.setScale([0.5, 0.5, 0.5])
            text2D.alignment(viz.ALIGN_CENTER_CENTER)
            WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=0, turnScale=0)
            yield viztask.waitKeyDown('s')
            text2D.remove()
                
        # increment trial counter
        self.trialCtr = self.trialCtr+1
        
        # did we reach end of round?
        if self.trialCtr <= len(self.trials)-1:                 
            self.cTrial = self.trials[self.trialCtr]
        else:
            self.logHdl.saveLogs('pointingTask')
            viz.quit()
        
        # reset log dict
        self.trialData.clear()
        
        # log trial data
        self.trialData['trialNr']     = self.trialCtr        
        
        self.trialData['srcBuilding'] = self.cTrial.getName('src')
        self.trialData['srcCtxt']     = self.cTrial.getContext('src')
        x,_,z = self.cTrial.getPos('src', 'near')
        self.trialData['srcXZ']       = (x,z) 
        
        self.trialData['trgBuilding'] = self.cTrial.getName('trg')
        self.trialData['trgCtxt']     = self.cTrial.getContext('trg')
        x,_,z = self.cTrial.getPos('trg', 'center')
        self.trialData['trgXZ']       = (x,z)
        
        # hide all buildings
        self.hideBuildings()
        
        # hide grid
        self.cross90.visible(viz.OFF)
        self.grid.visible(viz.OFF)
        
        # block user navigation
        WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=0, turnScale=0)
                    
        # show source building
        self.cTrial.showBuilding('src', 'opaque')
        
        # move & refVert view to far pos
        x,_,z = self.cTrial.getPos('src', 'far')
        viz.MainView.setPosition(x, 0, z)
        
        # align mainview to src building
        _,_,_,degs = self.cTrial.getAngle('src', 'far')
        viz.MainView.setAxisAngle(0, 1, 0, -degs)        
        viz.eyeheight(ct.EYE_HEIGHT)
                                    
        viztask.schedule( self.moveView() )
        
        # log reference angle
        self.trialData['refAngle'] = degs
        
        print "Please look at: %s"%self.cTrial.getName('trg')


    """Move view from far to near building position"""
    def moveView(self):
        # move view
        xT,_,zT  = self.cTrial.getPos('src', 'near')
        moveTo = vizact.moveTo([xT,ct.EYE_HEIGHT,zT], speed=5)
        viz.MainView.addAction(moveTo)
     
        yield viztask.waitActionEnd(viz.MainView, moveTo)
     
        # make source building semi transparent
        self.cTrial.showBuilding('src', 'transparent')
        
        # align reference vertex to mainview
        self.refVert.setMatrix( viz.MainView.getMatrix() )
                
        # enable user mouse look
        WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=0, turnScale=1.0)
        
        vx, _, vz = viz.MainView.getPosition()
        # draw grid            
        self.cross90.setPosition(vx, 0.01, vz)
        self.cross90.visible(viz.ON)
                
        self.grid.setPosition(vx, 0.1, vz)
        self.grid.visible(viz.ON)
        
        viztask.schedule( self.getTargetAngle() )
                
    """Get target angle from subject's response"""
    def getTargetAngle(self):
        gotAngle = 0
        
        # log trial onset
        self.trialData['trialOnset']  = viz.tick()
        
        # show pointing target
        self.info.showTargetInfo(self.cTrial, self.trialCtr+1, len(self.trials))
        
        while not gotAngle:
            keyObj = yield viztask.waitKeyDown(keys=None)
            
            if keyObj.key == ' ':
                trgAngle = viz.MainView.getEuler(viz.ABS_GLOBAL)
                print trgAngle[0]
                gotAngle = 1
                
#            if keyObj.key == 't':
#                viz.MainView.lookAt( self.cTrial.getPos('trg', 'center') )
#                self.cTrial.showBuilding('trg', 'opaque')
#                trueAngle = viz.MainView.getEuler(viz.ABS_GLOBAL)
#                print trueAngle[0]                
            
            if keyObj.key == 'q':
                self.cTrial.src.toggleTransp()
                        
        # hide buildings
        self.cTrial.hideBuildings()
        
        # hide pointing info
        self.info.resetMsg()
        
        # log trial end
        self.trialData['tChoiceMade'] = viz.tick()
        
        # log target angle
        self.trialData['measAngle'] = trgAngle[0] # measured
        
        self.refVert.lookAt( self.cTrial.getPos('trg', 'center') )
        trueAngle = self.refVert.getEuler(viz.ABS_GLOBAL)
        print "refVert: ", trueAngle[0]
        self.trialData['trueAngle'] = trueAngle[0] # ground truth
        
        # DEBUGGING
        # print self.trialData
        
        # log data
        self.logHdl.logDictData(self.trialData)
        
        # start new trial
        viztask.schedule( self.startNewTrial() )