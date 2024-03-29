#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from ccs import proxies
import sys
import math
import re
import time

# globals
try:
    rebpower = CCS.attachProxy("rebpower")
except:
    rebpower = None
srebs = []
crebs = []
rebpss = []
maxstep = int(25)
initial_stepsize = int(15)
volts_per_step0 = 0.125

# exceptional rebs (special setpoint)
erebd = dict()
erebd["R01/Reb0"] = 30.0
# regular rebs
sreb_regex = r"R../Reb[012]"
creb_regex = r"R../Reb[GW]"
# enabled rebs
enabled_rebs = re.compile(r"R(43|33)/Reb[012]")
# disabled rebs
disabled_rebs = r"R[^2][^2]/Reb."

# functions


def get_hvbias_config(ch):
    hvconf = int(rebpower.getConfigurationParameterValue(str(ch), "hvBias"))
    if hvconf < 0 or hvconf > config_max:
        print("hvconf:{} out of allowed range: 0--{}".format(hvconf, config_max))
        hvconf = 0
    return hvconf


def get_hvbias_volts(ch):
    volts = float(rebpower.readChannelValue("".join([ch, "/hvbias/VbefSwch"])))
    if volts < 0 or volts > volts_max:
        print("hvbias value:{} out of allowed range: 0--{}".format(volts, volts_max))
    return volts


def get_hvbias_current(ch):
    current_max = float(rebpower.readChannelValue("".join([ch, "/hvbias/IbefSwch"])))
    if current_max < 0 or current_max > current_maxmax:
        print(
            "hvbias current:{} out of allowed range: 0--{}".format(
                current_max, current_maxmax
            )
        )
    return current_max


def get_hvbias_dac(ch):
    hvbias_dac = int(hvbiasdict[ch]["target"].readHvBiasDac())
    return hvbias_dac


def init_hvbiasdict(state):
    """ """
    hvbiasdict = dict()  # will hold current data for REBs
    for reb in sorted(srebs + crebs):
        hvbiasdict[reb] = dict()
        hvbiasdict[reb]["target"] = getattr(rebpower, reb)()
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
        hvbiasdict[reb]["volts_per_step"] = volts_per_step0
        # hvbiasdict[reb][""] = ""
    return hvbiasdict


def update_hvbiasdict(state, hvbiasdict):
    """ """
    for reb in sorted(hvbiasdict):
        reb_state = str(state.getComponentStateBundle(reb))
        if re.search(r"RebPowerState:ON", reb_state):
            hvbiasdict[reb]["state"] = True
        else:
            hvbiasdict[reb]["state"] = False
        if enabled_rebs.match(reb):
            hvbiasdict[reb]["enable"] = True
        else:
            next
        hvbiasdict[reb]["setpt"] = get_hvbias_setpt(reb)
        hvbiasdict[reb]["config"] = int(
            rebpower.getConfigurationParameterValue(reb, "hvBias")
        )
        hvbiasdict[reb]["last_volts"] = hvbiasdict[reb]["volts"]
        hvbiasdict[reb]["volts"] = float(
            rebpower.readChannelValue("".join([reb, "/hvbias/VbefSwch"]))
        )
        hvbiasdict[reb]["current"] = float(
            rebpower.readChannelValue("".join([reb, "/hvbias/IbefSwch"]))
        )
        hvbiasdict[reb]["last_dac"] = int(hvbiasdict[reb]["dac"])
        hvbiasdict[reb]["dac"] = int(hvbiasdict[reb]["target"].readHvBiasDac())
        hvbiasdict[reb]["delta_dac"] = 0
        hvbiasdict[reb]["delta_volts"] = 0.0
        if (
            hvbiasdict[reb]["last_dac"] != 0
            and (hvbiasdict[reb]["dac"] - hvbiasdict[reb]["last_dac"]) != 0
        ):
            old = hvbiasdict[reb]["volts_per_step"]
            new = (hvbiasdict[reb]["volts"] - hvbiasdict[reb]["last_volts"]) / (
                hvbiasdict[reb]["dac"] - hvbiasdict[reb]["last_dac"]
            )
            if new < 0.025:
                new = 0.025
            hvbiasdict[reb]["volts_per_step"] = (2.0 * old + new) / 3.0
        # hvbiasdict[reb][""] = ""


def init_components(state):
    for component in state.componentsWithStates.iterator():
        # print("component={}".format(component))
        if re.match(r"RebPS/P..", component):
            rebpss.append(component)
        # if re.match(r"R../Reb[012]", component):
        if re.match(sreb_regex, component):
            srebs.append(component)
        if re.match(creb_regex, component):
            crebs.append(component)


def get_hvbias_setpt(reb):
    if reb in erebd:  # excceptions need to go first here
        return erebd[reb]
    elif reb in srebs:
        return hvSsetpt
    elif reb in crebs:
        return hvCsetpt
    else:
        # this should be an error
        return 0.0


def get_hvbias_dac_steps(setpt, volts, volts_per_step):
    #
    local_max = int(maxstep / (volts_per_step / 0.04))
    steps = int(round((setpt - volts) / volts_per_step))
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
    std_delay = 20
    min_delay = 10
    limit_steps = 0
    allrebs = sorted(hvbiasdict)
    while True:
        t0 = time.time()
        max_delta = 0.0
        changes = 0
        state = rebpower.getState()
        update_hvbiasdict(state, hvbiasdict)
        for reb in allrebs:
            if hvbiasdict[reb]["state"] and hvbiasdict[reb]["enable"]:
                # print("{} is ON and enabled".format(reb))
                volts = hvbiasdict[reb]["volts"]
                setpt = hvbiasdict[reb]["setpt"]
                delta = setpt - volts
                if abs(delta) > max_delta:
                    max_delta = abs(delta)
                if hvbiasdict[reb]["config"] != hvbiasdict[reb]["dac"]:
                    print(
                        "{}:ERROR hvbias config:{} != dac:{}, skipping {}".format(
                            reb, hvbiasdict[reb]["config"], hvbiasdict[reb]["dac"], reb
                        )
                    )
                    continue
                if hvbiasdict[reb]["dac"] < hvbias_dac_min:
                    print("{}: Configure dac to min={}".format(reb, hvbias_dac_min))
                    hvbiasdict[reb]["target"].submitChange("hvBias", hvbias_dac_min)
                    changes += 1
                else:
                    volts_per_step = hvbiasdict[reb]["volts_per_step"]
                    hvbiasdict[reb]["delta_dac"] = steps = get_hvbias_dac_steps(
                        setpt, volts, volts_per_step
                    )
                    if steps != 0:
                        # print("get_hvbias_dac_steps({}, {}, {}) returned {}".format(setpt, volts, volts_per_step, steps))
                        new_dac = hvbiasdict[reb]["dac"] + steps
                        if new_dac < hvbias_dac_min + maxstep:
                            steps = initial_stepsize
                            new_dac = hvbiasdict[reb]["dac"] + steps
                        print(
                            "{}: hvBias {:>4d}->{:>4d} steps={:>3d} for delta={:>7.3} volts/step={:>5.3f} volts={:>6.3f}".format(
                                reb,
                                hvbiasdict[reb]["dac"],
                                new_dac,
                                steps,
                                delta,
                                volts_per_step,
                                hvbiasdict[reb]["volts"],
                            )
                        )
                        hvbiasdict[reb]["target"].submitChange("hvBias", new_dac)
                        changes += 1
            else:
                # print("{} is NOT ON or is NOT enabled".format(reb))
                pass

            time.sleep(small_delay)
        #
        t1 = time.time()
        delta_time = t1 - t0
        if changes:
            rebpower.applySubmittedChanges()
            print(
                "loop_time={} change_count={} at {}".format(
                    delta_time,
                    changes,
                    time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t1)),
                )
            )
        if std_delay > delta_time + min_delay:
            time.sleep(std_delay - delta_time)
        else:
            time.sleep(min_delay)

    exit
