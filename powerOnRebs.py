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


# globals
# pseudo = ReadoutMode.PSEUDO

rebpower = None
# functions


def local_exit(retval=0):
    os._exit(retval)


try:
    rebpower = CCS.attachProxy("aliveness-rebpower")
except:
    print("failed to attach subsystems, exiting...")
    local_exit(1)

# main
if __name__ == "__main__":
    #
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    # process command line
    parser = OptionParser()
    parser.set_defaults(exptime=0.0, expcount=0, rowshift=0)
    parser.add_option("--rebexpr", dest="rebexpr", type="string", metavar="REBEXPR")
    (options, args) = parser.parse_args()

    if len(args) != 0 or options.rebexpr is None:
        print(parser.print_help())
        local_exit(1)

    # initialization
    agent = rebpower.getAgentProperty("agentName")
    state = rebpower.getState()
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

    local_exit()
