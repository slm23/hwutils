#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from ccs import proxies
import sys
import re
import time

# globals
try:
    rebpower = CCS.attachProxy("ts7-rebpower")  #### CHANGE
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

def init_hvbiasdict():
    """
    """
    hvbiasdict = dict()  # will hold current data for REBs
    hvbiasdict = update_hvbiasdict(hvbiasdict)
    return hvbiasdict

def update_hvbiasdict(hvbiasdict):
    """
    """
    for reb in sorted(srebs + crebs):
        reb_state = str(state.getComponentStateBundle(reb))
        if re.match(r"RebPowerState:ON", reb_state):
            hvbiasdict[reb]["state"] = True
        else:
            hvbiasdict[reb]["state"] = False
        hvbiasdict[reb]["setpt"] = get_hvbias_setpt(reb):
        hvbiasdict[reb]["enable"] = hv_enable  # config later
        hvbiasdict[reb]["config"] = get_hvbias_config(reb)
        hvbiasdict[reb]["volts"] = get_hvbias_volts(reb)
        hvbiasdict[reb]["current"] = get_hvbias_current(reb)
        hvbiasdict[reb]["dac"] = get_hvbias_dac(reb):
        hvbiasdict[reb]["delta_dac"] = 0
        hvbiasdict[reb]["delta_volts"] = 0.0
        # hvbiasdict[reb][""] = ""

def init_components():
    state = rebpower.getState()
    print(state)
    for component in state.componentsWithStates.iterator():
        if re.match(r"RebPS/P..", component):
            rebpss.append(str(component))
        if re.match(r"R../Reb[012]", component):
            srebs.append(str(component))
        if re.match(r"R../Reb[GW]", component):
            crebs.append(str(component))

def get_hvbias_setpt(reb):
    if reb in srebs:
        hvbiasdict[reb]["setpt"] = hvSsetpt  # change these to configs later
    elif reb in crebs:
        hvbiasdict[reb]["setpt"] = hvCsetpt
    else:
        # this should be an error
        hvbiasdict[reb]["setpt"] = 0.0

def get_hvbias_dac_steps(delta):
        maxstep = bigstep if abs(delta) > 2.0 else smallstep
        steps = int(delta / 0.05)
        if steps == 0:
            continue
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
    hvbias_dac_min = 1000
    dacStart = 1200
    bigstep = 20
    smallstep = 5
    hv_enable = True
    if rebpower is None:
        print("missing rebpower subsystem, exiting...")
        exit(-1)
    t0 = time.time()
    t0str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))

    init_components():
    print("RebPS[]={}".format(rebpss))
    print("science rebs={}".format(srebs))
    print("corner rebs={}".format(crebs))

    # print out info for each RebPS
    for rebps in rebpss:
        dstr = getattr(rebpower, rebps)().dump()
        print(dstr)

    # initialization
    hvbiasdict = init_hvbiasdict()

    # initial pass through
    update_hvbiasdict(hvbiasdict)
    for reb in sorted(hvbiasdict):
        if hvbiasdict[reb]["state"] and hvbiasdict[reb]["enable"]:
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
                getattr( rebpower, reb)().submitChange("hvBias", new_dac)
    rebpower.applySubmittedChanges()
    time.sleep(60)

    t1 = time.time()
    t1str = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
    print(t0str)
    print(t1str)
    print("elapsed time: {}".format(t1 - t0))

    exit


#    # bays = list([ "R43"])    ### CHANGE
#    setpoint = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
#    rebps = ""
#    hvmax = 57.0
#    hvStateOn = True
#    # channels = list(product(bays, rebs))
#    # channels = [ "%s/Reb%d"%achannel for achannel in channels  ]
#    channels = ["R43/Reb0", "R43/Reb1", "R43/Reb2", "R33/Reb0", "R33/Reb1", "R33/Reb2"]
#    filename = "/tmp/{}_hvbias_drive.log".format(
#        rebps, time.strftime("%Y%m%d%H%M", time.gmtime(time.time()))
#    )
#    fp = open(filename, "w")

#    bigstep = 20
#    smallstep = 5
#    maxdac = 3200
#    dacStart = 1200

#    # put RebPS info into the output and the file
#    dumpstr = dump()
#    print (dumpstr)
#    fp.write("{}\n".format(dumpstr))

#    # initialize
#    # rebpower.change("periodicTasks/monitor-publish/RebPS/{}".format(rebps), "taskPeriodMillis", "1000")
#    dosleep = False
#    for idx, achannel in enumerate(channels):
#        if int(getDAC(achannel)) < 1000:
#            changeDAC(achannel, "1000")
#            dosleep = True
#    if dosleep:
#        time.sleep(60)

#    if hvStateOn:
#        for achannel in channels:
#            hvBiasOn(achannel)
#            time.sleep(1)
#    else:
#        for achannel in channels:
#            hvBiasOff(achannel)
#        time.sleep(1)

#    hvarr = []
#    ival = []
#    dac0 = []
#    for idx, achannel in enumerate(channels):
#        hvarr.append(float(getHV(achannel)))
#        ival.append(float(setpoint[idx]))
#        dac0.append(int(getDAC(achannel)))

#    for idx, achannel in enumerate(channels):
#        if dac0[idx] < dacStart:
#            changeDAC(achannel, dacStart)

#    while True:
#        print ".",
#        while any(
#            [hvv < hvi - 0.06 or hvv > hvi + 0.06 for hvv, hvi in zip(hvarr, ival)]
#        ):
#            print ""
#            for idx, achannel in enumerate(channels):
#                # adjust
#                hvarr[idx] = float(getHV(achannel))  # update value
#                if hvarr[idx] > hvmax:
#                    print (
#                        "exiting on error: hvBias:{} for channel:{} too high (>{})".format(
#                            hvarr[idx], achannel, hvmax
#                        )
#                    )
#                    exit(-1)
#                delta = float(ival[idx] - hvarr[idx])
#                steps = int(delta / 0.05)
#                maxstep = bigstep if abs(delta) > 2.0 else smallstep
#                if steps == 0:
#                    continue
#                if steps > maxstep:
#                    steps = maxstep
#                if steps < -maxstep:
#                    steps = -maxstep
#                dac = int(getDAC(achannel))
#                if dac + steps > maxdac:  # adjust the set point since can't reach it
#                    ival[idx] = hvarr[idx]
#                else:
#                    changeDAC(achannel, dac + steps)
#                t0 = time.time()
#                t1 = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(t0))
#                print (
#                    "{:13} ch:{}  dac:{:4} --> {:4}  hv:{:6.3f} delta:{:6.3f}  {}".format(
#                        t0, achannel, dac, dac + steps, hvarr[idx], delta, t1
#                    )
#                )
#                fp.write(
#                    "{:13} ch:{}  dac:{:4} --> {:4}  hv:{:6.3f} delta:{:6.3f}  {}".format(
#                        t0, achannel, dac, dac + steps, hvarr[idx], delta, t1
#                    )
#                )
#            time.sleep(10)

#        for idx, achannel in enumerate(channels):
#            hvarr[idx] = float(getHV(achannel))  # update value

#        time.sleep(30)

#    fp.close()

# def getHV(ch):
#    if rebpower is None:
#        return 49.80
#    return getattr(rebpower, "{}/hvbias/VbefSwch".format(ch))().getValue()


# def getHI(ch):
#    if rebpower is None:
#        return 0.000
#    return getattr(rebpower, "{}/hvbias/IbefSwch".format(ch))().getValue()


# def getDAC(ch):
#    if rebpower is None:
#        return 1000
#    return int(
#        getattr(rebpower, ch)().printComponentConfigurationParameters()["hvBias"]
#    )


# def changeDAC(ch, dac):
#    if rebpower is None:
#        return
#    getattr(rebpower, ch)().change("hvBias", "{}".format(int(dac)))


# def hvBiasOn(ch):
#    if rebpower is None:
#        return
#    getattr(rebpower, ch)().hvBiasOn()


# def hvBiasOff(ch):
#    if rebpower is None:
#        return
#    getattr(rebpower, ch)().hvBiasOff()

# def getState():
#    return rebpower.getState()


# def dump():
#    return getattr(rebpower, "RebPS/{}".format(rebps))().dump()
