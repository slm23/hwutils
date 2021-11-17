#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from java.time import Duration
from ccs import proxies
import time
import re
import argparse

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
try:
    bb = CCS.attachProxy("ts8-bench")
    fp = CCS.attachProxy("ts8-fp")  #### CHANGE
except:
    print("failed to attach subsystems, exiting...")
    exit(-1)

# functions


def parse_args():
    """handle command line"""
    #
    parser = argparse.ArgumentParser(
        description="Take row shift images for given exptime, shift_size, repeat_count",
        epilog="Number of exposures will be (repeat_count + 1)",
    )
    parser.add_argument(
        "exptime",
        nargs=1,
        default=1.0,
        type=float,
        required=True,
        help="time between shifts",
    )
    parser.add_argument(
        "shift_size",
        nargs=1,
        default=20,
        type=int,
        required=True,
        help="number of rows to shift",
    )
    parser.add_argument(
        "repeat_count",
        nargs=1,
        default=0,
        type=int,
        required=True,
        help="number of times to shift",
    )
    return parser.parse_args()


# main
if __name__ == "__main__":
    #
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
    # process command line args
    optlist = parse_args()

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
        exit(-1)
    # SequencerState: [IDLE, RUNNING, IDLE_FLUSH]
    sstate = state.getState(SequencerState)
    if not re.match(r"IDLE", sstate.toString()):
        print("{} sequencer is not in IDLE* state, exiting...".format(agent))
        exit(-1)
    # FocalPlaneState: [NEEDS_CLEAR,
    #     CLEARING, INTEGRATING, READING_OUT, QUIESCENT, ROW_SHIFT, IMAGE_WAIT]
    sstate = state.getState(FocalPlaneState)
    if sstate != FocalPlaneState.QUIESCENT:
        print("{} is not in QUIESCENT state, exiting...".format(agent))
        exit(-1)
    # ConfigurationState: [UNCONFIGURED, CONFIGURED, DIRTY, INITIAL_SAFE]
    sstate = state.getState(ConfigurationState)
    if sstate != ConfigurationState.UNCONFIGURED:
        print("{} is in UNCONFIGURED state, exiting...".format(agent))
        exit(-1)

    for reb in state.componentsWithStates:
        # RebDeviceState: [OFFLINE, ONLINE]
        sstate = state.getComponentState(reb, RebDeviceState)
        if sstate == RebDeviceState.OFFLINE:
            print("{}/{} RebDeviceState is UNKNOWN, exiting...", agent, reb)
            exit(-1)
        # RebValidationState: [UNKNOWN, VALID, INVALID]
        sstate = state.getComponentState(reb, RebValidationState)
        if sstate != RebValidationState.VALID:
            print("{}/{} RebValidationState is UNKNOWN, exiting...", agent, reb)
            exit(-1)
        # CCDsPowerState: [UNKNOWN, FAULT, OFF, ON, DELTA]
        sstate = state.getComponentState(reb, CCDsPowerState)
        if sstate == CCDsPowerState.UNKNOWN:
            print("{}/{} CCDsPowerState is UNKNOWN, exiting...", agent, reb)
            exit(-1)
        # HVBiasState: [UNKNOWN, OFF, ON]
        sstate = state.getComponentState(reb, HVBiasState)
        if sstate == HVBiasState.UNKNOWN:
            print("{}/{} HVBiasState is UNKNOWN, exiting...", agent, reb)
            exit(-1)

    # flush out the CCD assuming it has been sitting a long time
    # this isn't needed in an active system (or query darktime, time since clear)
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

    print("expose({}s)".format(optlist.exptime)),
    time.sleep(optlist.exptime)
    for sh in range(optlist.repeat_count):
        print("shift({})".format(optlist.shift_size)),
        fp.shiftNRows(optlist.shift_size)
        print("expose({}s)".format(optlist.exptime)),
        time.sleep(optlist.exptime)
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

    exit
