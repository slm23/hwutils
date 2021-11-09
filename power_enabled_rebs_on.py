#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from ccs import proxies
import sys
import math
import re
import time

# globals
try:
    rebpower = CCS.attachProxy("rebpower")  #### CHANGE
except:
    rebpower = None
srebs = []
crebs = []
rebpss = []

# functions

def init_rebdict(state):
    """
    """
    rebdict = dict()  # will hold current data for REBs
    for reb in sorted(srebs + crebs):
        rebdict[reb] = dict()
        rebdict[reb]["state"] = False
        rebdict[reb]["enable"] = False
        # rebdict[reb][""] = ""
    return rebdict

def update_rebdict(state, rebdict):
    """
    """
    for reb in sorted(srebs + crebs):
        reb_state = str(state.getComponentStateBundle(reb))
        # print("reb_state = {}".format(reb_state))
        if re.search(r"RebPowerState:ON", reb_state):
            rebdict[reb]["state"] = True
            # print("{} is ON".format(reb))
        else:
            rebdict[reb]["state"] = False
            # print("{} is OFF".format(reb))
        rebdict[reb]["enable"] = reb_enable # retrieve as config later
        # rebdict[reb][""] = ""

def init_components(state):
    for component in state.componentsWithStates.iterator():
        if re.match(r"RebPS/P..", component):
            rebpss.append(str(component))
        if re.match(r"R../Reb[012]", component):
            srebs.append(str(component))
        if re.match(r"R../Reb[GW]", component):
            crebs.append(str(component))

if __name__ == "__main__":
    #
    reb_enable = True

    if rebpower is None:
        print("missing rebpower subsystem, exiting...")
        exit(-1)
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    state = rebpower.getState()
    # print(state)
    init_components(state)
    # print("RebPS[]={}".format(rebpss))
    # print("science rebs={}".format(srebs))
    # print("corner rebs={}".format(crebs))

    # print out info for each RebPS
    for rebps in rebpss:
        dstr = getattr(rebpower, rebps)().dump()
        # print(dstr)

    # initialization
    state = rebpower.getState()
    rebdict = init_rebdict(state)

    # initial pass through
    # main loop
    ondelay = 30.0
    seqdelay = 5.0
    update_rebdict(state, rebdict)
    for reb in sorted(rebdict):
        if not rebdict[reb]["state"] and rebdict[reb]["enable"]:
            print("{} is OFF and enabled -- powering on".format(reb))
            getattr(rebpower, reb)().powerRebOn()
            time.sleep(ondelay)
            getattr(rebpower, reb)().powerRebOff()
            time.sleep(seqdelay)
        else:
            print("{} is ON or NOT enabled".format(reb))

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
    print(t0str)
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    exit

