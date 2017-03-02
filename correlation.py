"""
this script correlates the RTT change and path changes
"""
import traceback
import logging
import ConfigParser
import os
import multiprocessing
import itertools
import json
import time
from localutils import benchmark as bch, misc as ms


METHOD = ['cpt_normal', 'cpt_np', 'cpt_poisson']
PENALTY = ["MBIC"]
PATH_CH_M = ['as_path_change', 'as_path_change_ixp', 'ifp_simple', 'ifp_bck']
WINDOW = 1800  # interval of traceroute measurement


def worker(rtt_ch_fn, path_ch_fn, rtt_ch_m):
    """ correlates the RTT changes and path changes in the given file

    Args:
        rtt_ch_fn (string): path to the rtt analysis output
        path_ch_fn (string): path to the path analysis output
        rtt_ch_m (string): the method used for RTT change detection

    Returns:
        rtt_change_res (list of tuple): from each rtt change point of view, what is it's character, is it matched to a path change
        path_change_res (list of tuple): from each path change point of view, is it matched to an RTT change, what kind of
        overview (list of tuple): from each probe, what's the overall correlation between RTT change and path change
    """
    rtt_change_res = []
    overview = []

    try:  # load rtt analysis
        with open(rtt_ch_fn, 'r') as fp:
            rtt_ch = json.load(fp)
    except IOError as e:
        logging.error(e)
        return [], []

    try:  # load path analysis
        with open(path_ch_fn, 'r') as fp:
            path_ch = json.load(fp)
    except IOError as e:
        logging.error(e)
        return [], []

    pbs = set(rtt_ch.keys()) & set(path_ch.keys())
    logging.info("%d probes in common in %s (%d) and %s (%d)" % (len(pbs), rtt_ch_fn, len(rtt_ch),
                                                                 path_ch_fn, len(path_ch)))

    # all possible rtt change detection method, key in the per pb rec in json
    # rtt_ch_m = [m+'&'+p for m in METHOD for p in PENALTY]
    # put all the method in one out file is too large to handle
    rtt_ch_m = [rtt_ch_m]

    for pb in pbs:
        rtt_ch_rec = rtt_ch.get(pb)
        path_ch_rec = path_ch.get(pb)
        rtt_trace = rtt_ch_rec.get('min_rtt')
        rtt_tstp = rtt_ch_rec.get('epoch')
        path_tstp = path_ch_rec.get('epoch')
        # for each rtt_ch_method try all path detections methods
        for rtt_m in rtt_ch_m:
            rtt_ch_index = [i for i, v in enumerate(rtt_ch_rec.get(rtt_m)) if v == 1]
            rtt_ch_tstp = [rtt_tstp[i] for i in rtt_ch_index]
            rtt_ch_character = bch.character(rtt_trace, rtt_ch_index)
            match_dic = {i: [] for i in PATH_CH_M}
            dis_dic = {i: [] for i in PATH_CH_M}
            for path_m in PATH_CH_M:
                path_ch_index = [i for i, v in enumerate(path_ch_rec.get(path_m)) if v == 1]
                path_ch_tstp = [path_tstp[i] for i in path_ch_index]
                cr = bch.evaluation_window_adp(rtt_ch_tstp, path_ch_tstp, WINDOW, return_match=True)
                # record the overview of matching between rtt_m and path_m
                overview.append((int(pb), len(rtt_trace), rtt_m, len(rtt_ch_index), path_m, len(path_ch_index),
                                 cr['tp'], cr['fp'], cr['fn'],
                                 cr['precision'], cr['recall'], cr['dis']))
                rtt_to_path = {i[0]: i[1] for i in cr.get('match')}
                #path_to_rtt = {i[1]: i[0] for i in cr.get('match')}
                # for each single RTT change check the match with path change
                for i, ch in enumerate(rtt_ch_index):
                    if i in rtt_to_path:
                        have_match = True
                        dis = abs(rtt_ch_tstp[i] - path_ch_tstp[rtt_to_path.get(i)])
                    else:
                        have_match = False
                        dis = None
                    match_dic[path_m].append(have_match)
                    dis_dic[path_m].append(dis)
            # combine the matching with different path change into oneline
            for i, ch in enumerate(rtt_ch_index):
                entry = [int(pb), i, ch]
                entry.extend(rtt_ch_character[i])
                for pm in PATH_CH_M:
                    entry.extend([match_dic[pm][i], dis_dic[pm][i]])
                rtt_change_res.append(entry)

    return rtt_change_res, overview


def worker_wrapper(args):
    try:
        return worker(*args)
    except Exception:
        logging.critical("Exception in worker.")
        traceback.print_exc()
        raise


def main():
    # log to data_collection.log file
    logging.basicConfig(filename='correlation.log', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S %z')

    # load data collection configuration from config file in the same folder
    config = ConfigParser.ConfigParser()
    if not config.read('./config'):
        logging.critical("Config file ./config is missing.")
        return

    # data dir
    try:
        data_dir = config.get("dir", "data")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("Config for data storage is not right.")
        return

    if not os.path.exists(data_dir):
        logging.critical("Repository %s storing data is missing" % data_dir)
        return

    # rtt analysis dir
    try:
        rtt_alyz_dir = config.get("dir", "rtt_analysis")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("Config for data storage is not right.")
        return

    if not os.path.exists(rtt_alyz_dir):
        logging.critical("Repository %s storing rtt analysis is missing" % rtt_alyz_dir)
        return

    # path analysis dir
    try:
        path_alyz_dir = config.get("dir", "path_analysis")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("Config for data storage is not right.")
        return

    # log error if the data repository is not there
    if not os.path.exists(path_alyz_dir):
        logging.critical("Repository %s storing path analysis is missing" % path_alyz_dir)
        return

    logging.info("Finished loading libs and config.")
    t1 = time.time()

    task = (((1010, 5010), 'v4'), ((2010, 6010), 'v6'))

    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())

    for (ping_msm, trace_msm), tid in task:
        # get total number of chunks for each tid
        try:
            chunk_count = ms.get_chunk_count(os.path.join(data_dir, 'pb_chunk_index_%s.csv' % tid))
        except (OSError, IOError, IndexError, ValueError) as e:
            logging.critical("Failed to learn chunk numbers for task %s: %s" % (tid, e))
            return

        # chunks to be handled
        rtt_files = [os.path.join(rtt_alyz_dir, "%d_%d.json" % (i, ping_msm)) for i in xrange(chunk_count)]
        path_files = [os.path.join(path_alyz_dir, "%d_%d.json" % (i, trace_msm)) for i in xrange(chunk_count)]

        for rtt_ch_m in [m + '&' + p for m in METHOD for p in PENALTY]:
            res = pool.map(worker_wrapper, itertools.izip(rtt_files, path_files, itertools.repeat(rtt_ch_m)))
            # save result to csv in data dir
            file_suf = rtt_ch_m.split('&')[0]
            rtt_change_res = []
            overview = []

            for r, o in res:
                rtt_change_res.append(r)
                overview.append(o)

            with open(os.path.join(data_dir, 'cor_overview_%s_%s.csv' % (tid, file_suf)), 'w') as fp:
                fp.write(';'.join(
                    ['probe', 'trace_len', 'cpt_method', 'cpt_count', 'pch_method', 'pch_count',
                     'tp', 'fp', 'fn', 'precision', 'recall', 'dis']) + '\n')
                for ck in overview:
                    for line in ck:
                        fp.write(";".join([str(i) for i in line]) + '\n')

            with open(os.path.join(data_dir, 'cor_rtt_ch_%s_%s.csv' % (tid, file_suf)), 'w') as fp:
                header = ['probe', 'i', 'cpt_idx',
                          'delta_median', 'delta_std', 'seg_len', 'seg_median', 'seg_std']
                for pm in PATH_CH_M:
                    header.extend(['%s_match' % pm, '%s_dis' % pm])
                fp.write(';'.join(header) + '\n')
                for ck in rtt_change_res:
                    for line in ck:
                        fp.write(";".join([str(i) for i in line]) + '\n')

    t2 = time.time()
    logging.info("All chunks calculated in %.2f sec." % (t2 - t1))


if __name__ == '__main__':
    main()

