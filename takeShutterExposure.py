#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from java.time import Duration
from ccs import proxies
from optparse import OptionParser
import time
import re
import sys
import os

# shutter, focal-plane, rafts, reb states
from org.lsst.ccs.bus.states import AlertState
from org.lsst.ccs.bus.states import CommandState
from org.lsst.ccs.bus.states import ConfigurationState
#from org.lsst.ccs.subsystem.focalplane.states import FocalPlaneState
#from org.lsst.ccs.subsystem.focalplane.states import SequencerState
#from org.lsst.ccs.subsystem.rafts.states import HVBiasState
#from org.lsst.ccs.subsystem.rafts.states import RebDeviceState
#from org.lsst.ccs.subsystem.rafts.states import RebValidationState
#from org.lsst.ccs.subsystem.rafts.states import CCDsPowerState
#from org.lsst.ccs.subsystem.focalplane.LSE71Commands import ReadoutMode


# globals

#bb = None
#shutter.= None
shutter = None

# functions

def local_exit(retval=0):
    os._exit(retval)

try:
    shutter = CCS.attachProxy("cam-shutter",99)
except:
    print("failed to attach subsystems, exiting...")
    local_exit(1)

# main
if __name__ == "__main__":
    #
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    print(t0str)

    # process command line
    parser=OptionParser()
    parser.set_defaults(exptime=0.0, expcount=0, delay=0)
    parser.add_option("--exptime", dest="exptime", type="float", metavar="EXPTIME")
    parser.add_option("--expcount", dest="expcount", type="int", metavar="EXPCOUNT")
    parser.add_option("--delay", dest="delay", type="float", metavar="DELAY")
    (options, args) = parser.parse_args()

    if len(args) != 0 or options.exptime == 0 or options.expcount == 0 or options.delay == 0:
        print(parser.print_help())
        local_exit(1)

    # initialization
    agent = shutter.getAgentProperty("agentName")
    state = shutter.getState()
    # AlertState: [NOMINAL, WARNING, ALARM]
    sstate = state.getState(AlertState)
    if sstate != AlertState.NOMINAL:
        print("{} is in AlertState {}".format(agent, sstate))
    # CommandState: [READY, ACTIVE]
    sstate = state.getState(CommandState)
    if sstate != CommandState.READY:
        print("{} is not in READY CommandState, exiting...".format(agent))
        local_exit()
    # ConfigurationState: [UNCONFIGURED, CONFIGURED, DIRTY, INITIAL_SAFE]
    sstate = state.getState(ConfigurationState)
    if sstate == ConfigurationState.UNCONFIGURED:
        print("{} is in UNCONFIGURED state, exiting...".format(agent))
        local_exit()

    # close shutter and flush out the CCD assuming it has been sitting a long time
    # this isn't needed in an active system (or query darktime, time since clear)
    try:
        shutter.closeShutter()
    except:
        pass
    time.sleep(1.0)

    
    for i in range(options.expcount):
        t1 = time.time()
        t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t1))
        print("{} exposure: {}".format(t1str, i))
        shutter.takeExposure(options.exptime)
        # need code here to wait for shutter to finish opening and closing
        time.sleep(options.exptime)
        time.sleep(1.0)
        time.sleep(options.delay)

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t1))
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    local_exit()
