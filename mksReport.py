#!/usr/bin/env python
"""
Issue readPressure queries to MKS 974B gauge and report stats
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
        "--setid",
        nargs="?",
        type=int,
        const=1,
        help="set the RS485 id:{1..253} and exit",
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
    mpl_logger = logging.getLogger("matplotlib")
    mpl_logger.setLevel(logging.WARNING)


def init_warnings():
    """Block warnings from Astropy"""
    warnings.simplefilter("ignore", category=AstropyWarning)

def query_and_response(query, optlist, ser):
    """ send command and return response """
    dt0 = 0.0
    retries = 0
    max_retries = 5
    query_str = f"@{optlist.id:03d}{query}?;FF"
    query_bts = bytes(query_str, "utf-8")
    errcnt = 0
    result = None
    nn = 0

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
            logging.debug(f"result={result} dt={dt:>.3f}")
            break
        elif (
            retries < max_retries and dt >= ser.timeout):  # retry
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
    """ send command and return response """
    dt0 = 0.0
    retries = 0
    max_retries = 5
    cmd_str = f"@{optlist.id:03d}{cmd};FF"
    cmd_bts = bytes(cmd_str, "utf-8")
    errcnt = 0
    result = None
    nn = 0

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
            logging.debug(f"result={result} dt={dt:>.3f}")
            break
        elif (
            retries < max_retries and dt >= ser.timeout):  # retry
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
    # ser = serial.rs485.RS485(optlist.port)
    ser.port = optlist.port
    ser.baudrate = optlist.baudrate
    ser.timeout = float(optlist.timeout)
    ser.open()

    #-- prepare meta data
    print("#---------- MKS Gauge Report ----")
    qry = "SN"    # serial number
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"SerialNumber: {res}")
    if optlist.serialonly:
        exit()

    qry = "PN"    # part number
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"PartNum: {res}")

    qry = "MD"    # model number
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Model: {res}")

    qry = "DT"    # device type
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"DeviceType: {res}")

    qry = "FV"    # firmware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Firmware: {res}")

    qry = "HV"    # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Hardware: {res}")

    qry = "AD"    # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Address: {res}")

    qry = "BR"    # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"BaudRate: {res}")

    qry = "RSD"    # hardware version
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"RecieveSendDelay: {res}")

    #cmd = "ENC!ON"   # enable AutoCC
    #res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
    #print(f"enable AutoCC, ")

    qry = "ENC"    # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"AutoCC: {res}")

    qry = "SLC"    # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCOnSetpoint: {res}")

    qry = "SHC"    # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCOffSetpoint: {res}")

    qry = "TIM"    # time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"TimeOn: {res}")

    qry = "TIM2"    # Cold Cathode time on
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCTimeOn: {res}")

    qry = "TIM3"    # Cold Cathode dose
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"CCDose: {res}")

    qry = "PR4"    # comb pressure reading
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Combined Pressure: {res}")

    qry = "PR5"    # comb pressure reading
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"Cold Cathode Reading: {res}")

    qry = "T"    # trans status
    res, dt, rt, ercnt = query_and_response(qry, optlist, ser)
    print(f"status: {res}")

    print("")

    print("Relays:")
    for a in range(1,4):
        
        #cmd = "EN{}!ON".format(a)    # enable relay
        #res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        #print(f"    enable relay{a}, ", end="")
        #cmd = "SD{}!BELOW".format(a)    # trans status
        #res, dt, rt, ercnt = cmd_and_response(cmd, optlist, ser)
        #print(f"set direction to BELOW")
        query = "EN{}".format(a)    # trans status
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f"    R{a} enable: {res}", end="")
        query = "SP{}".format(a)    # trans status
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f"    R{a} setPoint: {res}", end="")
        query = "SD{}".format(a)    # trans status
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f" R{a} direction: {res}", end="")
        query = "SS{}".format(a)    # trans status
        res, dt, rt, ercnt = query_and_response(query, optlist, ser)
        print(f" R{a} status: {res}")

    t0 = time.time()
    rstats = dict()
    dtlist = []
    retrytot = 0
    errtot = 0
    for nn in range(int(optlist.count)):
        prStr, dt, retries, errcnt = query_and_response("PR4", optlist, ser)
        dtlist.append(dt)
        prVal = float(prStr)
        if retries in rstats:
            rstats[retries] += 1
        else:
            rstats[retries] = 1
        retrytot += retries
        errtot += errcnt
        if float(optlist.delay) > dt:
            time.sleep(float(optlist.delay) - dt)

    t1 = time.time()
    elapsed = t1 - t0
    ser.close()
    print("")
    if len(dtlist):
        dtarray = np.array(dtlist)
        dtavg = np.mean(dtarray)
        dtmed = np.median(dtarray)
        dtstd = np.std(dtarray)
        dtmin = np.min(dtarray)
        dtmax = np.max(dtarray)

        print(f"dt stats:", end="")
        print(f" avg: {dtavg:>.4f}", end="")
        print(f" med: {dtmed:>4.3f}", end="")
        print(f" std: {dtstd:>.4f}", end="")
        print(f" min: {dtmin:>.4f}", end="")
        print(f" max: {dtmax:>.4f}", end="")
        print(f" nominal count: {len(dtlist)}")
        print(f"   total retries: {retrytot}")
        print(f"   total errors: {errtot}")
        print(f" rate: {(len(dtlist) / elapsed):>.1f} reads/sec")
        for rt in rstats:
            if rt > 0:
                print(f"    retry:{rt} -- {rstats[rt]:>5d} {(rstats[rt]/len(dtlist)):>.4f} probability")
        print("")



if __name__ == "__main__":
    main()
    sys.exit()
