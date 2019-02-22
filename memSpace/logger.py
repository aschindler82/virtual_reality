import viz
import vizact
import vizhtml

import os
import time
import warnings

import constants as ct
import numpy as np
import scipy.io as sio

# pre allocate some std events
STD_EVENTS = {}


################################################
# Class to log events
################################################
class LogData( object ):
    
    """Constructor"""
    def __init__(self, fields2log={}, path2logFile=ct.PATH_TO_LOGFILE,  useWebServer=0, **logIni):
        
        self.logInfo = {} # keeps information about logfile, subject etc
        self.data    = {} # keeps actual logging date per trial
        self.dTypes  = {} # keeps data types 
        self.useWebServer = useWebServer;
        
        # store initial data
        # i.e. subject name, etc.
        for key,value in logIni.items():
            self.logInfo[key] = value;
                    
        # folder where log file is saved
        self.path2logFile = path2logFile;
                
        # start webserver
        if useWebServer == 1:            
            self.startWebServer();
        
        # register log items
        if fields2log:
            self.initData(fields2log)
    
    """Register events here to make them logable"""
    def initData(self, *args):
                
        # if we get 2 arguments assume we want to register
        # a single log item with dType
        if len(args) == 2:
            kName = args[0]
            dType = args[1]
                                        
            # pre-allocate
            if not kName in self.data:
                self.data[kName]   = [];
                self.dTypes[kName] = dType
            else:
                wStr = ("Logfield: \"%s\" has been initialized, already!")%kName
                warnings.warn(wStr)
        
        else:                        
            # assume we submitted a dictionary with log fields an dtypes
            # register fields to log
            
            # reset         
            self.data    = {} # keeps actual logging date per trial
            
            # the re-fill
            for cKey, cDtype in args[0].items():
                self.initData(cKey, cDtype)
                
        
    """Append data to pre-allocated log field"""
    def logDictData(self, logDict):       
        
        #print "items: ", logDict.items()
                        
        # cycle over dict
        for key, val in logDict.items():
                                    
            # check whether this key exists
            if key in self.data:
                                                  
                # append logVal to corresponding list
                if isinstance(self.data[key], list):
                    #self.data[key].append( logDict[key] );
                    self.data[key].append( val );
                 
                    # DEBUGGING
                    #print "Logging: ", key, " ", logDict[key]
                 
                else:
                    wStr = ("Logfield: \"%s\" is not of type list!")%key
                    warnings.warn(wStr)                    
                                 
            else:
                wStr = ("Logfield: \"%s\" is not pre-allocated, yet!")%key
                warnings.warn(wStr)
            

    """Save logged events to disk"""
    def saveLogs(self, fileStem):

        # create log dir if it doesn't exist
        if not os.path.exists(self.path2logFile):
            os.makedirs(self.path2logFile);
            
        # concat file name
        finalLogFile = self.path2logFile + '/' + ct.SUBJECT_NAME + '_' + fileStem + time.strftime('_memSpace_%d-%m-%y_%H-%M.mat');
       
        # convert to scipy structured array

        # if anything was stored to log dict        
        if self.data:
        
            allKeys = self.data.keys() # get one key, assumes that lists are all of equal length
    
            # for all entries
            tupleList = []        
            for cEntry in range(len(self.data[allKeys[0]])):
                
                # for all fields
                cTuple = [] # start with list
                for cKey in allKeys:
                    cTuple.append( self.data[cKey][cEntry] )
           
                # convert to tuple and add to list
                tupleList.append( tuple(cTuple) )
            
            # add dtypes
            dTypeList = []
            for cKey, cVal in self.dTypes.items():
                if cVal == 'list':
                    cVal = list
                    
                dTypeList.append( (cKey, cVal) )
             
            # DEBUGGING       
            #print tupleList
            #print dTypeList
            
            if tupleList:                
                # store as structured numpy array
                structArray = np.rec.array(tupleList, dtype=dTypeList)
                
                # save as matlab file
                sio.savemat(finalLogFile, {'logs' : structArray})
                
                print 'Saved log data to: ' + finalLogFile;
                
            else:
                print "Delivery: Nothing logged -> nothing to be saved!"
        
        else:
            print "Delivery: Nothing logged -> nothing to be saved!"
        
        if self.useWebServer == 1:
            vizhtml.unregisterAllPages();


"""Handles WebServer"""
class WebServer():
    def __init__(self, webDict):
        print "init"            
        
        self.webDict = webDict
        
        # open html file
        htmlFile = os.path.join(ct.HTML_PATH, 'memSpace.htm');
        f = open (htmlFile,"r")

        #Read whole file into data
        htmlCode = f.read();

        # debugging: print it
        #print htmlCode;    

        # close the file
        f.close();
        
        # http://localhost:8080/vizhtml/websocket
        vizhtml.registerCode('websocket', htmlCode);
        
        # register method that is called when server connects to client
        vizhtml.onConnect(self.onWebServerConnect)
    
        # register time update function
        vizact.ontimer(5, self.updateTime)
    
    def updateServer(self, key, val):
        self.webDict[key] = val
    
    def updateTime(self):
        evtData = viz.Data( timeElapsed = "%d min"%(viz.tick()/60) )
        self.sendEvent2Server("set_timeElapsed", evtData)
        
        for cmnd, val in self.webDict.iteritems():
            self.sendEvent2Server(cmnd, val)
        
    def onWebServerConnect(self, e):
        print 'Client connected at',e.client.address
        
        
    def sendEvent2Server(self, event, data):
        """send stuff to webserver"""
        vizhtml.sendAll(event, data);