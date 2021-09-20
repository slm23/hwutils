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
maxstep = 60
initial_stepsize = 15

# functions

def get_hvbias_config(ch):
    hvconf = int(rebpower.getConfigurationParameterValue(ch, "hvBias"))
    if hvconf < 0 or hvconf > config_max:
        print("hvconf:{} out of allowed range: 0--{}".format(hvconf, config_max))
        hvconf = 0
    return hvconf


def get_hvbias_volts(ch):
    volts = float(rebpower.readChannelValue("".join([ch, "/hvbias/VbefSwch"])))
    # volts = float(rebpower.readChannelValue("".join([ch, "/hvbias/VbefSwch"])))
    if volts < 0 or volts > volts_max:
        print("hvbias value:{} out of allowed range: 0--{}".format(volts, volts_max))
    return volts


def get_hvbias_current(ch):
    current_max = float(rebpower.readChannelValue("".join([ch, "/hvbias/IbefSwch"])))
    # current_max = float(rebpower.readChannelValue("".join([ch, "/hvbias/IbefSwch"])))
    if current_max < 0 or current_max > current_maxmax:
        print("hvbias current:{} out of allowed range: 0--{}".format(current_max, current_maxmax))
    return current_max

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
        hvbiasdict[reb]["last_volts"] = 0.0
        hvbiasdict[reb]["current"] = 0.0
        hvbiasdict[reb]["dac"] = 0
        hvbiasdict[reb]["last_dac"] = 0
        hvbiasdict[reb]["delta_dac"] = 0
        hvbiasdict[reb]["delta_volts"] = 0.0
        hvbiasdict[reb]["volts_per_step"] = 0.04
        # hvbiasdict[reb][""] = ""
    return hvbiasdict

def update_hvbiasdict(state, hvbiasdict):
    """
    """
    for reb in sorted(srebs + crebs):
        reb_state = str(state.getComponentStateBundle(reb))
        # print("reb_state = {}".format(reb_state))
        if re.search(r"RebPowerState:ON", reb_state):
            hvbiasdict[reb]["state"] = True
            # print("{} is ON".format(reb))
        else:
            hvbiasdict[reb]["state"] = False
            # print("{} is OFF".format(reb))
        hvbiasdict[reb]["setpt"] = get_hvbias_setpt(reb)
        hvbiasdict[reb]["enable"] = hv_enable  # retrieve as config later
        hvbiasdict[reb]["config"] = get_hvbias_config(reb)
        hvbiasdict[reb]["last_volts"] = hvbiasdict[reb]["volts"]
        hvbiasdict[reb]["volts"] = get_hvbias_volts(reb)
        hvbiasdict[reb]["current"] = get_hvbias_current(reb)
        hvbiasdict[reb]["last_dac"] = hvbiasdict[reb]["dac"]
        hvbiasdict[reb]["dac"] = get_hvbias_dac(reb)
        hvbiasdict[reb]["delta_dac"] = 0
        hvbiasdict[reb]["delta_volts"] = 0.0
        if hvbiasdict[reb]["last_dac"] != 0 and int(hvbiasdict[reb]["dac"] - hvbiasdict[reb]["last_dac"]) != 0:
            old = hvbiasdict[reb]["volts_per_step"]
            new = (hvbiasdict[reb]["volts"] - 
                    hvbiasdict[reb]["last_volts"]) / (hvbiasdict[reb]["dac"] - hvbiasdict[reb]["last_dac"])
            if new < 0.025:
                new = 0.025
            hvbiasdict[reb]["volts_per_step"] = (2.0 * old + new) / 3.0
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

def get_hvbias_dac_steps(setpt, volts, volts_per_step):
    #
    steps = (setpt - volts) / volts_per_step
    #steps = int(steps * (abs(volts / setpt)))  # scaling to limit large jumps
    local_max = int(maxstep / (volts_per_step / 0.04))
    steps = int(steps)
    if steps > local_max:
        steps = local_max
    if steps < -local_max:
        steps = -local_max
    return steps


if __name__ == "__main__":
    #
    hvCsetpt = 30.0
    hvSsetpt = 50.0
    volts_max = 52.0
    config_max = 3200
    current_maxmax = 0.150
    hvbias_dac_min = 1100
    hv_enable = True
    if rebpower is None:
        print("missing rebpower subsystem, exiting...")
        exit(-1)

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
    hvbiasdict = init_hvbiasdict(state)

    # initial pass through
    # main loop
    small_delay = 0.05
    sleep_extra = False
    limit_steps = 0
    while True:
        t0 = time.time()
        max_delta = 0.0
        changes = 0
        state = rebpower.getState()
        update_hvbiasdict(state, hvbiasdict)
        for reb in sorted(hvbiasdict):
            if hvbiasdict[reb]["state"] and hvbiasdict[reb]["enable"]:
                # print("{} is ON and enabled -- first pass".format(reb))
                volts = hvbiasdict[reb]["volts"]
                setpt = hvbiasdict[reb]["setpt"]
                delta = setpt - volts
                if abs(delta) > max_delta:
                    max_delta = abs(delta)
                if hvbiasdict[reb]["config"] != hvbiasdict[reb]["dac"]:
                    print("{}:ERROR hvbias config:{} != dac:{}, skipping {}".format(
                        reb, hvbiasdict[reb]["config"], hvbiasdict[reb]["dac"], reb))
                    continue
                if hvbiasdict[reb]["dac"] < hvbias_dac_min:
                    print("{}: Configure dac to min={}".format(reb, hvbias_dac_min))
                    getattr( rebpower, reb)().submitChange("hvBias", hvbias_dac_min)
                    sleep_extra = True
                    changes += 1
                else:
                    volts_per_step = hvbiasdict[reb]["volts_per_step"]
                    hvbiasdict[reb]["delta_dac"] = steps = get_hvbias_dac_steps(setpt, volts, volts_per_step)
                    if steps != 0:
                        new_dac = hvbiasdict[reb]["dac"] + steps
                        if new_dac < hvbias_dac_min + maxstep:
                            steps = initial_stepsize
                            new_dac = hvbiasdict[reb]["dac"] + steps
                        print("{}: hvBias {:>4d}->{:>4d} steps={:>3d} for delta={:>7.3} volts/step={:>5.3f} volts={:>6.3f}".format(
                            reb, hvbiasdict[reb]["dac"], new_dac, steps, delta, volts_per_step, hvbiasdict[reb]["volts"]))
                        getattr( rebpower, reb)().submitChange("hvBias", new_dac)
                        changes += 1
            else:
                print("{} is NOT ON or is NOT enabled".format(reb))
                pass

            time.sleep(small_delay)
        if changes:
            rebpower.applySubmittedChanges()

        t1 = time.time()
        delta_time = t1 - t0
        # want delay ~ 10s if taking some large jumps, ~60s if taking all small jumps
        # delay = 600.0  / (8 + 3*math.sqrt(max_delta)) - delta_time
        # if delay < 15.0:
        #     delay = 15.0
        delay = 30.0
        print("{} updates, max_delta = {} cadence = {:>5.2f}s".format(changes, max_delta, delay + delta_time))
        time.sleep(delay)
        if sleep_extra:
            time.sleep(30.0)
            sleep_extra = False

    exit

