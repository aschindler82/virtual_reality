import numpy as np
import scipy.io as sio
import xml.etree.ElementTree as xmle

import os
import math

from shapely.geometry import mapping
from shapely.geometry import Point
from shapely import affinity
from xml.dom import minidom
from shapely.geometry import Polygon
from shapely.geometry import LineString
from shapely.geometry import box

import kmeans as km # see https://datasciencelab.wordpress.com/2014/01/15/improved-seeding-for-clustering-with-k-means/

import constants as ct


"""Defines an agent"""
class Agent:
    def __init__(self, x, y, ctxID):
        self.pStart    = np.array([x, y])
        self.wayPoints = []
        self.ctxID     = ctxID
    
    """Get context"""
    def getCtx(self):
        return self.ctxID
    
    """Get assigned waypoints"""
    def getWayPoints(self):
        return self.wayPoints
    
    """Add waypoint to agent"""
    def addWayPoint(self, wp):
        self.wayPoints.append(wp)
        
    """Write xml tags"""
    def getXMLtags(self, xmlTree):
        # new parent agent
        wpParent = xmle.SubElement(xmlTree, 'agent', {'x':str(np.round( self.pStart.item(0),2)), 'y':str(np.round(self.pStart.item(1),2)), 'n':str(1), 'dx':str(0), 'dy':str(0)})
        
        # add waypoints
        for cWp in self.wayPoints:
            xmle.SubElement(wpParent, 'addwaypoint', {'id':cWp.getID()})

"""Defines waypoint in pedSim space"""
class WayPoint:
    
    """create new waypoint"""
    def __init__(self, xy, wId, r, ctxID):
        self.xy    = xy        
        self.wId   = wId
        self.r     = r 
        self.ctxID = ctxID

    """get context id"""
    def getCtxID(self):
        return self.ctxID

    """returns xy -> in pedSim space"""
    def getXY(self):
        return self.xy

    """returns wp id"""
    def getID(self):
        return self.wId
    
    """returns radius"""
    def getR(self):
        return self.r
        
    """get xml tags for this obstacle"""
    def getXMLtags(self, xmlTree):
        xmle.SubElement(xmlTree, 'waypoint', {'x':str(np.round( self.xy[0],2)), 'y':str(np.round(self.xy[1],2)), 'id':self.wId, 'r':str(np.round(self.r,2))})
        
        
"""Defines an obstacle"""
class Obstacle:

    DIST_TO_WALL = 5
    
    """"Create new obstacle"""
    def __init__(self, name, context, geoObj, defSpace):
        #ps -> list of corner points
        self.obst = geoObj
        
        # safe name & context
        self.name    = name
        self.context = context

        #safe space
        if defSpace == 'ped' or defSpace == 'world':
            self.space = defSpace
                                
        else:
            print "Invalid defining space (valid: ped / world)"
            return
                
            
    """Get obstacle defining corners"""
    def getCorners(self, quSpace):
        crns = mapping(self.obst)
        crns = np.squeeze(np.array(crns["coordinates"]))
        if quSpace == self.space:        
            return crns            
        else:
            for i in range(len(crns)):
                crns[i][1] = -crns[i][1]
                
            #return tuple(map(tuple, crns))
            return crns.tolist()

    """Get center of obstacle bounding box"""
    def getBBcenter(self, quSpace):
        bds = self.getBounds(quSpace)
        ctrX = (bds[0]+bds[2])/2.0
        ctrY = (bds[1]+bds[3])/2.0
        
        return (ctrX, ctrY)
    
    """Get obtscle centroid"""
    def getCentroid(self, quSpace):
        ctr = self.obst.centroid
        x = ctr.x
        z = ctr.y        
        if quSpace == self.space:
            return (x, z)            
        else:           
            return (x,-z)
        
    """Get bounding box"""
    def getBounds(self, quSpace):
        bds = self.obst.bounds
        bds = list(bds)
        if not quSpace == self.space:
            bds[1] = -bds[1]
            bds[3] = -bds[3]
            
        return tuple(bds)
    
    """Get obstacle name"""
    def getName(self):
        return self.name
    
    """Get obstacle context"""
    def getContext(self):
        return self.context
        
    """Check whether p is in obstacle"""
    def isPinObst(self, p, quSpace, reScaleBy=1):
                
        if len(self.getCorners(quSpace)) > 2:
            if self.space == quSpace:
                # define point
                cP  = Point(p)
            else:
                # define point: flip z-axis
                cP  = Point((p[0], -p[1]))

            # shall we rescale obstacle before checking?
            if reScaleBy == 1:
                hit = self.obst.contains(cP)
            else:            
                scaledObst = affinity.scale(self.obst, xfact=reScaleBy, yfact=reScaleBy)
                hit = scaledObst.contains(cP)
            
            return hit
            
        else:                
            print "This obstacle has less than 3 corners!"
            return -1
            
            
    """Pushes out p to closest location on the line between poly center and p"""
    def pushOut(self, p, quSpace):

        #convert p to obst space
        if not self.space == quSpace:
            p = (p[0], -p[1])
        
        if len(self.getCorners(quSpace)) > 2:

            # get center of polygon bounding box
            polyCenter = self.getBBcenter(self.space)
        
            # find line equation between poly center and p
            # see http://stackoverflow.com/questions/21565994/method-to-return-the-equation-of-a-straight-line-given-two-points
            A = np.vstack([[polyCenter[0], p[0]], np.ones(2)]).T
            m, c = np.linalg.lstsq(A, [polyCenter[1], p[1]])[0]
            
            # incr / decr x vals to find closest point outside obst
            # do it in .1 m increments
            incrs = [-.1, .1]
            cPs = []
            ds  = []
            for i in range(2):
                cX = p[0]
                cIncr = incrs[i]
                while 1:
                    cX = cX+cIncr
                    cY = m*cX+c
                    cP = np.array([cX, cY])
                    
                    # debugging
                    #print "m ", m, "c ", c, "cP", cP
                    
                    if not self.isPinObst( cP, quSpace ):
                        ds.append(math.sqrt( (cX - p[0])**2 + (cY - p[1])**2 ))
                        cPs.append(cP)
                        break
                        
            # return p with closest distance to poly center
            pClosest = cPs[ ds.index(min(ds)) ]
            
            # return p in queried space
            if quSpace == self.space:
                return pClosest
            else:
                return (pClosest[0], -pClosest[1])
            
        else:
            print "This obstacle has less than 3 corners!"
            return -1
        
                    
    """get xml tags for this obstacle"""
    def getXMLtags(self, xmlTree):
        crns = self.getCorners('ped')
        for cP in range(len(crns)):
            if (cP == len(crns)-1):
                xmle.SubElement(xmlTree, 'obstacle', {'x1':str(np.round(crns[cP][0],2)), 'y1':str(np.round(crns[cP][1],2)), 'x2':str(np.round(crns[0][0],2)),    'y2':str(np.round(crns[0][1],2))})
            else:                
                xmle.SubElement(xmlTree, 'obstacle', {'x1':str(np.round(crns[cP][0],2)), 'y1':str(np.round(crns[cP][1],2)), 'x2':str(np.round(crns[cP+1][0],2)), 'y2':str(np.round(crns[cP+1][1],2))})
                
        

"""Writes scene def in XML file -> read by pedSim"""
class SceneDefinition:
    
    """Constructor """
    def __init__(self, oneCtx=0):
        # flag determines whether we have one or two
        # contexts
        self.oneCtx = oneCtx
        
        if self.oneCtx:
            self.condStr = "oneContext"
        else:
            self.condStr = "twoContexts"
        
        self.xmlAgtTree  = []
        self.xmlWpTree   = []
        self.xmlObstTree = []
        
        self.allX        = []
        self.allY        = []

        self.waypoints   = []
        self.obstacles   = []
        self.obstTypes   = []
        self.agents      = []        
                        
        self.add2BB      = 5
        self.bBox        = None
        self.bbCtx1      = None
        self.bbCtx2      = None
        
        # init xml trees
        self.xmlAgtTree = xmle.Element('avatarwalk')
        self.xmlAgtTree.append(xmle.Comment('Generated by Python'))

        self.xmlWpTree = xmle.Element('avatarwalk')
        self.xmlWpTree.append(xmle.Comment('Generated by Python'))
        
        self.xmlObstTree = xmle.Element('avatarwalk')
        self.xmlObstTree.append(xmle.Comment('Generated by Python'))
    
    
    """Log SceneDefinition"""
    def logSceneDef(self):
        
        # get building corners
        allBs = self.getBuildings()
        tupleList = []
        # save building info to lists
        for cB in allBs:
            tmpPs = [[round(float(xy), 2) for xy in ps] for ps in cB.getCorners('world')[0:-1]]
            tupleList.append( (cB.getName(), cB.getContext(), tmpPs)  )

        # store buildings in structured numpy array
        #buildingsArray = np.rec.array(tupleList, dtype=[ ('name', 'S10'), ('context', 'S10'), ('corners', [('c1', list),('c2', list),('c3', list),('c4', list)]) ])
        buildingsArray = np.rec.array(tupleList, dtype=[ ('name', 'S10'), ('context', 'S10'), ('corners', list) ])
        
        # get context boundaries
        sceneBox = [[round(float(xy), 2) for xy in ps] for ps in self.bBox.getCorners('world')[0:-1]]
        #sceneBox =   self.bBox.getCorners('world').round(2).tolist()[0:4]
        
        # log context boundaries
        if not self.oneCtx:
            ctx1Box = [[round(float(xy), 2) for xy in ps] for ps in self.bbCtx1.getCorners('world')[0:-1]]
            #ctx1Box  = self.bbCtx1.getCorners('world').round(2).tolist()[0:4]
            
            ctx2Box = [[round(float(xy), 2) for xy in ps] for ps in self.bbCtx2.getCorners('world')[0:-1]]
            #ctx2Box  = self.bbCtx2.getCorners('world').round(2).tolist()[0:4]
            
            # store in dict
            bBoxes = {'scene' : sceneBox, 'ctx1' : ctx1Box, 'ctx2' : ctx2Box }
        
        # just log scene bounding box
        else:
            bBoxes = {'scene' : sceneBox}
        
        # get waypoints
        tupleList = []
        for cWP in self.waypoints:
            x,z = cWP.getXY() # flip z-axis to get world coords!
            tupleList.append( (cWP.getID(), cWP.getCtxID(), [round(x,2), round(-z,2)], cWP.getR()) )
            
        # store waypoints in structured numpy array
        wpArray = np.rec.array(tupleList, dtype=[ ('wpID', 'S10'), ('context', int), ('xz', list), ('radius', int) ])
        
        # get agents
        tupleList = []
        for cAg in self.agents:
            wpIDs = []
            wpZXs = []
            for cWP in cAg.getWayPoints():
                wpIDs.append(cWP.getID())
                x,z = cWP.getXY() # flip z axis to get world coords
                wpZXs.append([round(x,2), round(-z,2)])
            
            # append this agent
            tupleList.append( (cAg.getCtx(), wpIDs, wpZXs) )
        
        # store waypoints in structured numpy array
        agArray = np.rec.array(tupleList, dtype=[ ('agContext', 'S10'), ('wpIDs', list), ('wpXZs', list) ])


        # store log data to dict and save to matlab file
        logData = {'buildings' : buildingsArray, 'bBoxes' : bBoxes, 'wayPoints' : wpArray, 'agents' : agArray, 'language' : ct.LANGUAGE}            
        sceneLogFile = os.path.join(ct.PATH_TO_LOGFILE, "%s_sceneDef_%s.mat"%(ct.SUBJECT_NAME, self.condStr) )
        sio.savemat(sceneLogFile, logData)
    
    
    """Use LLoyds algorithm to get waypoints equally spaced and outside buildings"""
    def addWayPoints(self, nWPs):

        # one or two contexts?
        if not self.oneCtx:
            nCtx = 2
            bBoxes = [self.bbCtx1, self.bbCtx2]
            wpStrs = ["wpI%s", "wpII%s"]
            
        else:
            nCtx = 1
            bBoxes = [self.bBox]
            wpStrs = ["wp%s"]
            
        # get wps for both contexts
        for cCtx in range(nCtx):
                    
            cX = np.array([])
            cY = np.array([])

            cBBox = bBoxes[cCtx]
            wpStr = wpStrs[cCtx]

            #===================================================================
            # # get bb obstacle object
            # if cCtx == 0:
            #     cBBox = self.bbCtx1
            #     wpStr = "wpI%s"
            # elif cCtx == 1:
            #     cBBox = self.bbCtx2
            #     wpStr = "wpII%s"
            #===================================================================

            bds = cBBox.getBounds('ped')
            #print "bounds", bds
            
            while cX.__len__() < 2000:
                # bBox minx, miny / maxx, maxy
                isInBB = 0                
                rX = np.random.uniform(bds[0], bds[2])
                rY = np.random.uniform(bds[1], bds[3])
                isInBB = cBBox.isPinObst(np.array([rX,rY]), 'ped')
                                                    
                if isInBB:
                    hit = 0                    
                    for cObst in self.obstacles:
                        if cObst.isPinObst(np.array([rX, rY]), 'ped'):
                            hit = 1
                            #print "Hit Building!"                            
                                                
                    if not hit:
                        cX = np.append(cX, rX)
                        cY = np.append(cY, rY)
                
            print "Getting waypoints ..."
                        
            # Random initialization                    
            #pCtr = Point( (cBBox.bounds[0] + cBBox.bounds[2])/2, (cBBox.bounds[1] + cBBox.bounds[3])/2 )
            #cX   = cX-pCtr.x            
            #cY   = cY-pCtr.y
            bds = np.array(cBBox.getBounds('ped'))
            scX = np.max(np.abs(bds))
            scY = np.max(np.abs(bds))
            ps  = np.column_stack(( np.divide(cX, scX), np.divide(cY, scY) ))
            #print "scaled Ps: ", ps
                    
            myKM = km.KPlusPlus(nWPs, X=ps)
            myKM.find_centers()
            myKM.plot_board()
            
            # get cluster centers
            wPs = myKM.mu
            for cWP in range(len(wPs)):
                
                tmpWP    = np.squeeze(np.asarray([wPs[cWP]]))
                #print "wp: ", tmpWP
                
                tmpWP[0] =  tmpWP[0]*scX
                tmpWP[1] =  tmpWP[1]*scY
                #print "scwp: ", tmpWP
                
                wPs[cWP] = tmpWP
                
                wpInObs = 0
                for cObs in self.obstacles: # exclude bounding box
                    if cObs.isPinObst(wPs[cWP], 'ped'):
                        wpInObs = 1
                        break
            
            # push wp out of obstacle if needed
            if wpInObs:
                print "WayPoint in obstacle!"
                wPs[cWP] = cObs.pushOut(wPs[cWP], 'ped')

            # finally add waypoints
            idCtr = 0
            r = 2
            for cWP in wPs:
                idCtr = idCtr+1
                cID = wpStr%(idCtr)
                self.waypoints.append(WayPoint(cWP, cID, r, cCtx+1))
                self.waypoints[-1].getXMLtags(self.xmlWpTree) # write xml tags
                        
            print "Done!"
        
    """Prettifies xml code"""
    def xmlPrettify(self, roughString):        
        #works just for print command, so far
        reparsed = minidom.parseString(roughString)
        return reparsed.toprettyxml(indent="  ")

    """Safe all x,y pos"""
    def safePs(self, ps):
        for cP in ps:
            self.allX.append(cP[0])
            self.allY.append(cP[1])
        
        
    """Writes obstacle xml tags x, y, x2, y2"""    
    #def addObstacle(self, name, context, obstType, ps, ctr, alpha, defSpace):
    def addObstacle(self, name, context, obstType, ps, defSpace):
        # use defSpace to define obstacle space
        # note: world and ped spaces are mirrowed along z axis
        # Obstacle methods take this into account via "space" property            
        
        # if ps contain xyz get rid of y coord 
        ps =[ p[0:3:2]  if len(p) == 3 else p for p in ps ]                
                        
        if len(ps) > 2:
            geoObj = Polygon(ps)
        elif len(ps) == 2:
            geoObj = LineString([ps[0], ps[1]])
        else:
            print "An obstacle needs at least two points!"
            return
        
                            
        # create obstacle new object
        self.obstacles.append(Obstacle(name, context, geoObj, defSpace))
        self.obstacles[-1].getXMLtags(self.xmlObstTree) # write xml tags

        # save obstacle type
        if obstType == 'building' or obstType == 'bbox':
            self.obstTypes.append(obstType)
        else:
            print 'Obstacle type must either be building or bbox!'
            return 0

        # get xy coords
        self.safePs(ps)

    """Return list of building objects"""
    def getBuildings(self):
        buildInds = [cO for cO, x in enumerate(self.obstTypes) if x == "building"]
        buildings = [self.obstacles[i] for i in buildInds]
        return buildings


    """Add bounding box to prevent agents from leaving town"""    
    def addBBs(self, bShapePs=None, alpha=0):
        
        # take rectangle containing all buildings as bBox
        if not bShapePs:
            # note: we are in pedSim space!
            # get overall bounding box        
            allX  = np.array(self.allX)
            allY  = np.array(self.allY)        
            maxXY = np.max(np.abs(np.append(allX, allY))) + self.add2BB
            bBox  = box( -maxXY, -maxXY, maxXY, maxXY )
            
            # add overall bbox
            self.bBox = Obstacle('bbox', 'N/A', bBox, 'ped')
            # debugging only: write xml tags
            #self.bBox.getXMLtags(self.xmlObstTree)
        
        # define submitted shape as bounding box
        else:
                            
            # define polygon
            bPoly = Polygon(bShapePs)
            
            # scale bounding shape to increase agents' walking areas
            bPoly = affinity.scale(bPoly, xfact=1.1, yfact=1.1, origin='center')
                        
            # assume we come from world space
            self.bBox = Obstacle('bbox', 'N/A', bPoly, 'world')
            
        
        # create context boundary if we are not in ctrl condition
        if not self.oneCtx:
                            
            # get bShape's bounds
            _, bbMinZ, _, bbMaxZ  = self.bBox.getBounds('ped')
            
            # divide box in two halves based on context border
            # do it in pedSim space z = -z            
            pBottom = Point(0,  bbMinZ*1.5)
            pTop    = Point(0,  bbMaxZ*1.5)
            ctxLine = LineString([pBottom, pTop])
            ctxLine = affinity.rotate(ctxLine, alpha, origin=(0,0))
            
            # get intersection with bbox
            ctxInterSect = self.bBox.obst.intersection(ctxLine).coords
            pSectBttm    = ctxInterSect[0]
            pSectTop     = ctxInterSect[1]
            
            # get coords of overall bBox
            bbCrns     = self.bBox.getCorners('ped')
            xCtr, zCtr = self.bBox.getCentroid('ped')
    
            ctx1Ps = []
            ctx2Ps = []
            # sort ps according to left/right center
            for cP in bbCrns:
                cX, cZ = cP
                if cX > xCtr:
                    ctx1Ps.append(cP)
                elif cX < xCtr:
                    ctx2Ps.append(cP)
                elif cX == xCtr:
                    if cZ > zCtr:
                        ctx1Ps.append(cP)
                    else:
                        ctx2Ps.append(cP)
        
            # define helper function to sort points counterclockwise
            # around center point
            def algo(p, ctr=0):            
                ctrX, ctrY = ctr    
                return (math.atan2(p[0] - ctrX, p[1] - ctrY) + 2 * math.pi) % (2*math.pi)
            
            # create obstacle object for context1        
            ps = [ pSectTop, pSectBttm ] + ctx1Ps
            ps.sort(key=lambda p: algo(p, (0,0)))
            #ps.reverse()        
            polyCtx1 = Polygon(ps)
            self.bbCtx1 = Obstacle('Ctx1Box', 'ct1', polyCtx1, 'ped')
            self.bbCtx1.getXMLtags(self.xmlObstTree) # write xml tags        
            
            # create obstacle object for context2        
            ps = [ pSectBttm, pSectTop ] + ctx2Ps
            ps.sort(key=lambda p: algo(p, (0,0)))
            #ps.reverse()        
            polyCtx2 = Polygon(ps)
            self.bbCtx2 = Obstacle('Ctx2Box', 'ct2', polyCtx2, 'ped')
            self.bbCtx2.getXMLtags(self.xmlObstTree) # write xml tags
    
            #debugging: context polys should have the same area
            #print "C1", polyCtx1.area
            #print "C2", polyCtx2.area
            
        else:
            # write xml tags for scene boundaries
            self.bBox.getXMLtags(self.xmlObstTree)
        
    """Add agents and waypoints"""
    def addAgents(self, n):
        
        # one or two contexts?
        if not self.oneCtx:
            nCtx = 2
            bBoxes = [self.bbCtx1, self.bbCtx2]
            wpStrs = ["wpI%s", "wpII%s"]
            
        else:
            nCtx = 1
            bBoxes = [self.bBox]
            wpStrs = ["wp%s"]
        
        # for both contexts
        for cCtx in range(nCtx):
            
            # for n agents to add
            for cAg in range(n):  # @UnusedVariable
                
                # while this agents wasn't added
                addedAgt = 0
                while not addedAgt:
                    
                    # bBox minx, miny / maxx, maxy
                    isInBB = 0
                    bds = bBoxes[cCtx].getBounds('ped')
                    rX = np.random.uniform(bds[0], bds[2])
                    rY = np.random.uniform(bds[1], bds[3])
                    isInBB = bBoxes[cCtx].isPinObst([rX, rY], 'ped')
                    
                    #===========================================================
                    # if cCtx == 0:
                    #     bds = self.bbCtx1.getBounds('ped')
                    #     rX = np.random.uniform(bds[0], bds[2])
                    #     rY = np.random.uniform(bds[1], bds[3])
                    #     isInBB = self.bbCtx1.isPinObst([rX, rY], 'ped')
                    #     
                    # elif cCtx == 1:
                    #     bds = self.bbCtx2.getBounds('ped')
                    #     rX = np.random.uniform(bds[0], bds[2])
                    #     rY = np.random.uniform(bds[1], bds[3])
                    #     isInBB = self.bbCtx2.isPinObst([rX, rY], 'ped')
                    #===========================================================
                        
                    if isInBB:
                        isInObst = 0
                        for cObst in self.obstacles:
                            #print "Checking: ", cObst.getName()
                            
                            if cObst.isPinObst(np.array([rX, rY]), 'ped'):
                                isInObst = 1
                                #print "Agent in obstacle: ", cObst.getName()
                                break
                                
                        # if not overlapping with any obstacle
                        if not isInObst:
                            self.agents.append(Agent(rX, rY, cCtx+1))
                            
                            # add waypoint IDs in random order
                            ctxIDs = np.array(map(lambda x: x.getCtxID(), self.waypoints))
                            
                            # two contexts:
                            if not self.oneCtx:                                                            
                                cInds  = np.where(ctxIDs==cCtx+1)
                                
                            # one context:
                            else:
                                # take wp of both contexts
                                cInds  = np.where(ctxIDs > -1)
                            
                            cWPs = np.array(self.waypoints)
                            cWPs = cWPs[cInds]
                            
                            randInds = np.random.permutation(len(cWPs))
                            for cWPind in randInds:
                                self.agents[-1].addWayPoint(cWPs[cWPind])
                                
                            # get XML tags
                            self.agents[-1].getXMLtags(self.xmlAgtTree)                                            
                            addedAgt = 1
                        

    """Print xml tree"""
    def printXML(self, tagType):
        if tagType == 'agent':
            roughString = xmle.tostring(self.xmlAgtTree, 'utf-8')            

        elif tagType == 'waypoint':
            roughString = xmle.tostring(self.xmlWpTree, 'utf-8')
            
        elif tagType == 'obstacle':
            roughString = xmle.tostring(self.xmlObstTree, 'utf-8')
        
        print self.xmlPrettify(roughString)

        
    """Write xml tree to file """
    def writeXML(self, tagType):
        if tagType == 'agent':
            tmp = xmle.ElementTree(self.xmlAgtTree)            
            fName = os.path.join(ct.XML_PATH, 'agents.xml')

        elif tagType == 'waypoint':
            tmp = xmle.ElementTree(self.xmlWpTree)
            fName = os.path.join(ct.XML_PATH, 'waypoints.xml')
            
        elif tagType == 'obstacle':
            tmp = xmle.ElementTree(self.xmlObstTree)
            fName = os.path.join(ct.XML_PATH, 'obstacles.xml')
    
        tmp.write(fName, encoding='utf-8', xml_declaration=True)