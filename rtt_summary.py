"""
This script summarizes the per probe RTT for both ping and traceroute measurements
"""
from localutils import timetools as tt, misc as ms
import multiprocessing
import ConfigParser
import logging
import os
import json
import numpy as np
import traceback


def rtt(f):
    summery = []
    with open(f, 'r') as fp:
        mes = json.load(fp)
        for pb, rec in mes.items():
            if 'min_rtt' in rec:
                rtts = rec.get('min_rtt', None)
                raw_len = len(rtts) # can be 0
                pos_rtt = [i for i in rtts if i > 0]
                if pos_rtt:
                    reached_len = len(pos_rtt) # if empty array is given, returns nan of type numpy.float64
                    mean_ = np.mean(pos_rtt)
                    mid = np.median(pos_rtt)
                    min_ = np.min(pos_rtt)
                    max_ = np.max(pos_rtt)
                    std_ = np.std(pos_rtt)
                else:
                    raw_len = reached_len = mean_ = mid = min_ = max_ = std_ = None
            elif 'path' in rec:
                paths = rec.get('path', None)
                raw_len = len(paths)
                reached_path = [i for i in paths if (i[-1][0] < 255 and i[-1][2] > 0)]
                reached_len = len(reached_path)
                rtts_last = [i[-1][2] for i in reached_path]
                if rtts_last:
                    mean_ = np.mean(rtts_last)
                    mid = np.median(rtts_last)
                    min_ = np.min(rtts_last)
                    max_ = np.max(rtts_last)
                    std_ = np.std(rtts_last)
                else:
                    raw_len = reached_len = mean_ = mid = min_ = max_ = std_ = None
            else:
                logging.warning("Probe %s with empty measurement result in %s" % (pb, f))
                raw_len = reached_len = mean_ = mid = min_ = max_ = std_ = None
            summery.append((pb, raw_len, reached_len, mean_, mid, min_, max_, std_))
    return summery


def rtt_wrapper(f):
    try:
        return rtt(f)
    except Exception:
        logging.critical("Exception in worker.")
        traceback.print_exc()
        raise


def main():
    # log to data_collection.log file
    logging.basicConfig(filename='rtt_summary.log', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S %z')

    # load data collection configuration from config file in the same folder
    config = ConfigParser.ConfigParser()
    if not config.read('./config'):
        logging.critical("Config file ./config is missing.")
        return

    # load the configured directory where collected data shall be saved
    try:
        data_dir = config.get("dir", "data")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("config for data storage is not right.")
        return

    # create data repository if not yet there
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # read configurations for data collection
    try:
        # start = tt.string_to_datetime(config.get("collection", "start"))
        # end = tt.string_to_datetime(config.get("collection", "end"))
        msmv4 = config.get("collection", "msmv4").split(',')  # multiple msm id can be separated by comma
        msmv4 = [int(i.strip()) for i in msmv4]  # remove the whitespaces and convert to int, could have ValueError
        msmv6 = config.get("collection", "msmv6").split(',')  # do the same for IPv6 measurements
        msmv6 = [int(i.strip()) for i in msmv6]
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError, ValueError):
        logging.critical("config for data collection is not right.")
        return

    task = ((msmv4, 'v4'), (msmv6, 'v6'))
    # each task has a probe to chunk id indexing file
    # the number of chunks has to be learnt from these file first
    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())
    for msm, tid in task:
        try:
            chunk_count = ms.get_chunk_count(os.path.join(data_dir, 'pb_chunk_index_%s.csv' % tid))
        except (OSError, IOError, IndexError, ValueError) as e:
            logging.critical("Failed to learn chunk numbers for task %s: %s" % (tid, e))
            return
        for mid in msm:
            file_chunk = [os.path.join(data_dir, "%d_%d.json" % (i, mid)) for i in xrange(chunk_count)]
            summary = pool.map(rtt_wrapper, file_chunk)
            with open(os.path.join(data_dir, 'rtt_summary_%d_of_%s.csv' % (mid, tid)),'w') as fp:
                fp.write('probe_id;raw_length;valid_length;mean;median;min;max;std\n')
                if summary:
                    for ck in summary:
                        for pb in ck:
                            fp.write(";".join([str(i) for i in pb]) + '\n')


if __name__ == '__main__':
    main()
