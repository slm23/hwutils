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


def read_pressure():
    """main logic"""
    optlist = parse_args()
    init_logging(optlist.debug)
    # init_warnings()

    ser = serial.Serial()
    # ser = serial.rs485.RS485(optlist.port)
    ser.port = optlist.port
    ser.baudrate = optlist.baudrate
    # ser.rs485_mode = serial.rs485.RS485Settings(...)
    # ser.rs485_mode.delay_before_rx = 0.02
    # ser.rs485_mode.loopback = True
    ser.timeout = float(optlist.timeout)
    ser.open()
    cmd = "PR4"
    query_str = f"@{optlist.id:03d}{cmd}?;FF"
    query_bts = bytes(query_str, "utf-8")
    dtlist = []
    errcnt = 0
    retrycnt = 0
    max_retries = 5
    t0 = time.time()
    rstats = dict()
    for nn in range(int(optlist.count)):
        dt0 = 0.0
        retries = 0
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

            if optlist.loopback:  # RS485 cmd echo -> read again
                if re.match(f"@{optlist.id:03d}{cmd}\?;FF", resp.decode()):
                    cmd_echo = resp
                    cmd_dt = dt
                    ser.timeout = float(optlist.timeout) - cmd_dt
                    resp = ser.read_until(expected=b";FF", size=None)
                    end_ns = time.clock_gettime_ns(time.CLOCK_REALTIME)
                    dt = (end_ns - start_ns) * 1e-9
                    logging.debug(f"cmd echo={cmd_echo} dt={cmd_dt:>.3f}")
                else:
                    logging.warning("half duplex query echo failed")

            # check the reply is valid
            if re.match(r"@...ACK.*;FF", resp.decode()):
                dt = dt0 + dt
                dtlist.append(dt)
                prStr = re.match(r"@...ACK(.*);FF", resp.decode()).groups()[0]
                prVal = float(prStr)
                logging.debug(f"prStr={prStr}  prVal={prVal:>.4g} dt={dt:>.3f}")
                break
            elif (
                retries < max_retries and len(resp) == 0 and dt >= ser.timeout):  # retry
                # logging.warning(
                #     "got 0 byte response and read timeout at trial %d -- retrying", nn
                # )
                print(f".", end="")
                dt0 = dt
                retries += 1
                retrycnt += 1
            else:
                dt = dt0 + dt
                logging.warning(
                    "failed at trial %d: cmd=%s  resp=%s, dt=%.3f",
                    nn,
                    cmd,
                    resp,
                    dt,
                )
                errcnt += 1
                break

        if retries in rstats:
            rstats[retries] += 1
        else:
            rstats[retries] = 1
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

        print(f"dt stats: avg: {dtavg:>.4f}")
        print(f"          med: {dtmed:>.3f}")
        print(f"          std: {dtstd:>.4f}")
        print(f"          min: {dtmin:>.4f}")
        print(f"          max: {dtmax:>.4f}")
        print(f" nominal count: {len(dtlist)}")
        print(f"   retry count: {retrycnt}")
        print(f"   error count: {errcnt}")
        print(f" rate: {(len(dtlist) / elapsed):>.1f} reads/sec")
        for rt in rstats:
            print(f"    retry:{rt} -- {rstats[rt]:>5d} {(rstats[rt]/len(dtlist)):>.4f} probability")
    sys.exit()


if __name__ == "__main__":
    read_pressure()
