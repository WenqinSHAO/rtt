from ripe.atlas.cousteau import AtlasResultsRequest, ProbeRequest
from error import MES_ERR, TIMEOUT_ERR, UNKNOWN_ERR, LATE_ERR, IP_ERR
import logging
import timetools as tt


def get_pb(pb_tag="system-v3", is_anchor=False, date=None, asn=None):
    """ fetch atlas probe/anchors hosted by a given asn

    Args:
        pb_tag (string) : firmware version of probes, not applied to anchors
        is_anchor (bool) : if set to True, anchors will be selected instead of normal probes
        date (int) : sec since epoch
        asn (int) :  Autonomous System Number, default to None, all probes will be fetched

    Returns:
        pb_id (list of tuple): [(id, asn_v4, ans_v6,...),]

    Notes:
        By default only v3 probes are selected.
        pb_tag parameter can be changed to select other probes.
    """

    if is_anchor:
        filters = dict(is_anchor=True)
    else:
        filters = dict(tags=pb_tag)
    if asn:
        filters['asn_v4'] = asn
    probes = ProbeRequest(**filters)
    pb_id = []
    for pb in probes:
        if date:
            if pb["first_connected"] and pb["first_connected"] <= date:
                pb_id.append((pb["id"], pb['asn_v4'], pb['asn_v6'],
                              pb['prefix_v4'], pb['prefix_v6'], pb['is_anchor'], pb['country_code']))
        else:
            pb_id.append((pb["id"], pb['asn_v4'], pb['asn_v6'],
                          pb['prefix_v4'], pb['prefix_v6'], pb['is_anchor'], pb['country_code']))

    return pb_id


def get_ms_by_pb_msm_id(msm_id, pb_id, start, end):
    """ fetch atlas measurements by measurement id and probe id.

    Args:
        msm_id (int): list of measurement ids
        pb_id (list of int): list of probe ids
        start (datetime): start time of the measurement
        end (datetime): stop time of the measurement

    Returns:
       dict of list : key is the probe id in int, item is a list of dict, each dict being
        an Atlas measurement parsed with sagon
    """
    filters = {"msm_id": msm_id,
               "probe_ids": pb_id,
               "start": start,
               "stop": end}
    is_success, results = AtlasResultsRequest(**filters).create()
    # results here is a list of dict, each dict is a measurement in JSON format
    if is_success:
        return group_by_probe(results)


def group_by_probe(results):
    """ Given a list of Atlas measurements in JSON format, parse them and group them by probe id
    The original JSON format of measurement format is very lengthy and takes place.
    group_by_probe first parse the original format into a more compact one

    Args:
        results (list of dict): each dict is an Atlas measurement in JSON format

    Returns:
        by_probe (dict) : key is the probe id in int, item is a dict
        if ping: dict(epoch=[int], min_rtt=[float], all_rtt=[tuple of float])
        if connection: dict(connect=[int], disconnect=[int])
        if traceroute: dict(epoch=[int], paris_id=[int], path=[tuple of hops])

    NOTE:
        assume that for each probe, there is only one type of measurement
    """
    by_probe = dict()
    for mes in results:
        probe_id = mes.get('prb_id', -1)
        type_ = mes.get('type', None)
        if probe_id not in by_probe:
            if type_ == 'ping':
                by_probe[probe_id] = dict(epoch=[], min_rtt=[], all_rtt=[])
            elif type_ == 'connection':
                by_probe[probe_id] = dict(connect=[], disconnect=[])
            elif type_ == 'traceroute':
                by_probe[probe_id] = dict(epoch=[], paris_id=[], path=[])
            else:
                logging.warning("%d had unsupported type of measurements %s" % (probe_id, str(type_)))
        if type_ == 'ping':
            parsed_mes = parser_of_ping(mes)
        elif type_ == 'connection':
            parsed_mes = parser_of_connection(mes)
        elif type_ == 'traceroute':
            parsed_mes = parser_of_trace(mes)
        else:
            logging.warning("%d had unsupported type of measurements %s" % (probe_id, str(type_)))
        for k in parsed_mes.keys():
            by_probe[probe_id][k].append(parsed_mes[k])
    return by_probe


def parser_of_connection(data):
    """ Parse the special measurement id for connection events

    Args:
        data (dict): see the following example
        {u'msm_id': 7000, u'timestamp': 1470134587, u'prefix': u'80.100.0.0/15', u'event': u'disconnect',
        u'controller': u'ctr-ams07', u'prb_id': 15093, u'type': u'connection', u'asn': 3265}

    Returns:
        dict, event name as key, either disconnect or connect, timestamp as value
    """
    event = data.get('event', None)
    tstp = data.get('timestamp', None)
    return {str(event): tstp}


def parser_of_ping(data):
    """ Given a dict of ping measurement, extract only the timestamp and rtt values

    Args: data (dict): {u'af': 4, u'prb_id': 11768,
    u'result': [{u'rtt': 199.323625}, {u'rtt': 199.38607}, {u'rtt': 199.28052}],
    u'ttl': 48, u'avg': 199.3300716667, u'size': 20, u'from': u'78.238.122.61',
    u'proto': u'ICMP', u'timestamp': 1470014924, u'dup': 0, u'type': u'ping', u'sent': 3,
    u'msm_id': 1010, u'fw': 4730, u'max': 199.38607, u'step': 240, u'src_addr': u'192.168.1.4',
    u'rcvd': 3, u'msm_name': u'Ping', u'lts': 28, u'dst_name': u'192.228.79.201', u'min': 199.28052,
    u'dst_addr': u'192.228.79.201'}

    Returns:
        rtt (dict): dict(epoch=integer, min_rtt=float, all_rtt=tuple of float)
    """
    pb_id = data['prb_id']
    rtt = dict()
    tstp = rtt['epoch'] = data['timestamp']
    result = data.get('result', None)
    if result:
        rtt_list = rtt_of_ping(pb_id, tstp, result)
        rtt['min_rtt'] = min_pos(rtt_list)
        rtt['all_rtt'] = tuple(rtt_list)
    else:
        rtt['min_rtt'] = None
        rtt['all_rtt'] = (None, None, None)
    return rtt


def parser_of_trace(data):
    """ Given a dict of traceroute measurement, extract timestamps, valide hops and rtts to each hop

    Args : data (dict)
    {u'af': 4,
     u'dst_addr': u'192.228.79.201', u'dst_name': u'192.228.79.201', u'endtime': 1483230652,
     u'from': u'103.7.251.180', u'fw': 4740, u'lts': 551, u'msm_id': 5010, u'msm_name': u'Traceroute',
     u'paris_id': 11, u'prb_id': 14797, u'proto': u'UDP',
     u'result': [
        {u'hop': 1, u'result':
            [{u'from': u'103.7.251.161', u'rtt': 0.509, u'size': 28, u'ttl': 255},
             {u'from': u'103.7.251.161', u'rtt': 0.459, u'size': 28, u'ttl': 255},
             {u'from': u'103.7.251.161', u'rtt': 0.457, u'size': 28, u'ttl': 255}]},
        {u'hop': 2,
        u'result':
            [{u'from': u'103.7.251.89', u'rtt': 0.7, u'size': 28, u'ttl': 254},
             {u'from': u'103.7.251.89', u'rtt': 0.582, u'size': 28, u'ttl': 254},
             {u'from': u'103.7.251.89', u'rtt': 0.571, u'size': 28, u'ttl': 254}]},
        ...
        {u'hop': 7, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 8, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 9, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 10, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 11, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 255, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]}],
     u'size': 40,
     u'src_addr': u'103.7.251.180',
     u'timestamp': 1483230639,
     u'type': u'traceroute'}

    Returns:
        trace (dict) : dict(epoch=int, paris_id=int, path=tuple of hops)
        each hop is a tuple of (hop count int, from IP address string, tuple of RTTs)
        the above example will be parsed into:
        {'epoch' : 1483230639, 'paris_id' : 11,
         'path' : ((1, '103.7.251.161', 0.457),
                   (2, '103.7.251.89', 0.571),
                                 ...
                   (7, 'x', -3),  # -3 is the error code for ICMP timeout
                   (8, 'x', -3),
                                 ...
                   (255, 'x', -3))}
    """
    pb_id = data['prb_id']
    trace = dict()
    tstp = trace['epoch'] = data['timestamp']
    trace['paris_id'] = data.get('paris_id', None)
    result = data.get('result', None)
    if result:
        trace['path'] = hops_of_trace(pb_id, tstp, result)
    else:
        trace['path'] = None
    return trace


def rtt_of_ping(pb_id, tstp, results):
    """ given the result field of a ping measurement (PingResult), extract its RTT values

     Args:
         pb_id (int) : probe that performed measurement in the results parameter
         tstp (int) : the epoch time of the measurement in the results parameter
         results (list of dict): [{u'rtt': 199.323625}, {u'rtt': 199.38607}, {u'rtt': 199.28052}];
         [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}];
         [{u'error': u'connect failed: Network is unreachable'}]

    Returns:
        rtt_in_res (list): invalid RTT measurement is translated into special negative code
        [199.32, 199.38, 199.28], [-3, -3, -3]
    """
    rtt_in_res = []
    for res in results:
        for key, value in res.items():
            if key == 'error':
                if 'unreachable' in value:
                    rtt_in_res.append(MES_ERR)
                else:
                    logging.warning(
                        "%d had measurement error other than unreachable at %s" % (pb_id, tt.epoch_to_string(tstp)))
                    rtt_in_res.append(MES_ERR)
            elif key == 'x':
                rtt_in_res.append(TIMEOUT_ERR)
            elif key == 'rtt':
                rtt_in_res.append(float(value))
            else:
                logging.warning("%d had unexpected key %s in results at %s" % (pb_id, key, tt.epoch_to_string(tstp)))
                rtt_in_res.append(UNKNOWN_ERR)
    return rtt_in_res


def hops_of_trace(pb_id, tstp, results):
    """ given the result field of a traceroute measurement in the result parameter, extract the hops and RTTs

    Args:
        pb_id (int) : probe that performed measurement in the results parameter
        tstp (int) : the epoch time of the measurement in the results parameter
        results (list of dict):
        [
        {u'hop': 1, u'result':
            [{u'from': u'103.7.251.161', u'rtt': 0.509, u'size': 28, u'ttl': 255},
             {u'from': u'103.7.251.161', u'rtt': 0.459, u'size': 28, u'ttl': 255},
             {u'from': u'103.7.251.161', u'rtt': 0.457, u'size': 28, u'ttl': 255}]},
        {u'hop': 2,
        u'result':
            [{u'from': u'103.7.251.89', u'rtt': 0.7, u'size': 28, u'ttl': 254},
             {u'from': u'103.7.251.89', u'rtt': 0.582, u'size': 28, u'ttl': 254},
             {u'from': u'103.7.251.89', u'rtt': 0.571, u'size': 28, u'ttl': 254}]},
        ...
        {u'hop': 7, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 8, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 9, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 10, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 11, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]},
        {u'hop': 255, u'result': [{u'x': u'*'}, {u'x': u'*'}, {u'x': u'*'}]}]

    Return:
        hops (tuple of tuples):
        ((1, '103.7.251.161', 0.457),
         (2, '103.7.251.89', 0.572),
                                 ...
         (7, 'x', -3),  # -3 is the error code for ICMP timeout
         (8, 'x', -3),
                                 ...
         (255, 'x', -3))
    """
    hops = []
    for rec in results:
        if 'hop' in rec:
            n_hop = rec['hop']
        else:
            n_hop = None
            logging.warning(
                "%d had a traceroute measurement without hop field at %s" % (pb_id, tt.epoch_to_string(tstp)))

        if 'result' in rec:
            from_ip, rtt = get_hop(pb_id, tstp, rec['result'])
            hops.append((n_hop, from_ip, rtt))  # normal return cases
        elif 'error' in rec:
            hops.append((n_hop, IP_ERR, MES_ERR))
            logging.warning("%d had measurement error at %s : %s" % (pb_id, tt.epoch_to_string(tstp), rec['error']))
        else:
            hops.append((n_hop, IP_ERR, UNKNOWN_ERR))
            logging.warning(
                "%d had a traceroute measurement without error or result field at %s" % (pb_id, tt.epoch_to_string(tstp)))
    return tuple(hops)


def get_hop(pb_id, tstp, hop_result):
    """" given the result field of a single hop in traceroute measurement, get the hop IP and RTT

    Args:
        pb_id (int) : probe that performed measurement in the results parameter
        tstp (int) : the epoch time of the measurement in the results parameter
        hop_result (list of dict): one single hop in traceroute
        [{u'from': u'103.7.251.161', u'rtt': 0.509, u'size': 28, u'ttl': 255},
         {u'from': u'103.7.251.161', u'rtt': 0.459, u'size': 28, u'ttl': 255},
         {u'from': u'103.7.251.161', u'rtt': 0.457, u'size': 28, u'ttl': 255}]
        Multiple measurements can be made.
        Not necessary that all the hops are error free;
        Not necessary that all the hops are of same IP address

    Returns:
        IP hop (string), RTT (float)
        IP hop is the IP address that present the most times
        RTT is the smallest valid RTT associated with the IP hop
        103.7.251.161, 0.457
    """
    mes = dict()
    for rec in hop_result:
        if 'from' in rec:
            if rec['from'] not in mes:
                mes[rec['from']] = []
            if 'rtt' in rec:
                mes[rec['from']].append(rec['rtt'])
            elif 'err' in rec:
                mes[rec['from']].append(MES_ERR)
                logging.warning(
                        "%d had traceroute measurement error at %s: %s" % (pb_id, tt.epoch_to_string(tstp), rec['err']))
            elif 'late' in rec:
                mes[rec['from']].append(LATE_ERR)
                logging.warning(
                        "%d had %d late packets in traceroute at %s" % (pb_id, rec['late'], tt.epoch_to_string(tstp)))
            else:
                mes[rec['from']].append(UNKNOWN_ERR)
                logging.warning(
                        "%d had traceroute measurement w/o rtt,err,late flied at %s" % (pb_id, tt.epoch_to_string(tstp)))
        elif 'x' in rec:
            if 'x' not in mes:
                mes['x'] = []
            mes['x'].append(TIMEOUT_ERR)

    ip_hop = sorted(mes.items(), key=lambda s: len(s[1]), reverse=True)[0][0]
    rtt = min_pos(mes[ip_hop])
    return ip_hop, rtt


def min_pos(x):
    """ return the smallest positive number in a given numeric list;
    in the case all values are negative, return the biggest one (generally the err code for timeout)
    """
    pos_x = [i for i in x if i > 0]
    if len(pos_x):
        return min(pos_x)
    else:
        return max(x)
