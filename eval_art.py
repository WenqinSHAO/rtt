"""
evaluate the changedetection method on artifical dataset
"""
import pandas as pd
import os
from localutils import changedetect as dc, benchmark as bch
import logging
import ConfigParser


def main():
    # logging setting
    logging.basicConfig(filename='eval_art.log', level=logging.INFO,
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

    # load where artificial traces are stored
    try:
        art_dir = config.get("dir", "artificial_trace")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("config for artificial trace storage is not right.")
        return

    # check if the folder is there
    if not os.path.exists(art_dir):
        logging.critical("folder %s does not exisit." % data_dir)
        return

    res = dict()
    window = 2  # perform evaluation with window size equaling 2
    for f in os.listdir(art_dir):
        if f.endswith('.csv') and not f.startswith('~'):
            logging.info("handling %s" % f)
            trace = pd.read_csv(os.path.join(art_dir, f), sep=';')
            fact = trace['cp']
            fact = [i for i, v in enumerate(fact) if v == 1]  # fact in format of data index
            pred_normal = dc.cpt_normal(trace['rtt'])
            pred_np = dc.cpt_np(trace['rtt'])
            res[f] = dict(len=len(fact), changes=len(fact),
                          normal=bch.evaluation_window_weighted(trace['rtt'],
                                                                fact,
                                                                pred_normal, window),
                          np=bch.evaluation_window_weighted(trace['rtt'],
                                                            fact,
                                                            pred_np, window))

    with open(os.path.join(data_dir, 'eval_art.csv'), 'w') as fp:
        fp.write(';'.join(
            ['file', 'len', 'changes', 'tp', 'fp', 'fn', 'precision', 'recall', 'dis', 'score', 'method']) + '\n')
        for f in res:
            for m in ['normal', 'np']:
                line = ';'.join([str(i) for i in [f, res[f]['len'], res[f]['changes'],
                                                  res[f][m]['tp'], res[f][m]['fp'], res[f][m]['fn'],
                                                  res[f][m]['precision'], res[f][m]['recall'],
                                                  res[f][m]['dis'], res[f][m]['score'], m]]) + '\n'
                fp.write(line)


if __name__ == '__main__':
    main()
