"""
evaluate human labeller, along with change detection method on an artificial dataset
"""
import pandas as pd
import os
from localutils import changedetect as dc, benchmark as bch
import logging
import ConfigParser
import argparse

METHOD = ['cpt_normal', 'cpt_poisson', 'cpt_poisson_naive', 'cpt_np']
PENALTY = ["BIC", "MBIC", "Hannan-Quinn"]
WINDOW = 2  # perform evaluation with window size equaling 2
MINSEGLEN = 3


def worker(f, fact_dir, human_dir):
    """evaluate human detector along with cpt methods

    Args:
        f (string): the file name in both fact dir and human dir
        fact_dir (string): directory containing facts
        human_dir (string): directory containing human labeller detections
    Return:
        list of tuple
    """
    r = []
    logging.info("handling %s" % f)
    # read csv with same name f from both directory
    fact_trace = pd.read_csv(os.path.join(fact_dir, f), sep=';')
    if type(fact_trace['rtt'][0]) is str:
        fact_trace = pd.read_csv(os.path.join(fact_dir, f), sep=';', decimal=',')
    human_trace = pd.read_csv(os.path.join(human_dir, f), sep=';')
    if type(human_trace['rtt'][0]) is str:
        human_trace = pd.read_csv(os.path.join(human_dir, f), sep=';', decimal=',')
    # check if the two traces are the same
    if len(fact_trace['rtt']) != len(human_trace['rtt']):
        logging.error("trace %s length differs in human (%d) and fact directory (%d)!" % (f, len(human_trace['rtt']),
                                                                                          len(fact_trace['rtt'])))
        return []
    else:
        eq = [fact_trace['rtt'][i] == human_trace['rtt'][i] for i in range(len(fact_trace['rtt']))]
        if not all(eq):
            logging.error("trace %s value differs in human and fact directory!" % f)
            return []

    fact = fact_trace['cp']
    fact = [i for i, v in enumerate(fact) if v == 1]  # fact in format of data index
    logging.debug("%s : change counts %d" % (f, len(fact)))

    human_detect = human_trace['cp']
    human_detect = [i for i, v in enumerate(human_detect) if v == 1]
    logging.debug("%s : human detections counts %d" % (f, len(human_detect)))

    b = bch.evaluation_window_weighted(fact_trace['rtt'], fact, human_detect, WINDOW)
    logging.debug('%r' % b)

    r.append((f, len(fact_trace), len(fact),
              b['tp'], b['fp'], b['fn'],
              b['precision'], b['recall'], b['score'], b['dis'], 'human', 'human'))

    for m, p in [(x, y) for x in METHOD for y in PENALTY]:
        logging.info("%s: evaluating %s with %s" % (f, m, p))
        method_caller = getattr(dc, m)
        detect = method_caller(fact_trace['rtt'], p, MINSEGLEN)
        b = bch.evaluation_window_weighted(fact_trace['rtt'], fact, detect, WINDOW)
        r.append((f, len(fact_trace), len(fact),
                  b['tp'], b['fp'], b['fn'],
                  b['precision'], b['recall'], b['score'], b['dis'], m, p))
        logging.debug('%r' % b)
    return r


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
    parser.add_argument("-f", "--fact",
                        help="directory storing ground fact.",
                        action="store")
    parser.add_argument("-l", "--labeller",
                        help="directory storing the detections of human labeller.",
                        action="store")
    parser.add_argument("-o", "--output",
                        help="filename storing the output result.",
                        action="store")
    args = parser.parse_args()

    # all the three inputs are required
    if not args.fact or not args.labeller or not args.output:
        print args.help
        return
    else:
        fact_dir = args.fact
        human_dir = args.labeller
        outfile = args.output

    if not os.path.exists(fact_dir):
        print "%s doesn't exist." % fact_dir
    if not os.path.exists(human_dir):
        print "%s doesn't exist." % human_dir

    files = []
    fact_files = os.listdir(fact_dir)
    for f in os.listdir(human_dir):
        if f.endswith('.csv') and (not f.startswith('~')) and f in fact_files:
            files.append(f)
    logging.info("%d traces to be considered:\n %s" % (len(files), str(files)))

    res = [worker(f, fact_dir, human_dir) for f in files]

    with open(os.path.join(data_dir, outfile), 'w') as fp:
        fp.write(';'.join(
            ['file', 'len', 'changes', 'tp', 'fp', 'fn', 'precision', 'recall', 'score', 'dis', 'method', 'penalty']) + '\n')
        for ck in res:
            for line in ck:
                fp.write(";".join([str(i) for i in line]) + '\n')


if __name__ == '__main__':
    main()
