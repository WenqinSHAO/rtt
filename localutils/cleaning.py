from error import PING_INTV, TRACE_INTV, MISS_ERR, START, PING_LEN, TRACE_LEN
import numpy as np
import timetools as tt

# cleaning criteria
INTV_MX = 2  # the maximum tolerable consecutive connection losses, times by interval.
LEN_P = 0.9  # the minimum length portion compared to ideal case.


def interv(lst):
    """ calculate the interval of neighbouring items

    Args:
        lst (list of some numerical data)

    Returns:
        list of some numerical data
    """
    return np.array(lst[1:]) - np.array(lst[:-1])


def pltf_stab(tstp, mes_type='ping'):
    """ check if probe have stable connection to the platform

    Args:
        tstp (list of int): list of measurement timestamps in seconds since epoch
        mes_type (string): indicate the type of data to be checked, default to be ping;
        and string other than 'ping' will be treated as traceroute

    Returns:
        boolean: False means the connection is not stable
    """

    if mes_type == 'ping':
        max_intv = INTV_MX * PING_INTV
        min_length = LEN_P * PING_LEN
    else:
        max_intv = INTV_MX * TRACE_INTV
        min_length = LEN_P * TRACE_LEN

    if len(tstp) < min_length:
        return False

    mes_interval = interv(tstp)
    if np.max(mes_interval) > max_intv:
        return False

    return True


def padding(tstp, rtt, ref):
    """ align measurements to closest reference and pad missing moments with MISS_ERR code

    Args:
        tstp (list of int): initial measurement timestamps
        rtt (list of float): RTT measurements, should be of same length as tstp
        ref (list of int): reference measurement timestamps

    Returns:
        padded (np.array of float): aligned and padded RTT measurements

    """
    # aligning the tstp to the closest timestamp in ref
    # idx storing the corresponding indices in ref
    start = ref[0]
    intv = ref[1] - ref[0]
    idx = np.rint((np.array(tstp, dtype='float') - start)/intv).astype(int)
    # handle the case where tstp is mapped to an index beyond the length of ref
    idx = idx[idx < len(ref)]
    rtt = rtt[:(len(idx)-1)]
    # padding by filling
    padded = np.array([MISS_ERR]*len(ref), dtype='float')
    padded[idx] = rtt
    return padded


def ref_tstp(tstp):
    """ generate reference measurement timestamp with perfect interval

    Args:
        tstp (list of int): actual measurement timestamp

    Returns:
        ref (list of int): reference timestamp with perfect interval
    """
    head = tstp[0]
    idx = int(np.floor((head - tt.string_to_epoch(START)) / PING_INTV))
    head -= idx * PING_INTV
    ref = range(head, int(head+PING_INTV*PING_LEN), PING_INTV)
    return ref

