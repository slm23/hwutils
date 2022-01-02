#!/usr/bin/env ccs-script
from org.lsst.ccs.scripting import CCS
from ccs import proxies
import sys
import math
import re
import time

# globals
try:
    refrig = CCS.attachProxy("refrig")
    hexsub = CCS.attachProxy("hex")
except:
    refrig = None
    hexsub = None

channels = ['Cold1', 'Cold2']
readonly = dict()
readonly['Cold1'] = True
readonly['Cold2'] = True
setpt = dict()
setpt['Cold1'] = 18.0
setpt['Cold2'] = 20.0
delay = 120      # seconds between cycles
min_delay = 60
min_delta = 0.3  # trigger pressure delta from set point for a change (~2X noise)
step = 1.0       # step size per change

eepr_min = 25.0
eepr_max = 80.0


def get_eepr_valve_posn(ch):
    eepr_posn = float(getattr(refrig, "".join([ch, "/EEPRValvePosn"]))().getValue())
    if eepr_posn < eepr_min or eepr_posn > eepr_max:
        print("WARNING: eepr_posn value:{} out of allowed range: {:2d}--{:2d}".format(eepr_posn, eepr_min, eepr_max))
    return eepr_posn


def set_eepr_valve_posn(ch, posn):
    if posn < eepr_min or posn > eepr_max:
        print("requested eepr_posn:{:5.2f} out of allowed range: {:2d}--{:2d}, skipping...".format(posn, eepr_min, eepr_max))
        return -1
    getattr(refrig, ch)().setValvePosition('EEPR', posn / 100.0)


def get_return_prs(ch):
    return float(getattr(hexsub, "".join([ch, "/ReturnPrs"]))().getValue())


def init_cold_ctrl():
    """
    """
    cold_ctrl = dict()  # will hold current data for REBs
    #
    for ch in channels:
        cold_ctrl[ch] = dict()
        cold_ctrl[ch]['setpt'] = setpt[ch]
        cold_ctrl[ch]['return_prs0'] = get_return_prs(ch)
        cold_ctrl[ch]['return_prs1'] = cold_ctrl[ch]['return_prs0']
        cold_ctrl[ch]['return_prs2'] = cold_ctrl[ch]['return_prs0']
        cold_ctrl[ch]['eepr_posn'] = get_eepr_valve_posn(ch)  # 0-100
        cold_ctrl[ch]['eepr_last'] = cold_ctrl[ch]['eepr_posn']
        cold_ctrl[ch]['readonly'] = readonly[ch]
    return cold_ctrl


if __name__ == "__main__":
    #
    if refrig is None:
        print("missing refrig subsystem, exiting...")
        exit(-1)
    if hexsub is None:
        print("missing hex subsystem, exiting...")
        exit(-1)
    t0 = time.time()
    cold_ctrl = init_cold_ctrl()

    # startup print out info for each channel
    for ch in channels:
        print("{} ".format(time.strftime("%Y-%m-%dT%H:%M:%S %Z",time.localtime(t0)))),
        print("{}: ReturnPrs = {:5.2f}  EEPRValvePosn = {:2d}".format(
            ch, cold_ctrl[ch]['return_prs0'], int(round(cold_ctrl[ch]['eepr_posn']))))

    # main loop
    while True:
        t0 = time.time()
        changes = 0
        for ch in channels:
            cold_ctrl[ch]['return_prs2'] = cold_ctrl[ch]['return_prs1']
            cold_ctrl[ch]['return_prs1'] = cold_ctrl[ch]['return_prs0']
            cold_ctrl[ch]['return_prs0'] = get_return_prs(ch)
            cold_ctrl[ch]['eepr_last'] = cold_ctrl[ch]['eepr_posn']
            cold_ctrl[ch]['eepr_posn'] = get_eepr_valve_posn(ch)
            if cold_ctrl[ch]['eepr_posn'] != cold_ctrl[ch]['eepr_last']:
                cold_ctrl[ch]['readonly'] = True
                print("WARNING: EEPR setting changed since last time, assuming operator override, setting to READONLY")

            # average the last 3 readings
            return_prs = (cold_ctrl[ch]['return_prs0'] +
                            cold_ctrl[ch]['return_prs1'] +
                            cold_ctrl[ch]['return_prs2']) / 3.0

            # if pressure is higher than set point, open the valve (positive)
            # if pressure is lower than set point, close the valve (negative)
            delta_prs = return_prs - cold_ctrl[ch]['setpt']
            eepr_posn = eepr_new = cold_ctrl[ch]['eepr_posn']
            if delta_prs > min_delta:
                eepr_new = int(round(eepr_posn + 1.0))
            elif delta_prs < -min_delta:
                eepr_new = int(round(eepr_posn - 1.0))

            if eepr_new != eepr_posn:
                print("{} EEPR: {:2d} --> {:2d}".format(ch, int(round(eepr_posn), int(round(eepr_new))),
                if not cold_ctrl[ch]['readonly']:
                    print("")
                    set_eepr_valve_posn(ch, eepr_new)
                else:
                    print(" (readonly, nochange)")
                changes += 1
                cold_ctrl[ch]['eepr_posn'] = eepr_new

        #
        t1 = time.time()
        delta_time = t1 - t0
        print("loop_time={:5.2f} change_count={:1d} at {}".format(
                delta_time, changes, time.strftime("%Y-%m-%dT%H:%M:%S %Z",time.localtime(t1))))
        if delay > delta_time:
            time.sleep(delay - delta_time)
        else:
            time.sleep(min_delay)

    exit

