"""
This script translates IP path to AS path and detect changes in both paths for each probe
"""
import localutils.changedetect as dc
import localutils.misc as ms
import logging
import ConfigParser
import os
import multiprocessing
import traceback
import itertools
import json
import time
from rpy2.rinterface import RRuntimeError

METHOD = ['cpt_normal', 'cpt_poisson', 'cpt_np']
PENALTY = ["MBIC"]
MINSEGLEN = 3


def rtt(fn, data_dir, rtt_alyz_dir):
    """ for each ping json in data, detect changes in min_rtt time series

    Args:
        fn (string): traceroute json file name, e.g. '0_1010.json'

        data_dir: the directory containing fn
        rtt_alyz_dir: the directory in which analysis results shall be stored

    """
    # skip if already done
    if os.path.exists(os.path.join(rtt_alyz_dir, fn)):
        logging.info("%r already treated, thus skipped." % fn)
        return
    t1 = time.time()

    try:
        with open(os.path.join(data_dir, fn), 'r') as fp:
            mes = json.load(fp)
    except IOError as e:
        logging.error(e)
        return

    output = dict()
    for pb, rec in mes.items():
        pb = int(pb)
        rtt_mes = rec.get('min_rtt')  # [[#hop, address, rtt],...]
        output[pb] = dict(epoch=rec.get('epoch'), min_rtt=rtt_mes)
        for m, p in [(x, y) for x in METHOD for y in PENALTY]:
            method_caller = getattr(dc, m)
            try:
                detect = method_caller(rtt_mes, p, MINSEGLEN)
            except RRuntimeError as e:
                logging.error("%s, %d encounter error in R runtime: %s" % (fn, pb, e))
                detect = []
            detect = [1 if i in detect else 0 for i in range(len(rtt_mes))]
            output[pb][m+'&'+p] = detect

    with open(os.path.join(rtt_alyz_dir, fn), 'w') as fp:
        json.dump(output, fp)

    t2 = time.time()
    logging.info("%s handled in %.2f sec." % (fn, (t2 - t1)))


def rtt_wrapper(args):
    """ wrapper for path() that enables trouble shooting in worker and multiple args"""
    try:
        return rtt(*args)
    except Exception:
        logging.critical("Exception in worker.")
        traceback.print_exc()
        raise


def main():
    # log to data_collection.log file
    logging.basicConfig(filename='rtt_analysis.log', level=logging.DEBUG,
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
        logging.critical("Config for data storage is not right.")
        return

    try:
        rtt_alyz_dir = config.get("dir", "rtt_analysis")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("Config for data storage is not right.")
        return

    # log error if the data repository is not there
    if not os.path.exists(data_dir):
        logging.critical("Repository %s storing measurement data is missing" % data_dir)
        return

    # create repository if not yet there
    if not os.path.exists(rtt_alyz_dir):
        os.makedirs(rtt_alyz_dir)

    logging.info("Finished loading libs and config.")
    t1 = time.time()

    task = (([1010], 'v4'), ([2010], 'v6'))

    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())

    for msm, tid in task:
        try:
            chunk_count = ms.get_chunk_count(os.path.join(data_dir, 'pb_chunk_index_%s.csv' % tid))
        except (OSError, IOError, IndexError, ValueError) as e:
            logging.critical("Failed to learn chunk numbers for task %s: %s" % (tid, e))
            return
        for mid in msm:
            file_chunk = ["%d_%d.json" % (i, mid) for i in xrange(chunk_count)]
            pool.map(rtt_wrapper,
                     itertools.izip(file_chunk, itertools.repeat(data_dir), itertools.repeat(rtt_alyz_dir)))

    t2 = time.time()
    logging.info("All chunks calculated in %.2f sec." % (t2 - t1))


if __name__ == '__main__':
    main()
