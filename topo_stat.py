"""
this script reads the AS paths in data/path_analysis and data/ repository and counts the number of AS, AS path, IP path, IXP
"""
import traceback
import logging
import multiprocessing
import ConfigParser
import os
import time
import itertools
import json
from localutils import misc as ms

DST = ['192.228.79.201', '2001:500:84::b', 226]


def worker(fn, data_dir, path_alyz_dir):
    try:  # load traceroute file
        with open(os.path.join(data_dir, fn), 'r') as fp:
            traceroute = json.load(fp)
    except IOError as e:
        logging.error(e)
        return [], set(), set(), set()

    try:  # load path analysis file
        with open(os.path.join(path_alyz_dir, fn), 'r') as fp:
            path_alyz = json.load(fp)
    except IOError as e:
        logging.error(e)
        return [], set(), set(), set()

    pbs = set(traceroute.keys()) & set(path_alyz.keys())
    logging.info("%d probes in common for %s" % (len(pbs), fn))
    pb_res = []
    unique_as_glb = set()
    unique_ixp_glb = set()
    unique_as_path_glb = set()
    for pb in pbs:
        ip_paths = traceroute.get(pb).get('path')
        #reached_ip = [[hop[1] for hop in path] for path in ip_paths if (path[-1][1] in DST)]
        reached_ip = [[hop[1] for hop in path] for path in ip_paths]
        as_paths = path_alyz.get(pb).get('asn_path')
        reached_as = [i for i in as_paths if len(i) >= 1 and i[-1] in DST]

        unique_as = set([reached_as[i][j] for i in range(len(reached_as)) for j in range(len(reached_as[i])) if
                         type(reached_as[i][j]) is int])
        unique_ixp = set([reached_as[i][j] for i in range(len(reached_as)) for j in range(len(reached_as[i])) if
                         type(reached_as[i][j]) is not int])
        unique_ip_path = set([';'.join([str(hop) for hop in path]) for path in reached_ip])
        unique_as_path = set([';'.join([str(hop) for hop in path]) for path in reached_as])

        pb_res.append((int(pb), len(unique_ip_path), len(unique_as_path), len(unique_as), len(unique_ixp)))
        unique_as_glb.update(unique_as)
        unique_ixp_glb.update(unique_ixp)
        unique_as_path_glb.update(unique_as_path)

    return pb_res, unique_as_glb, unique_ixp_glb, unique_as_path_glb


def worker_wrapper(args):
    try:
        return worker(*args)
    except Exception:
        logging.critical("Exception in worker.")
        traceback.print_exc()
        raise


def main():
    # log to data_collection.log file
    logging.basicConfig(filename='topo_stat.log', level=logging.DEBUG,
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
        path_alyz_dir = config.get("dir", "path_analysis")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("Config for data storage is not right.")
        return

    # log error if the data repository is not there
    if not os.path.exists(data_dir):
        logging.critical("Repository %s storing measurement data is missing" % data_dir)
        return

    # create repository if not yet there
    if not os.path.exists(path_alyz_dir):
        logging.critical("Repository %s storing measurement data is missing" % path_alyz_dir)
        return

    logging.info("Finished loading libs and config.")
    t1 = time.time()

    task = (([5010], 'v4'), ([6010], 'v6'))

    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())

    for msm, tid in task:
        try:
            chunk_count = ms.get_chunk_count(os.path.join(data_dir, 'pb_chunk_index_%s.csv' % tid))
        except (OSError, IOError, IndexError, ValueError) as e:
            logging.critical("Failed to learn chunk numbers for task %s: %s" % (tid, e))
            return
        for mid in msm:
            file_chunk = ["%d_%d.json" % (i, mid) for i in xrange(chunk_count)]
            res = pool.map(worker_wrapper,
                           itertools.izip(file_chunk, itertools.repeat(data_dir), itertools.repeat(path_alyz_dir)))

            # save results to file
            pb_summary = []
            unique_as = set()
            unique_ixp = set()
            unique_as_path = set()

            for p, a, x, pth in res:
                pb_summary.append(p)
                unique_as.update(a)
                unique_ixp.update(x)
                unique_as_path.update(pth)

            with open(os.path.join(data_dir, 'topo_stat_%s.csv' % tid), 'w') as fp:
                fp.write(';'.join(
                    ['probe', 'ip_path_count', 'as_path_count', 'as_count', 'ixp_count']) + '\n')
                for ck in pb_summary:
                    for line in ck:
                        fp.write(";".join([str(i) for i in line]) + '\n')

            with open(os.path.join(data_dir, 'unique_as_%s.txt' % tid), 'w') as fp:
                for asn in unique_as:
                    fp.write(str(asn) + '\n')

            with open(os.path.join(data_dir, 'unique_ixp_%s.txt' % tid), 'w') as fp:
                for ixp in unique_ixp:
                    fp.write(str(ixp) + '\n')

            with open(os.path.join(data_dir, 'unique_as_path_%s.txt' % tid), 'w') as fp:
                for path in unique_as_path:
                    fp.write(path + '\n')

    t2 = time.time()
    logging.info("All chunks calculated in %.2f sec." % (t2 - t1))

if __name__ == '__main__':
    main()
