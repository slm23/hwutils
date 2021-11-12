#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from java.time import Duration
from ccs import proxies
import time
import re
import sys
import math
# focal-plane, rafts, reb states
from org.lsst.ccs.bus.states import AlertState
from org.lsst.ccs.bus.states import CommandState
from org.lsst.ccs.bus.states import ConfigurationState
from org.lsst.ccs.bus.states import OperationalState
from org.lsst.ccs.subsystem.focalplane.states import FocalPlaneState;
from org.lsst.ccs.subsystem.focalplane.states import SequencerState;
from org.lsst.ccs.subsystem.rafts.states import HVBiasState;
from org.lsst.ccs.subsystem.rafts.states import RebDeviceState;
from org.lsst.ccs.subsystem.rafts.states import RebValidationState;
from org.lsst.ccs.subsystem.rafts.states import RebDeviceState
from org.lsst.ccs.subsystem.rafts.states import RebValidationState
from org.lsst.ccs.subsystem.rafts.states import CCDsPowerState
from org.lsst.ccs.subsystem.focalplane.LSE71Commands import ReadoutMode

# globals
pseudo = ReadoutMode.PSEUDO
exptime = 20.0
row_shift_cnt = 10
row_shift = 50

bb = None
fp = None
try:
    bb = CCS.attachProxy("ts8-bench")
    fp = CCS.attachProxy("ts8-fp")  #### CHANGE
except:
    print("failed to attach subsystems, exiting...")
    exit(-1)

# functions


# main
if __name__ == "__main__":
    #
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    # initialization
    agent = fp.getAgentProperty("agentName")
    state = fp.getState()
    #AlertState:WARNING CommandState:READY ConfigurationState:CONFIGURED FocalPlaneState:QUIESCENT
    #                   OperationalState:ENGINEERING_OK PhaseState:OPERATIONAL SequencerState:IDLE 
    #AlertState, [NOMINAL, WARNING, ALARM]
    #FocalPlaneState: [NEEDS_CLEAR, CLEARING, INTEGRATING, READING_OUT, QUIESCENT, ROW_SHIFT, IMAGE_WAIT]
    #SequencerState: [IDLE, RUNNING, IDLE_FLUSH]
    #CommandState: [READY, ACTIVE]
    #ConfigurationState, [UNCONFIGURED, CONFIGURED, DIRTY, INITIAL_SAFE]
    sstate = state.getState(AlertState)
    if sstate != AlertState.NOMINAL:
        print("{} is in AlertState {}".format(agent, sstate))
    sstate = state.getState(CommandState)
    if sstate != CommandState.READY:
        print("{} is not in READY CommandState, exiting...".format(agent))
        exit(-1)
    sstate = state.getState(SequencerState)
    if not re.match(r"IDLE", sstate.toString()):
        print("{} sequencer is not in IDLE* state, exiting...".format(agent))
        exit(-1)
    sstate = state.getState(FocalPlaneState)
    if sstate != FocalPlaneState.QUIESCENT:
        print("{} is not in QUIESCENT state, exiting...".format(agent))
        exit(-1)
    
    #'CCDsPowerState:ON HVBiasState:ON RebDeviceState:ONLINE RebValidationState:VALID
    #CCDsPowerState, [UNKNOWN, FAULT, OFF, ON, DELTA]
    #HVBiasState, [UNKNOWN, OFF, ON]
    #RebDeviceState, [OFFLINE, ONLINE]
    #RebValidationState, [UNKNOWN, VALID, INVALID]
    for reb in state.componentsWithStates:
        sstate = state.getComponentState(reb, RebDeviceState)
        if sstate == RebDeviceState.OFFLINE:
            print("{}/{} RebDeviceState is UNKNOWN, exiting...", agent, reb)
            exit(-1)
        sstate = state.getComponentState(reb, RebValidationState)
        if sstate != RebValidationState.VALID:
            print("{}/{} RebValidationState is UNKNOWN, exiting...", agent, reb)
            exit(-1)
        sstate = state.getComponentState(reb, CCDsPowerState)
        if sstate == CCDsPowerState.UNKNOWN:
            print("{}/{} CCDsPowerState is UNKNOWN, exiting...", agent, reb)
            exit(-1)
        sstate = state.getComponentState(reb, HVBiasState)
        if sstate == HVBiasState.UNKNOWN:
            print("{}/{} HVBiasState is UNKNOWN, exiting...", agent, reb)
            exit(-1)

    fp.clear(1)
    time.sleep(0.1)
    fp.clear(1)
    time.sleep(0.1)
    fp.clear(1)
    time.sleep(0.1)
    # do a pseudo read to give a nice clear (after sitting a long while)
    res = fp.startIntegration()
    res = fp.endIntegration(pseudo)
    time.sleep(2.4)
    #print(fp.getState())
    #print("start: stepAfterIntegrate={}".format(fp.getConfigurationParameterValue("sequencerConfig", "stepAfterIntegrate")))
    stepAfterIntegrate0 = fp.getConfigurationParameterValue("sequencerConfig", "stepAfterIntegrate")
    # change back to stepAfterIntegrate false to enable row shifting
    fp.submitChange("sequencerConfig", "stepAfterIntegrate", 'false')
    fp.applySubmittedChanges()
    #print("new:   stepAfterIntegrate={}".format(fp.getConfigurationParameterValue("sequencerConfig", "stepAfterIntegrate")))
    bb.ProjectorShutter().openShutter()
    print(fp.startIntegration())
    #print(fp.getState())
    print("integrating"),
    
    print("expose({}s)".format(exptime)),
    time.sleep(exptime)
    for sh in range(row_shift_cnt):
        print("shift({})".format(row_shift)),
        fp.shiftNRows(row_shift)
        print("expose({}s)".format(exptime)),
        time.sleep(exptime)
    print("done")

    bb.ProjectorShutter().closeShutter()
    time.sleep(0.2)
    fp.endIntegration()
    #print(fp.getState())
    fp.waitForFitsFiles()
    #print(fp.getState())

    # change back to previous config for stepAfterIntegrate
    fp.submitChange("sequencerConfig", "stepAfterIntegrate", stepAfterIntegrate0)
    fp.applySubmittedChanges()
    #print("final: stepAfterIntegrate={}".format(fp.getConfigurationParameterValue("sequencerConfig", "stepAfterIntegrate")))

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
    #print(t0str)
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    exit

