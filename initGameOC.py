import viz
import vizfx
import vizcam
import vizact

import os
import time

import numpy as np

import memSpace.scene  as sc
import memSpace.agents as ag
import memSpace.delivery as dl

import memSpace.constants as ct

import oculus

if __name__ == '__main__':

    viz.setOption('viz.dwm_composition', '0')

    # get global coords of building corners
    # by locally adding helper vertices to corners 
    def getCornerCoords(cNode, quSpace):
    
        nBox = cNode.getBoundingBox(viz.ABS_LOCAL)
        
        cCrns      = [ (nBox.xmin, 0, nBox.zmin), (nBox.xmin, 0, nBox.zmax), (nBox.xmax, 0, nBox.zmax), (nBox.xmax, 0, nBox.zmin) ]
        globalCrns = []
        singleVertChildren = []
        for c in cNode.getChildren():
            if c.__class__ == viz.VizPrimitive:
                singleVertChildren.append( c )
        
        #print "nChildren: ", singleVertChildren
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
                cV.setParent(cNode)
                
                # move to parent's corner
                x,y,z = cC
                cV.setPosition(x, y, z, viz.ABS_PARENT)
                
            else:
                cV = singleVertChildren[i]
                                       
            # set obst as parent
            cV.setParent(cNode)
            
            # move to parent's corner
            x,y,z = cC
            cV.setPosition(x, y, z, viz.ABS_PARENT)
            
            # get global coords
            x,y,z = cV.getPosition(viz.ABS_GLOBAL)
            
            # flip z axis to get from world to pedSim space
            if quSpace == 'ped':
                z=-z
                
            globalCrns.append( (x,y,z) )
                            
            # remove this vertex
            #cV.remove()
            
            i = i+1
            
        return globalCrns

    # scale factor
    scFac = 60
    
    viz.setMultiSample(4)
    viz.go()
    
    viz.eyeheight(ct.EYE_HEIGHT)
    
    
    
    canvas = viz.addGUICanvas()
    canvas.setRenderWorldOverlay([1280,720],fov=40.0,distance=5.0)
    viz.MainWindow.setDefaultGUICanvas(canvas)
    
    # Key commands
    KEYS = { 'forward'	: viz.KEY_UP
            ,'back' 	: viz.KEY_DOWN
            ,'left' 	: viz.KEY_LEFT
            ,'right'	: viz.KEY_RIGHT
            ,'reset'	: 'r'
            ,'camera'	: 'c'
            ,'help'		: ' '
    }    
    
    
    # Setup Oculus Rift HMD
    hmd = oculus.Rift()
    if not hmd.getSensor():
        sys.exit('Oculus Rift not detected')

    # Setup heading reset key
    vizact.onkeydown(KEYS['reset'], hmd.getSensor().reset)

    # Check if HMD supports position tracking
    supportPositionTracking = hmd.getSensor().getSrcMask() & viz.LINK_POS
    if supportPositionTracking:

        # Add camera bounds model
        camera_bounds = hmd.addCameraBounds()
        camera_bounds.visible(False)

        # Change color of bounds to reflect whether position was tracked
        def CheckPositionTracked():
            if hmd.getSensor().getStatus() & oculus.STATUS_POSITION_TRACKED:
                camera_bounds.color(viz.GREEN)
            else:
                camera_bounds.color(viz.RED)
        vizact.onupdate(0, CheckPositionTracked)

    # Setup navigation node and link to main view
    navigationNode = viz.addGroup()
    viewLink = viz.link(navigationNode, viz.MainView)
    viewLink.preMultLinkable(hmd.getSensor())

    # Apply user profile eye height to view
    profile = hmd.getProfile()
    if profile:
        navigationNode.setPosition([0,profile.eyeHeight,0])
    else:
        navigationNode.setPosition([0,1.8,0])

    # Setup arrow key navigation    
    def UpdateView():
        yaw,pitch,roll = viewLink.getEuler()
        m = viz.Matrix.euler(yaw,0,0)
        dm = viz.getFrameElapsed() *2* ct.MOVE_SPEED
        if viz.key.isDown(KEYS['forward']):
            m.preTrans([0,0,dm])
        if viz.key.isDown(KEYS['back']):
            m.preTrans([0,0,-dm])
        if viz.key.isDown(KEYS['left']):
            m.preTrans([-dm,0,0])
        if viz.key.isDown(KEYS['right']):
            m.preTrans([dm,0,0])
        navigationNode.setPosition(m.getPosition(), viz.REL_PARENT)
    vizact.ontimer(0,UpdateView)

    
    
    
    
    # add code to navigate through scene via "wasd" control
    #vizcam.WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=ct.MOVE_SPEED, turnScale=1.0)    
    
    
    #Get a handle to the main headlight and disable it
    headLight = viz.MainView.getHeadLight()
    #headLight.disable()
    
    # add sky
    sky = viz.add('sky_day.osgb')
    
    # add grassy plane surrounded by mountains
    gScale = 1.1
    hills = vizfx.addChild(os.path.join(ct.PATH_TO_OSGB, 'hills.osgb'))
    hills.setScale(gScale, gScale, gScale)
    
    # add invisible cylinder to prevent subjects from leaving the arena
    invWall = vizfx.addChild(os.path.join(ct.PATH_TO_OSGB, 'cylinderWall.osgb'))
    invWall.setScale(gScale, gScale, gScale)
    invWall.disable(viz.RENDERING)
    #invWall.alpha(0)
    
    # add flags
    redBanner  = vizfx.addChild(os.path.join(ct.PATH_TO_OSGB, 'redFlag.osgb' ))
    redBanner.setScale(gScale, gScale, gScale)
    
    blueBanner = vizfx.addChild(os.path.join(ct.PATH_TO_OSGB, 'blueFlag.osgb'))
    blueBanner.setScale(gScale, gScale, gScale)
    
    # enable viewpoint collision handling
    viz.MainView.collision( viz.ON )
    
    bData  = []
    bNodes = []
    
    # create new scene definition object
    SceneDef = sc.SceneDefinition();
    
    # create new delivery obj, specify world boundaries and grid steps
    # these are hard coded so far -> a bit ugly
    wCrns = np.array([[ 65,  65], [ 65, -65], [-65, -65], [-65,  65], [ 65,  65]])
    myDl  = dl.ParcelDelivery(wCrns, 1, ct.MOVE_SPEED)
    
    # load building nodes and place according to external txt file
    cornerBalls = []
    with open('./coords.txt') as fp:
        for cB in fp:
            # store building information in list
            # one row corresponds to one building:
            # context name x y z rotation
            
            # split line
            bData.append(cB.split())
            
            # get context
            ctx = int(bData[-1][0][2])        
            
            # convert xyz and orientation angle to numbers
            bData[-1][2:6] = [float(i) for i in bData[-1][2:6]]
        
            # this building's orientation            
            theta = bData[-1][5]  
            
            # import model
            cNode = viz.add(os.path.join(ct.PATH_TO_OSGB, "%s%s"%(bData[-1][1], ".OSGB")))
            bNodes.append( cNode ) # add building
            cNode.setPosition(bData[-1][2]*scFac, bData[-1][3], bData[-1][4]*scFac)                   # set building's position
            cNode.setAxisAngle(0, 1, 0, theta, viz.ABS_LOCAL)                                         # rotate building in worldviz
            
            if 'house' in bData[-1][1]:
                # filler houses                
                myDl.addBuilding(cNode, bData[-1][1], 'pickup', ctx)                                  # add obstacle to A* grid (assumes to have helper vertices assigned to each corner)
            else:
                # crucial comparisons                
                myDl.addBuilding(cNode, bData[-1][1], 'drop', ctx)                                    # add obstacle to A* grid (assumes to have helper vertices assigned to each corner)
        
            # set building's animation params
            cNode.setAnimationLoopMode(viz.OFF, node='')
            cNode.setAnimationState(viz.STOP, node='')
        
            # add building as obstacle in PedSim space                                                        
            SceneDef.addObstacle(bData[-1][1], bData[-1][0], 'building', getCornerCoords(cNode, 'ped'), 'ped')
            
    # load bounding box coords
    # contains one line with xz coords
    bBoxPs   = []
    bBcoords = []
    with open('./bBox.txt') as fp:        
        bBoxcoords = fp.readline().split()
    
    # convert xz coords to scaled float (x,z) tuples
    bBoxcoords = [float(i)*scFac for i in bBoxcoords]
    bBoxPs     = [(bBoxcoords[i], bBoxcoords[i+1]) for i in range(0, len(bBoxcoords)-2, 2)]
            
    # add context bounding boxes    
    SceneDef.addBBs(bBoxPs, ct.CONTEXT_ANGLE)
     
    # start order queue to precompute order routes
    myDl.startOrderQueue()
            
    # safe xml tree to file
    print "Writing obstacles ..."
    SceneDef.writeXML('obstacle')
    print "Done!"
      
    # create and write waypoints using k nearest neighbor
    SceneDef.addWayPoints(9)
    SceneDef.writeXML('waypoint')
      
    # add agents and waypoints
    # safe xml tree to file
    print "Writing agents"
    SceneDef.addAgents(ct.N_RESIDENTS) # per context
    #SceneDef.addAgents(2)
    SceneDef.writeXML('agent')
    print "Done!"
      
    # log scene setup
    SceneDef.logSceneDef()
      
    # start listening to UDP port
    print "Opening UDP socket ..."
    UDPl = ag.UDPlistener()
    UDPl.start()
    
    # start avtr walk subprocess -> kill on exit    
    os.startfile(os.path.join(ct.PATH_TO_AVTRWALK, "avtrWalk.exe"))
    
    # wait for UDP server
    # i.e. wait until all avatars have been assign at least 2 waypoints
    print "======== Waiting for UDP server ========"
    waitingForData = 1
    while waitingForData:
        if UDPl.countWPs((ct.N_RESIDENTS*2)-1) > 1: # avIds start at 0
            waitingForData = 0
      
    # wait a bit
    time.sleep(5.0)    
    
    # get crowd manager
    CrowdMan = ag.CrowdManager(UDPl, SceneDef, myDl)
    
    # start new parcel delivery round
    myDl.startNewRound()
    
    # DEBUGGING: draw boundary boxes
    def drawContextBorders(bbCtx):
        crns = bbCtx.getCorners('world')
        viz.startLayer(viz.LINE_STRIP)
        viz.lineWidth(10)
        viz.vertexColor(1,0,0)
        
        for c in crns:
            viz.vertex(c[0], 1, c[1])            
        viz.endLayer()
            
    #drawContextBorders(SceneDef.bbCtx1)
    #drawContextBorders(SceneDef.bbCtx2)
    
    
    # DEBUG: show obstacle corners using balls
    def drawCorners(sD):
        # buildings
        tmpObst = sD.obstacles
        for cObst in tmpObst:
            for cP in cObst.getCorners('world'):
                cornerBalls.append(viz.add('ball.wrl'))
                cornerBalls[-1].setPosition(cP[0],0,cP[1])
        # show bounding box corners using balls
        for cP in sD.bbCtx1.getCorners('world'):
            cornerBalls.append(viz.add('ball.wrl'))
            cornerBalls[-1].setPosition(cP[0],0,cP[1])            
        # show bounding box corners using balls
        for cP in sD.bbCtx2.getCorners('world'):
            cornerBalls.append(viz.add('ball.wrl'))
            cornerBalls[-1].setPosition(cP[0],0,cP[1])
            
                
    #drawCorners(SceneDef)
    
    # DEBUG: define user callbacks
    def changeView():
        # enable viewpoint collision handling
        viz.MainView.collision( viz.OFF )
        viz.MainView.setPosition(0,200,0)
        viz.MainView.setAxisAngle(1,0,0,deg=90)
    
    def changeViewBack():
        viz.MainView.collision( viz.ON )
        viz.eyeheight(1.7)
    
    def checkViewPos():
        vP = viz.MainView.getPosition()
        vP = np.array([vP[0], vP[2]])
        for cObst in SceneDef.obstacles:
            #print "x: ", vP[0], "y: ", vP[1]
            if cObst.isPinObst(vP, 'world'):
                print "You are in: ", cObst.getName()
    
    vizact.onkeydown(' ', changeView)
    vizact.onkeydown('r', changeViewBack)
    vizact.onkeydown('v', checkViewPos)
    
    vizact.onkeydown('c', viz.MainView.collision, viz.TOGGLE)
    
    #vizact.onkeydown('n', myDl.placeOrder)