import viz
import vizfx
import os

import memSpace.constants as ct
import memSpace.pointingTask as pt

viz.setMultiSample(4)
viz.go()

viz.eyeheight(ct.EYE_HEIGHT)


# add code to navigate through scene via "wasd" control
pt.WalkNavigate(forward='w', backward='s', left='a', right='d', moveScale=ct.MOVE_SPEED, turnScale=1.0)


# add sky
sky = viz.add('sky_day.osgb')

# add fixation cross
texture = viz.add( os.path.join(ct.PATH_TO_IMGS, 'fixationCross-01.png') )
quad = viz.addTexQuad(viz.SCREEN, align=viz.TEXT_CENTER_CENTER, pos=(0.5,0.5,0))
p = 0.05
#quad.setScale([16.0*p, 12.0*p, 1])
quad.setScale([(16.0)/2*p, 12.0*p, 1])
quad.texture(texture)

# add grassy plane surrounded by mountains
gScale = 1.1
hills = vizfx.addChild(os.path.join(ct.PATH_TO_OSGB, 'hills.osgb'))
hills.setScale(gScale, gScale, gScale)

# create new scene definition object
#SceneDef = sc.SceneDefinition();

# load building nodes and place according to external txt file
pBuildings = []
with open('./coords.txt') as fp:
    for cB in fp:
        # store building information in list
        # one row corresponds to one building:
        # context name x y z rotation
        
        # scale factor
        scFac = 60
        
        bData  = []
        bNodes = []
        
        # split line
        bData.append(cB.split())
        
        # get context
        ctx = int(bData[-1][0][2])        
        
        # convert xyz and orientation angle to numbers
        bData[-1][2:6] = [float(i) for i in bData[-1][2:6]]
    
        # this building's orientation            
        theta = bData[-1][5]
        
        # import model if not a house
        if not 'house' in bData[-1][1]:
            # filler houses          
            cNode = viz.add(os.path.join(ct.PATH_TO_OSGB, "%s%s"%(bData[-1][1], ".OSGB")))
            bNodes.append( cNode ) # add building
            cNode.setPosition(bData[-1][2]*scFac, bData[-1][3], bData[-1][4]*scFac)                   # set building's position
            cNode.setAxisAngle(0, 1, 0, theta, viz.ABS_LOCAL)                                         # rotate building in worldviz
        
            # set building's animation params
            cNode.setAnimationLoopMode(viz.OFF, node='')
            cNode.setAnimationState(viz.STOP, node='')      
            
            # add building to list
            pBuildings.append( pt.building(bData[-1][1], ctx, cNode) )
        
    ptTask = pt.PointingTask(pBuildings)    
    
    ptTask.startNewRound()
    
        
    