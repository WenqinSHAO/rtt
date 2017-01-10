from localutils import atlas as at, timetools as tt
import json
import os
import time
import multiprocessing
import ConfigParser
import logging
import itertools


def mes_fetcher(chunk_id, msm, probe_list, start, end, suffix, save_dir):
    t1 = time.time()
    mes = at.get_ms_by_pb_msm_id(msm_id=msm, pb_id=probe_list, start=start, end=end)
    if mes:
        # store measurements with raw time stamps
        with open(os.path.join(save_dir, '%d_%s.json' % (chunk_id, suffix)), 'w') as fp:
            json.dump(mes, fp)
    t2 = time.time()
    logging.info("Chunk %d of measurement %s fetched in %s sec." % (chunk_id, suffix, (t2 - t1)))


def mes_fetcher_wrapper(args):
    return mes_fetcher(*args)


def main():
    # log to data_collection.log file
    logging.basicConfig(filename='data_collection.log', level=logging.DEBUG,
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
        start = config.get("collection", "start")
        end = config.get("collection", "end")
        msm = config.get("collection", "msm").split(',')  # multiple msm id can be separated by comma
        msm = [int(i.strip()) for i in msm]  # remove the whitespaces and convert to int, could have ValueError
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError, ValueError):
        logging.critical("config for data collection is not right.")
        return

    # fetch probes/anchors and their meta data
    t1 = time.time()
    probes = at.get_pb(date=tt.string_to_epoch(start))
    probes.extend(at.get_pb(is_anchor=True, date=tt.string_to_epoch(start)))
    t2 = time.time()
    logging.info("Probe query finished in %d sec." % (t2-t1))

    # save probe meta info
    with open(os.path.join(data_dir, "pb.csv"), 'w') as fp:
        fp.write("probe_id,asn_v4,asn_v6,prefix_v4,prefix_v6,is_anchor,country_code\n")
        for tup in probes:
            fp.write(','.join([str(i) for i in tup]) + '\n')

    # select only probe ids with not None IPv4 ASN or prefixes
    pb_id = [i[0] for i in probes if (i[2] is not None and i[3] is not None)]
    logging.info("%d probes with not-None v4 ASN and prefixes will be considered in data collection." % len(pb_id))

    # collect measurement for all the mid configured
    for mid in msm:
        t1 = time.time()
        id_chunks = [pb_id[i:i+100] for i in xrange(0, len(pb_id), 100)]
        chunk_count = len(id_chunks)
        pool = multiprocessing.Pool(multiprocessing.cpu_count())
        pool.map(mes_fetcher_wrapper,
                 itertools.izip(xrange(chunk_count), itertools.repeat(mid),
                                id_chunks, itertools.repeat(start), itertools.repeat(end),
                                itertools.repeat(str(mid)), itertools.repeat(data_dir)))
        t2 = time.time()
        logging.info("Measurements fetched in %d sec." % (t2-t1))


if __name__ == '__main__':
    main()

