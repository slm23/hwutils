#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from java.time import Duration
from ccs import proxies
from optparse import OptionParser
import time
import re
import sys
import os

# focal-plane, rafts, reb states
from org.lsst.ccs.bus.states import AlertState
from org.lsst.ccs.bus.states import CommandState
from org.lsst.ccs.bus.states import ConfigurationState
from org.lsst.ccs.subsystem.focalplane.states import FocalPlaneState
from org.lsst.ccs.subsystem.focalplane.states import SequencerState
from org.lsst.ccs.subsystem.rafts.states import HVBiasState
from org.lsst.ccs.subsystem.rafts.states import RebDeviceState
from org.lsst.ccs.subsystem.rafts.states import RebValidationState
from org.lsst.ccs.subsystem.rafts.states import CCDsPowerState
from org.lsst.ccs.subsystem.focalplane.LSE71Commands import ReadoutMode


# globals
pseudo = ReadoutMode.PSEUDO

bb = None
fp = None
# functions

def local_exit(retval=0):
    os._exit(retval)

try:
    bb = CCS.attachProxy("ts8-bench")
    fp = CCS.attachProxy("ts8-fp")  #### CHANGE
except:
    print("failed to attach subsystems, exiting...")
    local_exit(1)

# main
if __name__ == "__main__":
    #
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    # process command line
    parser=OptionParser()
    parser.set_defaults(exptime=0.0, expcount=0, rowshift=0)
    parser.add_option("--exptime", dest="exptime", type="float", metavar="EXPTIME")
    parser.add_option("--expcount", dest="expcount", type="int", metavar="EXPCOUNT")
    parser.add_option("--rowshift", dest="rowshift", type="int", metavar="ROWSHIFT")
    (options, args) = parser.parse_args()

    if len(args) != 0 or options.exptime == 0 or options.expcount == 0 or options.rowshift == 0:
        print(parser.print_help())
        local_exit(1)

    # initialization
    agent = fp.getAgentProperty("agentName")
    state = fp.getState()
    # AlertState: [NOMINAL, WARNING, ALARM]
    sstate = state.getState(AlertState)
    if sstate != AlertState.NOMINAL:
        print("{} is in AlertState {}".format(agent, sstate))
    # CommandState: [READY, ACTIVE]
    sstate = state.getState(CommandState)
    if sstate != CommandState.READY:
        print("{} is not in READY CommandState, exiting...".format(agent))
        local_exit()
    # SequencerState: [IDLE, RUNNING, IDLE_FLUSH]
    sstate = state.getState(SequencerState)
    if not re.match(r"IDLE", sstate.toString()):
        print("{} sequencer is not in IDLE* state, exiting...".format(agent))
        local_exit()
    # FocalPlaneState: [NEEDS_CLEAR,
    #     CLEARING, INTEGRATING, READING_OUT, QUIESCENT, ROW_SHIFT, IMAGE_WAIT]
    sstate = state.getState(FocalPlaneState)
    if sstate != FocalPlaneState.QUIESCENT:
        print("{} is not in QUIESCENT state, exiting...".format(agent))
        local_exit()
    # ConfigurationState: [UNCONFIGURED, CONFIGURED, DIRTY, INITIAL_SAFE]
    sstate = state.getState(ConfigurationState)
    if sstate == ConfigurationState.UNCONFIGURED:
        print("{} is in UNCONFIGURED state, exiting...".format(agent))
        local_exit()

    for reb in state.componentsWithStates:
        # RebDeviceState: [OFFLINE, ONLINE]
        sstate = state.getComponentState(reb, RebDeviceState)
        if sstate == RebDeviceState.OFFLINE:
            print("{}/{} RebDeviceState is UNKNOWN, exiting...", agent, reb)
            local_exit()
        # RebValidationState: [UNKNOWN, VALID, INVALID]
        sstate = state.getComponentState(reb, RebValidationState)
        if sstate != RebValidationState.VALID:
            print("{}/{} RebValidationState is UNKNOWN, exiting...", agent, reb)
            local_exit()
        # CCDsPowerState: [UNKNOWN, FAULT, OFF, ON, DELTA]
        sstate = state.getComponentState(reb, CCDsPowerState)
        if sstate == CCDsPowerState.UNKNOWN:
            print("{}/{} CCDsPowerState is UNKNOWN, exiting...", agent, reb)
            local_exit()
        # HVBiasState: [UNKNOWN, OFF, ON]
        sstate = state.getComponentState(reb, HVBiasState)
        if sstate == HVBiasState.UNKNOWN:
            print("{}/{} HVBiasState is UNKNOWN, exiting...", agent, reb)
            local_exit()

    # close shutter and flush out the CCD assuming it has been sitting a long time
    # this isn't needed in an active system (or query darktime, time since clear)
    try:
        bb.ProjectorShutter().closeShutter()
    except:
        pass
    fp.clear(1)
    time.sleep(0.1)
    fp.clear(5)
    time.sleep(0.4)
    # do a pseudo read to give a nice clear (after sitting a long while)
    res = fp.startIntegration()
    res = fp.endIntegration(pseudo)
    time.sleep(2.4)
    # again
    res = fp.startIntegration()
    res = fp.endIntegration(pseudo)
    time.sleep(2.4)

    # cache initial value
    stepAfterIntegrate0 = fp.getConfigurationParameterValue(
        "sequencerConfig", "stepAfterIntegrate"
    )
    # must be set to false
    fp.submitChange("sequencerConfig", "stepAfterIntegrate", "false")
    fp.applySubmittedChanges()
    # begin the image
    bb.ProjectorShutter().openShutter()
    print(fp.startIntegration())
    print("integrating"),
    time.sleep(0.1)  # est shutter open delay

    print("expose({}s)".format(options.exptime)),
    time.sleep(options.exptime)
    for sh in range(options.expcount - 1):
        print("shift({})".format(options.rowshift)),
        fp.shiftNRows(options.rowshift)
        print("expose({}s)".format(options.exptime)),
        time.sleep(options.exptime)
    print("done")

    bb.ProjectorShutter().closeShutter()
    time.sleep(0.2)
    fp.endIntegration()
    fp.waitForFitsFiles()

    # restore cached initial config for stepAfterIntegrate
    fp.submitChange("sequencerConfig", "stepAfterIntegrate", stepAfterIntegrate0)
    fp.applySubmittedChanges()

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t1))
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    local_exit()
