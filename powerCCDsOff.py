#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from ccs import proxies
import sys
import math
import re
import time

# globals
try:
    fp = CCS.attachProxy("focal-plane")  #### CHANGE
except:
    fp = None

srebs = []
crebs = []

# functions

def init_fpdict(state):
    """
    """
    fpdict = dict()  # will hold current data for REBs
    for reb in sorted(srebs + crebs):
        fpdict[reb] = dict()
        fpdict[reb]["CCDstate"] = False
        fpdict[reb]["HVstate"] = False
        fpdict[reb]["enable"] = False
        # fpdict[reb][""] = ""
    return fpdict

def update_fpdict(state, fpdict):
    """
    """
    for reb in sorted(srebs + crebs):
        reb_state = str(state.getComponentStateBundle(reb))
        # print("reb_state = {}".format(reb_state))
        if re.search(r"CCDsPowerState:ON", reb_state):
            fpdict[reb]["CCDstate"] = True
            # print("{} CCDs are ON".format(reb))
        else:
            fpdict[reb]["CCDstate"] = False
            # print("{} CCDs are OFF".format(reb))
        if re.search(r"HVBiasState:ON", reb_state):
            fpdict[reb]["HVstate"] = True
            # print("{} HVBiases are ON".format(reb))
        else:
            fpdict[reb]["HVstate"] = False
            # print("{} HVBiases are OFF".format(reb))
        fpdict[reb]["enable"] = reb_enable # retrieve as config later
        # fpdict[reb][""] = ""

def init_components(state):
    for component in state.componentsWithStates.iterator():
        if re.match(r"R../Reb[012]", component):
            srebs.append(str(component))
        if re.match(r"R../Reb[GW]", component):
            crebs.append(str(component))

if __name__ == "__main__":
    #
    reb_enable = True

    if fp is None:
        print("missing fp subsystem, exiting...")
        exit
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    state = fp.getState()
    # print(state)
    init_components(state)
    # print("science rebs={}".format(srebs))
    # print("corner rebs={}".format(crebs))

    # initialization
    state = fp.getState()
    fpdict = init_fpdict(state)

    ondelay = 30.0
    seqdelay = 1.0
    update_fpdict(state, fpdict)
    for reb in sorted(fpdict):
        if fpdict[reb]["CCDstate"] and fpdict[reb]["enable"]:
            print("{} is ON and enabled -- powering CCDs off".format(reb))
            getattr(fp, reb)().powerCCDsOff()
            print("getattr(fp, {})().powerCCDsOff()".format(reb))
            time.sleep(seqdelay)
        else:
            print("{} is OFF or NOT enabled".format(reb))

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
    print(t0str)
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    exit

