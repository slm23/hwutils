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

readonly = True
channels = ['Cold1', 'Cold2']
setpt['Cold1'] = 18.0
setpt['Cold2'] = 20.0
delay = 120      # seconds between cycles
min_delay = 60
min_delta = 0.4  # trigger pressure delta from set point for a change (~2X noise)
step = 1.0       # step size per change
period = 30      # loop period time

eepr_min = 30.0
eepr_max = 70.0


def get_eepr_valve_posn(ch):
    eepr_posn = float(refrig.readChannelValue("/".join(["", ch, "EEPRValvePosn"])))
    if eepr_posn < eepr_min or eepr_posn > eepr_max:
        print("eepr_posn value:{} out of allowed range: {}--{}".format(eepr_posn, eepr_min, eepr_max))
    return eepr_posn


def set_eepr_valve_posn(ch, posn):
    if posn < eepr_min or posn > eepr_max:
        print("requested eepr_posn:{} out of allowed range: {}--{}, skipping".format(posn, eepr_min, eepr_max))
        return -1
    if readonly:
        print("getattr(refrig, {})().setValvePosition({}, {})".format(ch, 'EEPR', eepr_new / 100.0))
    else:
        getattr(refrig, ch)().setValvePosition('EEPR', posn / 100.0)


def get_return_prs(ch):
    # return_prs = float(hex.readChannelValue("/".join(["", ch, "ReturnPrs"])))
    return_prs = float(getattr(refrig, "/".join(["", ch, "ReturnPrs"]))().getValue())
    return return_prs


def init_control_dict():
    """
    """
    cold_ctrl = dict()  # will hold current data for REBs
    #
    cold_ctrl['Cold1']['setpt'] = cold1_setpt
    cold_ctrl['Cold1']['return_prs0'] = get_return_prs(channels[0])
    cold_ctrl['Cold1']['return_prs1'] = cold_ctrl['Cold1']['return_prs0']
    cold_ctrl['Cold1']['return_prs2'] = cold_ctrl['Cold1']['return_prs0']
    cold_ctrl['Cold1']['eepr_posn'] = get_eepr_valve_posn(channels[0])  # 0-100
    cold_ctrl['Cold1']['eepr_last'] = -1.0
    #
    cold_ctrl['Cold2']['setpt'] = cold2_setpt
    cold_ctrl['Cold2']['return_prs0'] = get_return_prs(channels[1])
    cold_ctrl['Cold2']['return_prs1'] = cold_ctrl['Cold2']['return_prs0']
    cold_ctrl['Cold2']['return_prs2'] = cold_ctrl['Cold2']['return_prs0']
    cold_ctrl['Cold2']['eepr_posn'] = get_eepr_valve_posn(channels[1])  # 0-100
    cold_ctrl['Cold2']['eepr_last'] = -1.0
    return control_dict


if __name__ == "__main__":
    #
    if refrig is None:
        print("missing refrig subsystem, exiting...")
        exit(-1)
    if hexsub is None:
        print("missing hex subsystem, exiting...")
        exit(-1)
    t0 = time.time()
    control_dict = init_control_dict()

    # startup print out info for each channel
    for ch in channels:
        print("".format(time.strftime("%Y-%m-%dT%H:%M:%S %Z",time.localtime(t0))))
        print("{}: ReturnPrs = {}  EEPRValvePosn = {}".format(
            ch, control_dict[ch]['return_prs'], control_dict[ch]['eepr_posn']))

    # main loop
    while True:
        t0 = time.time()
        max_delta = 0.0
        changes = 0
        for ch in channels:
            cold_ctrl[ch]['return_prs2'] = cold_ctrl[ch]['return_prs1']
            cold_ctrl[ch]['return_prs1'] = cold_ctrl[ch]['return_prs0']
            cold_ctrl[ch]['return_prs0'] = get_return_prs(ch)
            cold_ctrl[ch]['eepr_last'] = cold_ctrl[ch]['eepr_posn']
            cold_ctrl[ch]['eepr_posn'] = get_eepr_valve_posn(ch)
            if cold_ctrl[ch]['eepr_posn'] != cold_ctrl[ch]['eepr_last']:
                readonly = True

            # average the last 3 readings
            return_prs = (cold_ctrl[ch]['return_prs0'] +
                            cold_ctrl[ch]['return_prs1'] +
                            cold_ctrl[ch]['return_prs2']) / 3.0

            # if pressure is higher than set point, open the valve (positive)
            # if pressure is lower than set point, close the valve (negative)
            delta_prs = return_prs - cold_ctrl[ch]['setpt']
            eepr_pos = eepr_new = cold_ctrl[ch]['eepr_posn']
            if delta_prs > min_delta:
                eepr_new = int(round(eepr_posn + 1.0))
            elif delta_prs < -min_delta:
                eepr_new = int(round(eepr_posn - 1.0))

            if eepr_new != eepr_pos:
                print("{}".format(getattr(refrig, ch).().getValveNames()))
                set_eepr_valve_posn(ch, eepr_new):
                changes += 1

        #
        t1 = time.time()
        delta_time = t1 - t0
        print("loop_time={} change_count={} at {}".format(
                delta_time, changes, time.strftime("%Y-%m-%dT%H:%M:%S %Z",time.localtime(t1))))
        if delay > delta_time
            time.sleep(delay - delta_time)
        else:
            time.sleep(min_delay)

    exit

