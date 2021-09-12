#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from ccs import proxies
import sys
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

def get_hvbias_config(ch):
    hvconf = int(rebpower.getConfigurationParameterValue(ch, "hvBias"))
    if hvconf < 0 or hvconf > hvconfmax:
        print("hvconf:{} out of allowed range: 0--{}".format(hvconf, hvconfmax))
        hvconf = 0
    return hvconf


def get_hvbias_volts(ch):
    hvval = float(rebpower.readChannelValue("".join([ch, "/hvbias/VbefSwch"])))
    if hvval < 0 or hvval > hvvalmax:
        print("hvbias value:{} out of allowed range: 0--{}".format(hvconf, hvvalmax))
    return hvval


def get_hvbias_current(ch):
    hvcurr = float(rebpower.readChannelValue("".join([ch, "/hvbias/IbefSwch"])))
    if hvcurr < 0 or hvcurr > hvcurrmax:
        print("hvbias current:{} out of allowed range: 0--{}".format(hvcurr, hvcurrmax))
    return hvcurr

def get_hvbias_dac(ch):
    hvbias_dac = int(getattr(rebpower, ch)().readHvBiasDac())
    return hvbias_dac

def init_hvbiasdict(state):
    """
    """
    hvbiasdict = dict()  # will hold current data for REBs
    for reb in sorted(srebs + crebs):
        hvbiasdict[reb] = dict()
        hvbiasdict[reb]["state"] = False
        hvbiasdict[reb]["setpt"] = 0.0
        hvbiasdict[reb]["enable"] = False
        hvbiasdict[reb]["config"] = 0
        hvbiasdict[reb]["volts"] = 0.0
        hvbiasdict[reb]["current"] = 0.0
        hvbiasdict[reb]["dac"] = 0
        hvbiasdict[reb]["delta_dac"] = 0
        hvbiasdict[reb]["delta_volts"] = 0.0
        # hvbiasdict[reb][""] = ""
    return hvbiasdict

def update_hvbiasdict(state, hvbiasdict):
    """
    """
    for reb in sorted(srebs + crebs):
        reb_state = str(state.getComponentStateBundle(reb))
        print("reb_state = {}".format(reb_state))
        if re.search(r"RebPowerState:ON", reb_state):
            hvbiasdict[reb]["state"] = True
            print("{} is ON".format(reb))
        else:
            hvbiasdict[reb]["state"] = False
            print("{} is OFF".format(reb))
        hvbiasdict[reb]["setpt"] = get_hvbias_setpt(reb)
        hvbiasdict[reb]["enable"] = hv_enable  # retrieve as config later
        hvbiasdict[reb]["config"] = get_hvbias_config(reb)
        hvbiasdict[reb]["volts"] = get_hvbias_volts(reb)
        hvbiasdict[reb]["current"] = get_hvbias_current(reb)
        hvbiasdict[reb]["dac"] = get_hvbias_dac(reb)
        hvbiasdict[reb]["delta_dac"] = 0
        hvbiasdict[reb]["delta_volts"] = 0.0
        # hvbiasdict[reb][""] = ""

def init_components(state):
    for component in state.componentsWithStates.iterator():
        if re.match(r"RebPS/P..", component):
            rebpss.append(str(component))
        if re.match(r"R../Reb[012]", component):
            srebs.append(str(component))
        if re.match(r"R../Reb[GW]", component):
            crebs.append(str(component))

def get_hvbias_setpt(reb):
    if reb in srebs:
        return hvSsetpt
    elif reb in crebs:
        return hvCsetpt
    else:
        # this should be an error
        return 0.0

def get_hvbias_dac_steps(delta):
        maxstep = bigstep if abs(delta) > 2.0 else smallstep
        steps = int(delta / 0.05)
        if steps > maxstep:
            steps = maxstep
        if steps < -maxstep:
            steps = -maxstep
        return steps


if __name__ == "__main__":
    #
    hvCsetpt = 30.0
    hvSsetpt = 30.0
    hvvalmax = 52.0
    hvconfmax = 3200
    hvcurrmax = 0.150
    hvbias_dac_min = 1200
    dacStart = 1200
    bigstep = 40
    smallstep = 5
    hv_enable = True
    if rebpower is None:
        print("missing rebpower subsystem, exiting...")
        exit(-1)
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    state = rebpower.getState()
    print(state)
    init_components(state)
    print("RebPS[]={}".format(rebpss))
    print("science rebs={}".format(srebs))
    print("corner rebs={}".format(crebs))

    # print out info for each RebPS
    for rebps in rebpss:
        dstr = getattr(rebpower, rebps)().dump()
        print(dstr)

    # initialization
    state = rebpower.getState()
    hvbiasdict = init_hvbiasdict(state)

    # initial pass through
    update_hvbiasdict(state, hvbiasdict)
    for reb in sorted(hvbiasdict):
        if hvbiasdict[reb]["state"] and hvbiasdict[reb]["enable"]:
            print("{} is ON and enabled -- first pass".format(reb))
            delta = hvbiasdict[reb]["delta_volts"] = (
                hvbiasdict[reb]["setpt"] - hvbiasdict[reb]["volts"]
            )
            if hvbiasdict[reb]["config"] != hvbiasdict[reb]["dac"]:
                print("{}:hvbias config:{} != dac:{}, skipping {}".format(
                    reb, hvbiasdict[reb]["config"], hvbiasdict[reb]["dac"], reb))
                continue
            if hvbiasdict[reb]["dac"] < hvbias_dac_min:
                print("{}: Configure hvbias dac to min={}", reb, hvbias_dac_min)
                getattr( rebpower, reb)().submitChange("hvBias", hvbias_dac_min)
            else:
                hvbiasdict[reb]["delta_dac"] = steps = get_hvbias_dac_steps(delta)
                new_dac = hvbiasdict[reb]["dac"] + steps
                print("{}: Configure hvbias dac to hvBias={}".format(reb, new_dac))
                getattr( rebpower, reb)().submitChange("hvBias", new_dac)
        else:
            print("{} is NOT ON or is NOT enabled".format(reb))
    rebpower.applySubmittedChanges()
    time.sleep(1)

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
    print(t0str)
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    exit

