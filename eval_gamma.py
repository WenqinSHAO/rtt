"""
evaluate the gamma distribution with different shape settings
"""
import pandas as pd
import os
from localutils import changedetect as dc, benchmark as bch, misc as ms
import logging
import ConfigParser
import traceback
import multiprocessing
import argparse
import numpy as np

METHOD = ['cpt_gamma%1', 'cpt_gamma%10', 'cpt_gamma%20', 'cpt_gamma%30', 'cpt_gamma%50', 'cpt_gamma%80',
          'cpt_gamma%adpt', 'cpt_np', 'cpt_poisson']
PENALTY = ["AIC", "BIC", "MBIC", "Hannan-Quinn"]
WINDOW = 2  # perform evaluation with window size equaling 2
MINSEGLEN = 3


def worker(f):
    f_base = os.path.basename(f)
    r = []
    logging.info("handling %s" % f)
    trace = pd.read_csv(f, sep=';')
    if type(trace['rtt'][0]) is str:
        trace = pd.read_csv(f, sep=';', decimal=',')
    fact = trace['cp']
    fact = [i for i, v in enumerate(fact) if v == 1]  # fact in format of data index
    logging.debug("%s : change counts %d" % (f_base, len(fact)))
    for m, p in [(x, y) for x in METHOD for y in PENALTY]:
        logging.info("%s: evaluating %s with %s" % (f_base, m, p))
        if 'gamma' in m:
            mm = m.split('%')
            method_caller = getattr(dc, 'cpt_gamma')
            if 'adpt' in mm[1]:
                shape = np.sqrt(np.mean([i for i in trace['rtt'] if 0 < i < 1000]))
                detect = method_caller(trace['rtt'], p, MINSEGLEN, shape=shape)
            else:
                shape = ms.type_convert(mm[1])
                detect = method_caller(trace['rtt'], p, MINSEGLEN, shape=shape)
        else:
            method_caller = getattr(dc, m)
            detect = method_caller(trace['rtt'], p, MINSEGLEN)
        b = bch.evaluation_window_weighted(trace['rtt'], fact, detect, WINDOW)
        r.append((os.path.basename(f), len(trace), len(fact),
                  b['tp'], b['fp'], b['fn'],
                  b['precision'], b['recall'], b['score'], b['dis'], m, p))
        logging.debug('%r' % b)
    return r


def worker_wrapper(args):
    try:
        return worker(args)
    except Exception:
        logging.critical("Exception in worker.")
        traceback.print_exc()
        raise


def main():
    # logging setting
    logging.basicConfig(filename='cpt_evaluation.log', level=logging.INFO,
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

    # check if the directory is there
    if not os.path.exists(data_dir):
        logging.critical("data folder %s does not exisit." % data_dir)
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory",
                        help="benchmark changepoint methods using the traces from the specified directory.",
                        action="store")
    parser.add_argument("-f", "--filename",
                        help="file name for output.",
                        action="store")
    args = parser.parse_args()

    if not args.directory or not args.filename:
        print args.help
        return
    else:
        trace_dir = args.directory
        outfile = args.filename

    if not os.path.exists(trace_dir):
        print "%s doesn't existe." % trace_dir

    files = []
    for f in os.listdir(trace_dir):
        if f.endswith('.csv') and not f.startswith('~'):
            files.append(os.path.join(trace_dir,f))

    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())
    res = pool.map(worker_wrapper, files)

    with open(os.path.join(data_dir, outfile), 'w') as fp:
        fp.write(';'.join(
            ['file', 'len', 'changes', 'tp', 'fp', 'fn', 'precision', 'recall', 'score', 'dis', 'method', 'penalty']) + '\n')
        for ck in res:
            for line in ck:
                fp.write(";".join([str(i) for i in line]) + '\n')


if __name__ == '__main__':
    main()
