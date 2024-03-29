#!/usr/bin/env python
"""
Issue commands to set up MKS 974B gauge
"""
import os
import sys
import serial

# import serial.rs485
import argparse
import textwrap
import time
import logging
import warnings
import re
import numpy as np
from astropy import stats
from astropy.utils.exceptions import AstropyWarning


def parse_args():
    """handle command line"""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
           Description goes here
                                    """
        ),
        epilog=textwrap.dedent(
            """\
                               """
        ),
    )
    parser.add_argument(
        "--port",
        nargs="?",
        default="/dev/ttyS0",
        const="/dev/ttyS0",
        help="serial port to open",
    )
    parser.add_argument(
        "--baudrate",
        nargs="?",
        type=int,
        default=9600,
        const=9600,
        help="4800, [9600], 19200, 38400, 57600, 115200, 230400",
    )
    parser.add_argument(
        "--id",
        nargs="?",
        type=int,
        default=1,
        const=1,
        help="RS485 id:{1..253}",
    )
    parser.add_argument(
        "--count",
        nargs="?",
        type=int,
        default=1,
        help="number of queries",
    )
    parser.add_argument(
        "--delay",
        nargs="?",
        type=float,
        default=1.0,
        const=1.0,
        help="delay between queries",
    )
    parser.add_argument(
        "--timeout",
        nargs="?",
        type=float,
        default=0.1,
        const=0.1,
        help="timeout for read()",
    )
    # commands
    parser.add_argument(
        "--setid",
        metavar="rs485id",
        help="set the RS485 id:{1..253} and exit",
    )
    parser.add_argument(
        "--setrelay",
        nargs="+",
        metavar="R# enable setpoint direction",
        action="append",
        help=f"set up relay R# in {1,2,3}, enable=ON|OFF, setpoint<500, direction=BELOW|ABOVE",
    )
    parser.add_argument(
        "--setusertag",
        nargs=1,
        metavar="usertag",
        help="set the gauge usertag",
    )
    parser.add_argument(
        "--ccenable",
        metavar="ccenable",
        help="set enable for CCAuto (ON|OFF)",
    )
    parser.add_argument(
        "--ccon",
        metavar="cconvalue",
        help="set the CCAuto ON set point (1e-4,5e-4)",
    )
    parser.add_argument(
        "--ccoff",
        metavar="ccoffvalue",
        help="set the CCAuto OFF set point (5e-4,8e-4)",
    )
    parser.add_argument(
        "--ccprotection",
        metavar="ccprotvalue",
        help="set the CC Protection set point (10,120) seconds",
    )
    parser.add_argument(
        "--ccsmoothing",
        metavar="ccsmoothval",
        help="set the CC/MP smoothing boundary (>1e-4)",
    )
    parser.add_argument(
        "--serialonly", action="store_true", help="print serial number and exit"
    )
    parser.add_argument(
        "--loopback", action="store_true", help="connection is RS485 half duplex"
    )
    parser.add_argument(
        "--noflush", action="store_true", help="no flush after write() call"
    )
    parser.add_argument(
        "--noreset", action="store_true", help="no reset after write() call"
    )
    parser.add_argument(
        "--debug", action="store_true", help="print additional debugging messages"
    )
    return parser.parse_args()


def init_logging(debug):
    """Set up debug and info level logging"""
    if debug:
        logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)
    else:
        logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
    # suppress plotting debug messages
    # mpl_logger = logging.getLogger("matplotlib")
    # mpl_logger.setLevel(logging.WARNING)


def init_warnings():
    """Block warnings from Astropy"""
    warnings.simplefilter("ignore", category=AstropyWarning)


def query_and_response(query, optlist, ser):
    """send command and return response"""
    dt0 = 0.0
    retries = 0
    max_retries = 5
    query_str = f"@{optlist.id:03d}{query}?;FF"
    query_bts = bytes(query_str, "utf-8")
    errcnt = 0
    result = None
    # nn = 0
    if optlist.debug:
        logging.debug(f"query_bts={query_bts}")

    while retries < max_retries:
        if not optlist.noreset:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        start_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)
        ser.write(query_bts)
        if not optlist.noflush:
            ser.flush()
        resp = ser.read_until(expected=b";FF", size=None)
        end_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)
        dt = (end_ns - start_ns) * 1e-9

        if optlist.loopback:  # RS485 query echo -> read again
            query_echo = resp
            query_dt = dt
            if re.match(f"@{optlist.id:03d}{query}\?;FF", resp.decode()):
                ser.timeout = float(optlist.timeout) - query_dt
                resp = ser.read_until(expected=b";FF", size=None)
                end_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)
                dt = (end_ns - start_ns) * 1e-9
                logging.debug(f"query echo={query_echo} dt={query_dt:>.3f}")
            else:
                logging.warning(f"echo failed: {query_echo} dt={query_dt:>.3f}")

        # check the reply is valid
        if re.match(r"@...ACK.*;FF", resp.decode()):
            dt = dt0 + dt
            result = re.match(r"@...ACK(.*);FF", resp.decode()).groups()[0]
            logging.debug(f"resp={resp} dt={dt:>.3f}")
            break
        elif retries < max_retries and dt >= ser.timeout:  # retry
            # print(f"{resp}")
            dt0 = dt
            retries += 1
        else:
            dt = dt0 + dt
            logging.warning(
                "failed at trial %d: query=%s  resp=%s, dt=%.3f",
                retries,
                query,
                resp,
                dt,
            )
            errcnt += 1
            break
    return result, dt, retries, errcnt


def cmd_and_response(cmd, optlist, ser):
    """send command and return response"""
    dt0 = 0.0
    retries = 0
    max_retries = 5
    cmd_str = f"@{optlist.id:03d}{cmd};FF"
    cmd_bts = bytes(cmd_str, "utf-8")
    errcnt = 0
    result = None
    if optlist.debug:
        logging.debug(f"cmd_bts={cmd_bts}")

    while retries < max_retries:
        if not optlist.noreset:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        start_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)
        ser.write(cmd_bts)
        if not optlist.noflush:
            ser.flush()
        resp = ser.read_until(expected=b";FF", size=None)
        end_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)
        dt = (end_ns - start_ns) * 1e-9

        if optlist.loopback:  # RS485 cmd echo -> read again
            cmd_echo = resp
            cmd_dt = dt
            if re.match(f"@{optlist.id:03d}{cmd};FF", resp.decode()):
                ser.timeout = float(optlist.timeout) - cmd_dt
                resp = ser.read_until(expected=b";FF", size=None)
                end_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)
                dt = (end_ns - start_ns) * 1e-9
                logging.debug(f"cmd echo={cmd_echo} dt={cmd_dt:>.3f}")
            else:
                logging.warning(f"echo failed: {cmd_echo} dt={cmd_dt:>.3f}")

        # check the reply is valid
        if re.match(r"@...ACK.*;FF", resp.decode()):
            dt = dt0 + dt
            result = re.match(r"@...ACK(.*);FF", resp.decode()).groups()[0]
            logging.debug(f"resp={resp} dt={dt:>.3f}")
            break
        elif retries < max_retries and dt >= ser.timeout:  # retry
            # print(f"{resp}")
            dt0 = dt
            retries += 1
        else:
            dt = dt0 + dt
            logging.warning(
                "failed at trial %d: cmd=%s  resp=%s, dt=%.3f",
                retries,
                cmd,
                resp,
                dt,
            )
            errcnt += 1
            break
    return result, dt, retries, errcnt


def main():
    """main logic"""
    optlist = parse_args()
    init_logging(optlist.debug)
    # init_warnings()

    ser = serial.Serial()
    ser.port = optlist.port
    ser.baudrate = optlist.baudrate
    ser.timeout = float(optlist.timeout)
    ser.open()
    relayid = None

    # -- prepare meta data
    print("#---------- MKS Gauge Report ----")
    qry = "SN"  # serial number
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"SerialNumber: {res}")
    if optlist.serialonly:
        exit()

    # run commands
    # unlock the system
    cmd = f"FD!UNLOCK"
    res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
    cmdcnt = 0
    if optlist.setid:
        cmd = f"AD!{int(optlist.setid):03d}"  # set the RS485 address
        res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        print(f"SetID result: {res}", end="")
        cmdcnt += 1
        exit()  # cmd fails after the change

    if optlist.setrelay:
        for arglist in optlist.setrelay:
            if len(arglist) != 4:
                logging.error(f"--relayid option takes 4 args, exiting")
                return
            rid, ren, rval, rdir = arglist
            rid = int(rid)
            rval = float(rval)
            print(f"--setrelay: rid={rid} ren={ren} rval={rval} rdir={rdir}")
            if rid not in {1, 2, 3}:
                logging.error(f"relayid not in allowed set {1,2,3}")
                return
            ren = ren.upper()
            if ren != "OFF" and ren != "ON":
                logging.error(f"relay enable ({ren}) must be OFF OR ON")
                return
            rsp = float(rval)
            if rsp < 1e-8 or rsp > 500:
                logging.error(f"relay setpoint:{rsp} must be in range (2E-8, 500)")
                return
            cmd = f"EN{rid:d}!{ren}"  # set the relay1 setpoint
            res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
            print(f"relay {rid} enable is set to {res}")
            cmdcnt += 1
            time.sleep(float(0.2))
            #
            cmd = f"SP{rid:d}!{rsp:.2E}"  # set the relay1 setpoint
            res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
            print(f"relay {rid} setpoint is set to {res}")
            cmdcnt += 1
            time.sleep(float(0.2))
            #
            cmd = f"SD{rid:d}!{rdir}"  # set the relay1 direction
            res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
            print(f"relay {rid} direction set to {res}")
            cmdcnt += 1
            time.sleep(float(0.2))

    if optlist.setusertag:
        uval = optlist.setusertag[0].upper()
        cmd = f"UT!{uval}"  # set the relay1 direction
        res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        print(f"usertag:{res} is set")
        cmdcnt += 1
        time.sleep(float(0.2))

    if optlist.ccenable:
        cen = optlist.ccenable.upper()
        if cen != "OFF" and cen != "ON":
            logging.error(f"ccenable ({cen}) must be OFF OR ON")
            return
        cmd = f"ENC!{cen}"  # set Auto CC
        res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        print(f"CCenable is set to {res}")
        cmdcnt += 1
        time.sleep(float(0.2))

    if optlist.ccon:
        ccn = float(optlist.ccon)
        if ccn < 1e-4 or ccn > 5e-4:
            logging.error(f"CCAuto On setpoint:{ccn} must be in range (1e-4, 5e-4)")
            return
        cmd = f"SLC!{ccn:.2E}"  # set the CCAuto On
        res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        print(f"CCAuto On setpoint is set to {res}")
        cmdcnt += 1
        time.sleep(float(0.2))

    if optlist.ccoff:
        ccf = float(optlist.ccoff)
        if ccf < 5e-4 or ccf > 8e-4:
            logging.error(f"CCAuto Off setpoint:{ccf} must be in range (5e-4, 8e-4)")
            return
        cmd = f"SHC!{ccf:.2E}"  # set the CCAuto On
        res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        print(f"CCAuto Off setpoint is set to {res}")
        cmdcnt += 1
        time.sleep(float(0.2))

    if optlist.ccprotection:
        pro = int(optlist.ccprotection)
        if pro < 10 or pro > 120:
            logging.error(f"CC protection setpoint:{pro} must be in range (10, 120)")
            return
        cmd = f"PRO!{pro}"  # set the CC protection set point (seconds)
        res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        print(f"CC protection setpoint is set to {res}")
        cmdcnt += 1
        time.sleep(float(0.2))

    if optlist.ccsmoothing:
        ccs = float(optlist.ccon)
        if ccs < 1e-4 or ccs > 5e-4:
            logging.error(f"CCAuto On setpoint:{ccs} must be in range (1e-4, 5e-4)")
            return
        cmd = f"SLP!{ccs:.2E}"  # set the CC/MP smoothing boundary
        res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        print(f"CC smoothing setpoint is set to {res}")
        cmdcnt += 1
        time.sleep(float(0.2))

    # lock the system
    cmd = f"FD!LOCK"
    res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)

    if cmdcnt:
        print(f"{cmdcnt} commands were executed")

    print("")
    qry = "PN"  # part number
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"PartNum: {res}")

    qry = "UT"  # user tag
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"UserTag: {res}")

    qry = "MD"  # model number
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Model: {res}")

    qry = "DT"  # device type
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"DeviceType: {res}")

    qry = "FV"  # firmware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Firmware: {res}")

    qry = "HV"  # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Hardware: {res}")

    qry = "AD"  # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Address: {res}")

    qry = "BR"  # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"BaudRate: {res}")

    qry = "RSD"  # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"RecieveSendDelay: {res}")

    qry = "ENC"  # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"AutoCC: {res}")

    qry = "SLC"  # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCOnSetpoint: {res}")

    qry = "SHC"  # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCOffSetpoint: {res}")

    qry = "SLP"  # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CC/MP smoothing setpoint: {res}")

    qry = "PRO"  # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CC protection setpoint: {res} (sec > 5E-3)")

    qry = "TIM"  # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"TimeOn: {res}")

    qry = "TIM2"  # Cold Cathode time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCTimeOn: {res}")

    qry = "TIM3"  # Cold Cathode dose
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCDose: {res}")

    qry = "PR4"  # comb pressure reading
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Combined Pressure: {res}")

    qry = "PR5"  # comb pressure reading
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Cold Cathode Reading: {res}")

    qry = "TEM"  # trans status
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"temp: {float(res):.1f} C")

    qry = "T"  # trans status
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"status: {res}")

    print("")

    print("Relays:")
    for a in range(1, 4):

        query = "EN{}".format(a)  # relay enabled?
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f"    R{a} enable: {res}", end="")
        #
        query = "SH{}".format(a)  # setpoint switch value
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f"    R{a} hysteresis: {res}", end="")
        #
        query = "SP{}".format(a)  # setpoint switch value
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f"    R{a} setPoint: {res}", end="")
        #
        query = "SD{}".format(a)  # setpoint direction value
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f" R{a} direction: {res}", end="")
        #
        query = "SS{}".format(a)  # status SET|CLEAR
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f" R{a} status: {res}")
    ser.close()


# cmd                   response        description
# @xxxBR!19200;FF       @xxxACK19200;F  Set communication Baud rate (4800, 9600, 19200, 38400, 57600, 115200, 230400)
# @xxxAD!123;FF         @xxxACK123;FF   Set Transducer communication address (001 to 253)
# @xxxRSD!OFF;FF        @xxxACKOFF;FF   Turn on or off communication delay between receive and transmit sequence.
# @xxxSP{relay}!{sp};FF @xxxACK{sp};FF  Turn on or off communication delay between receive and transmit sequence.
# @xxx{cmd}!{arg};FF


if __name__ == "__main__":
    main()
    sys.exit()
