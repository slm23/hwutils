#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from java.time import Duration
from ccs import proxies
from optparse import OptionParser
import time
import re
import sys
import os

# fcs, focal-plane, rafts, reb states
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
#fcs.= None
fcs = None

# functions

def local_exit(retval=0):
    os._exit(retval)

try:
    fcs = CCS.attachProxy("fcs",99)
except:
    print("failed to attach subsystems, exiting...")
    local_exit(1)

# main
if __name__ == "__main__":
    #
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
    CCS.setDefaultTimeout(Duration.ofSeconds(60))

    print(t0str)

    # process command line
    parser=OptionParser()
    parser.set_defaults(movetime=0.0, count=0, delay=0.0)
    #parser.add_option("--movetime", dest="movetime", type="float", metavar="MOVETIME")
    parser.add_option("--count", dest="count", type="int", metavar="CYCLECOUNT")
    parser.add_option("--delay", dest="delay", type="float", metavar="DELAY")
    (options, args) = parser.parse_args()

    if len(args) == 0 or options.count == 0 or options.delay == 0:
        print(parser.print_help())
        local_exit(1)

    # initialization
    agent = fcs.getAgentProperty("agentName")
    state = fcs.getState()
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

    for i in range(options.count):
        t1 = time.time()
        t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t1))
        print("{} cycle: {}".format(t1str, i))
        fcs.autochanger().moveToHandoffWithHighVelocity()
        if fcs.autochanger().isAtHandoff():
            pass
        else:
            print("move to Handoff failed")
            local_exit(1)
        fcs.autochanger().moveToApproachStandbyPositionWithHighVelocity()
        if fcs.autochanger().isAtApproachStandbyPosition():
            pass
        else:
            print("move to ApproachStandby failed")
            local_exit(1)
        # need code here to wait for fcs to finish opening and closing
        time.sleep(options.delay)

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t1))
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    local_exit()
