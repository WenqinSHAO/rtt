"""
This script translates IP path to AS path and detect changes in both paths for each probe
"""
from localutils import pathtools as pt, dbtools as db
import localutils.misc as ms
import logging
import ConfigParser
import os
import multiprocessing
import traceback
import itertools
import json
import time


def path(fn, pb_meta, data_dir, path_alyz_dir):
    """ for each traceroute json in data, translate ip path to asn path, detect changes both in ip and asn path

    Args:
        fn (string): traceroute json file name, e.g. '0_5010.json'
        pb_meta (dict): probe_id (int) : tuple; initialized form pb.csv
        data_dir: the directory containing fn
        path_alyz_dir: the directory in which analysis results shall be stored

    """
    # skip if already done
    if os.path.exists(os.path.join(path_alyz_dir, fn)):
        logging.info("%r already treated, thus skipped." % fn)
        return
    t1 = time.time()
    # 5010 for ipv4 traceroute, 6010 for ipv6
    is_v4 = True
    if '6010.json' in fn:
        is_v4 = False

    with open(os.path.join(data_dir, fn), 'r') as fp:
        mes = json.load(fp)

    output = dict()
    for pb, rec in mes.items():
        pb_addr = None
        pb = int(pb)
        # get probe address from metadata
        if pb in pb_meta:
            if is_v4:
                pb_addr = pb_meta[pb][1]
            else:
                pd_addr = pb_meta[pb][4]
        ip_path_seq_raw = rec.get('path')  # [[#hop, address, rtt],...]
        ip_path_seq = []  # [address,...]
        paris_id_seq = rec.get('paris_id')
        if ip_path_seq is not None and paris_id_seq is not None:
            if len(paris_id_seq) != len(ip_path_seq_raw):
                logging.error("%r in %r, path and paris are of unequal length" % (pb, fn))
            else:
                asn_path_seq = []
                # translate ip path to asn path
                for ip_path in ip_path_seq_raw:
                    # extract the address string
                    ip_path = [str(i[1]) for i in ip_path]
                    ip_path_seq.append(ip_path)
                    # add probe address at the beginning if not None
                    if pb_addr is not None:
                        ip_path = [pb_addr] + ip_path
                    enhanced_path = [pt.get_ip_info(i) for i in ip_path]  # query IP information
                    enhanced_path = pt.bridge(enhanced_path)  # remove holes if possible
                    if is_v4:  # for v4 traceroute, detect IXP
                        enhanced_path = pt.insert_ixp(enhanced_path)
                    asn_path = [hop.get_asn() for hop in enhanced_path]  # construct asn path
                    asn_path = pt.remove_repeated_asn(asn_path)  # remove continuously repeated asn
                    asn_path_seq.append(asn_path)
                # detect asn path changes
                asn_path_change = pt.as_path_change_cs(asn_path_seq)
                asn_path_change_ixp = pt.as_path_change_ixp_cs(asn_path_seq)
                # detect ip forwarding pattern change with three different methods
                ifp_change_simple = pt.ifp_change(pt.ip_path_change_simple(paris_id_seq, ip_path_seq, 16),
                                                  len(paris_id_seq))
                ifp_change_bck_ext = pt.ifp_change(pt.ip_path_change_bck_ext(paris_id_seq, ip_path_seq, 16),
                                                   len(paris_id_seq))
                ifp_change_split = pt.ifp_change(pt.ip_path_change_split(paris_id_seq, ip_path_seq, 16),
                                                 len(paris_id_seq))
                output[pb] = dict(epoch=rec.get('epoch'), paris_id=paris_id_seq,
                                  ip_path=ip_path_seq, asn_path=asn_path_seq,
                                  ifp_simple=ifp_change_simple,
                                  ifp_bck=ifp_change_bck_ext,
                                  ifp_split=ifp_change_split,
                                  as_path_change=asn_path_change,
                                  as_path_change_ixp=asn_path_change_ixp)

    with open(os.path.join(path_alyz_dir, fn), 'w') as fp:
        json.dump(output, fp)

    t2 = time.time()
    logging.info("%s handled in %.2f sec." % (fn, (t2 - t1)))


def path_wrapper(args):
    """ wrapper for path() that enables trouble shooting in worker and multiple args"""
    try:
        return path(*args)
    except Exception:
        logging.critical("Exception in worker.")
        traceback.print_exc()
        raise


def main():
    # log to data_collection.log file
    logging.basicConfig(filename='path_analysis.log', level=logging.DEBUG,
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
        os.makedirs(path_alyz_dir)

    logging.info("Finished loading libs and config.")
    t1 = time.time()

    task = (([5010], 'v4'), ([6010], 'v6'))

    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())
    probe_meta = {i[0]: i for i in ms.read_probe(os.path.join(data_dir, "pb.csv"))}

    for msm, tid in task:
        try:
            chunk_count = ms.get_chunk_count(os.path.join(data_dir, 'pb_chunk_index_%s.csv' % tid))
        except (OSError, IOError, IndexError, ValueError) as e:
            logging.critical("Failed to learn chunk numbers for task %s: %s" % (tid, e))
            return
        for mid in msm:
            file_chunk = ["%d_%d.json" % (i, mid) for i in xrange(chunk_count)]
            pool.map(path_wrapper,
                     itertools.izip(file_chunk, itertools.repeat(probe_meta),
                                    itertools.repeat(data_dir), itertools.repeat(path_alyz_dir)))

    t2 = time.time()
    logging.info("All chunks calculated in %.2f sec." % (t2 - t1))


if __name__ == '__main__':
    main()
