"""
pathtools.py provides functions handling IP hops, IXP detection and ASN information.
"""
import dbtools as db
import os
import copy

cur_path = os.path.abspath(os.path.dirname(__file__))

as_rel = db.AsRelationDB(os.path.join(cur_path, "db/20161201.as-rel2.txt"))
ip2asn = db.AsnDB(main=os.path.join(cur_path, "db/ipasn.dat"),
                  reserved=os.path.join(cur_path, "db/reserved_ip.txt"))
ixp_pref = db.IxpPrefixDB(os.path.join(cur_path, "db/ixp_prefixes.txt"))
ixp_member = db.IxpMemberDB(os.path.join(cur_path, "db/ixp_membership.txt"))


def get_ip_info(ip):
    """Query the ASN and IXP information for a given IP address from various data source

    Args:
        ip (string): ip address, e.g. '129.250.66.33'

    Returns:
        addr (db.Addr): Addr object, with addr_type attribute set

    """
    # first check if it is IXP interconnection
    addr = ixp_member.lookup_interco(ip)
    if addr is None:
        # then check if it belongs to a certian IXP prefix
        ixp = ixp_pref.lookup(ip)
        if ixp is not None:
            addr = db.Addr(addr=ip, addr_type=db.AddrType.IxpPref, ixp=ixp)
        else:  # finally check if can be found from ip2asn db
            asn = ip2asn.lookup(ip)
            if type(asn) is int:  # if int then returns ASN
                addr = db.Addr(addr=ip, addr_type=db.AddrType.Normal, asn=asn)
            else:  # other type either string for reserved IP blocks or none for not found
                addr = db.Addr(addr=ip, addr_type=db.AddrType.Others, desc=asn)
    return addr


def bridge(path):
    """given a sequence of IP hops, identify sub-sequences without ASN, and remove only those IPs other than
    IXP IPs if the the ASes wrapping the sub-sequence have known relation ship

    Args:
        path (list of dbtools.Addr): a path composed of IP hops; sub-sequence without ASN can be composed of
        IP hops of dbtools.AddrType.IxpPref or dbtools.AddrType.Others.

    Return:
        list of dbtools.Addr
    """
    remove_flag = [False] * len(path)  # hop flag to one meant to be removed
    asn_path = [hop.asn for hop in path]
    holes = find_holes(asn_path)  # indexes of None (ASN) sub-sequences
    last_idx = len(path) - 1
    for start, end in holes:
        # only check the sub-sequences having type dbtools.AddrType.Others hops
        if start > 0 and end < last_idx and db.AddrType.Others in [hop.type for hop in path[start:end+1]]:
            # if there is known relation between the two ASes wrapping the None sub-sequence
            left_asn = path[start-1].asn
            right_asn = path[end+1].asn
            if left_asn == right_asn or as_rel.has_relation((left_asn, right_asn)) is not None:
                # remove only the hop of type dbtools.AddrType.Others
                for idx in range(start, end+1):
                    if path[idx].type == db.AddrType.Others:
                        remove_flag[idx] = True
    return [path[idx] for idx in range(last_idx+1) if not remove_flag[idx]]


def find_holes(x):
    """find the begining and end of continuous None in the given iterator

    Args:
        x (iterator): the input sequence

    Returns:
        list of (int, int) indicating the beginning and the end of a continuous None sub-sequence
    """
    holes = []
    in_hole = False
    for idx, val in enumerate(x):
        if not in_hole:
            if val is None:
                start = idx
                in_hole = True
        else:
            if val is not None:
                end = idx - 1
                in_hole = False
                holes.append((start, end))
    # in case the iteration ends while still in hole
    # test_case = [None, 1, 1, None, 1, None, None, None, 1, None]
    if in_hole:
        holes.append((start, idx))
    return holes


def insert_ixp(path):
    """insert IXP hops according to the presence of IXP address and IXP memebership of surrounding AS

    Args:
        path (list of db.Addr): a list of hops

    Returns:
        list of db.Addr
    """
    path_len = len(path)
    ixp_insertion = []
    for idx, hop in enumerate(path):
        if (hop.type == db.AddrType.InterCo or hop.type == db.AddrType.IxpPref) and (0 < idx < path_len-1):
            # Normal - Interco/IxpPref - Normal
            if path[idx-1].type == db.AddrType.Normal and path[idx+1].type == db.AddrType.Normal:
                left_hop = path[idx-1]
                right_hop = path[idx+1]
                # Normal - Interco - Normal
                if hop.type == db.AddrType.InterCo:
                    # ASN: A - A - A -> A - A - A
                    if left_hop.get_asn() == hop.get_asn() == right_hop.get_asn():
                        pass
                    # ASN: A - A - B -> A - A - IXP - B
                    elif left_hop.get_asn() == hop.get_asn() != right_hop.get_asn():
                        ixp_insertion.append((idx+1, hop.ixp))
                    # ASN: A - B - B -> A - IXP - B - B
                    elif left_hop.get_asn() != hop.get_asn() == right_hop.get_asn():
                        ixp_insertion.append((idx, hop.ixp))
                    # ASN: A - B - C
                    elif left_hop.get_asn() != hop.get_asn() != right_hop.get_asn():
                        # check IXP member ship
                        left_is_member = ixp_member.is_member(ixp=hop.ixp, asn=left_hop.asn)
                        right_is_member = ixp_member.is_member(ixp=hop.ixp, asn=right_hop.asn)
                        # IXP membership: A -m- B -m- C -> A - IXP - B - IXP - C
                        if left_is_member and right_is_member:
                            ixp_insertion.append((idx, hop.ixp))
                            ixp_insertion.append((idx+1, hop.ixp))
                        # IXP membership: A -m- B - C -> A - IXP - B - C
                        elif left_is_member:
                            ixp_insertion.append((idx, hop.ixp))
                        # IXP membership: A - B -m- C -> A - B - IXP - C
                        elif right_is_member:
                            ixp_insertion.append((idx + 1, hop.ixp))
                        else:
                            pass  # in this case no IXP hop will be seen in the path
                # Normal - IxpPref - Normal
                elif hop.type == db.AddrType.IxpPref:
                    left_is_member = ixp_member.is_member(ixp=hop.ixp, asn=left_hop.asn)
                    right_is_member = ixp_member.is_member(ixp=hop.ixp, asn=right_hop.asn)
                    # IXP membership: A -m- IxpPref -m- B -> A - IXP - IxpPref - IXP - B
                    if left_is_member and right_is_member:
                        ixp_insertion.append((idx, hop.ixp))
                        ixp_insertion.append((idx + 1, hop.ixp))
                    # IXP membership: A -m- IxpPref- B -> A - IXP - IxpPref - B
                    elif left_is_member:
                        ixp_insertion.append((idx, hop.ixp))
                    # IXP membership: A - IxpPref -m- B -> A - IxpPref- IXP - B
                    elif right_is_member:
                        ixp_insertion.append((idx + 1, hop.ixp))
                    else:
                        pass  # in this case no IXP shop shall be seen in the path
            # Interco/IxpPref - Inter/IxpPref
            elif path[idx+1].type == db.AddrType.InterCo or path[idx+1].type == db.AddrType.IxpPref:
                # belong to same IXP
                if path[idx].ixp == path[idx+1].ixp:
                    ixp_insertion.append((idx + 1, hop.ixp))
                else:
                    ixp_insertion.append((idx, hop.ixp))
                    ixp_insertion.append((idx+1, path[idx+1].ixp))
    shift = 0
    for ins in ixp_insertion:
        path.insert(ins[0]+shift, db.Addr(addr=None, addr_type=db.AddrType.Virtual, ixp=ins[1]))
        shift += 1
    return path


def remove_repeated_asn(path):
    """ remove repeated ASN in the give path

    Args:
        path (list of ASN): ASN can be int for str if IXP hop

    Returns:
        list of ASN
    """
    removed = []
    for idx, hop in enumerate(path):
        if idx == 0:
            removed.append(hop)
        elif hop != path[idx-1]:
            removed.append(hop)
    return removed


def as_path_change(paths):
    """ mark the idx at which AS path changes

    Args:
        paths (list of list of ASN): [[ASN,...],...]

    Returns:
        list of int, index of change is set to 1, otherwise 0
    """
    change = [0] * len(paths)
    for idx, path in enumerate(paths):
        if idx > 0:
            if path != paths[idx-1]:
                change[idx] = 1
    return change


class IpForwardingPattern:

    def __init__(self, size, paris_id=None, paths=None):
        self.pattern = [None] * size
        if paris_id is not None and paths is not None:
            assert len(paris_id) == len(paths)
            for pid, path in zip(paris_id, paths):
                    self.pattern[pid] = path

    def update(self, paris_id, path):
        assert paris_id < len(self.pattern)
        if self.pattern[paris_id] is None:
            self.pattern[paris_id] = path
            return True
        elif self.pattern[paris_id] == path:
            return True
        else:
            return False

    def is_complete(self):
        return not None in self.pattern

    def is_match(self, paris_id, paths):
        for pid, path in zip(paris_id, paths):
            if self.pattern[pid] != path:
                return False
        return True

    def __repr__(self):
        return "IpForwardingPattern(%r)" % dict(enumerate(self.pattern))

    def __str__(self):
        return "%s" % dict(enumerate(self.pattern))

    def __hash__(self):
        return hash(self.__repr__())

    def __eq__(self, other):
        return self.__repr__() == other.__repr__()


class PatternSegment:
    def __init__(self, begin, end, pattern):
        self.begin = begin
        self.end = end
        self.pattern = pattern

    def get_len(self):
        return self.end - self.begin + 1

    def __repr__(self):
        return "PatternSegment(begin=%r, end=%r, pattern=%r)" % (self.begin, self.end, self.pattern)

    def __str__(self):
        return "(%r, %r, pattern=%s)" % (self.begin, self.end, self.pattern)

    def __hash__(self):
        return hash(self.__repr__())

    def __eq__(self, other):
        return self.__repr__() == other.__repr__()


def ip_path_change_simple(paris_id, paths, size=16):
    """ given paris_id and path, detect when ip path experienced a change

    Args:
        paris_id (list of int): Paris ID used when tracerouting
        paths (list of list of IP hops): IP hops are just plein string of IP address
        size (int): number of different paris_ids

    Returns:
        list of int, index of change is set to 1, otherwise 0
    """
    assert (len(paris_id) == len(paths))
    seg = []
    cur_seg = PatternSegment(begin=0, end=0, pattern=IpForwardingPattern(size))
    for idx, (pid, path) in enumerate(zip(paris_id, paths)):
        if cur_seg.pattern.update(pid, path):
            cur_seg.end = idx
        else:
            seg.append(cur_seg)
            cur_seg = PatternSegment(begin=idx, end=idx, pattern=IpForwardingPattern(size))
            cur_seg.pattern.update(pid, path)
    if cur_seg not in seg:
        seg.append(cur_seg)
    return seg


def ip_path_change_heuristics(paris_id, paths, size=16):

    seg = ip_path_change_simple(paris_id, paths, size)  # simple segmentation

    for idx, s in enumerate(seg[:-1]):
        next_s = seg[idx + 1]
        # | cur seg |<-  next seg  | extend later segment while possible
        # |  cur seg ->|  next seg | is not possible
        if next_s.pattern.is_complete() and next_s.get_len() >= 2 * size and next_s.get_len() > s.get_len():
            next_s_cp = copy.deepcopy(next_s)
            cur_s_cp = copy.deepcopy(s)
            pos = cur_s_cp.end
            while True:
                # can be extended <-
                if next_s.pattern.update(paris_id[pos], paths[pos]):
                    cur_s_cp.end = pos - 1
                    cur_s_cp.pattern = IpForwardingPattern(size,
                                                           paris_id[cur_s_cp.begin:cur_s_cp.end+1],
                                                           paths[cur_s_cp.begin:cur_s_cp.end+1])
                    next_s_cp.begin = pos
                    pos -= 1
                else:
                    break
            # if extended, change the previous segmentation
            if cur_s_cp != s:
                seg[idx] = cur_s_cp
                seg[idx+1] = next_s_cp

    # find relatively popular IpForwarding pattern
    long_pat = [s.pattern for s in seg if s.get_len() > 2*size]
    print "Long patterns: %s" % long_pat
    split = dict()
    split_seg = []
    # try to further split short segments by finding longest match with popular pattern
    for idx, s in enumerate(seg):
        if s.get_len() < 2 * size:
            print "short seg: %s" % s
            max_len_per_pos = []
            # iterate over all the idx as starting point in the short segment
            # and store the longest match with popular patterns
            for pos in range(s.begin, s.end):
                print "check %r" % pos
                l = 2  # starting from match length 2
                # TODO: for seg at last, shall not surpass the total length
                while True:
                    pt_count = 0 # the number of  matched long pattern
                    for lp in long_pat:
                        if lp.is_match(paris_id[pos:pos+l], paths[pos:pos+l]):
                            pt_count += 1
                    if pt_count: # if pos:pos+l matches at least one long pattern, further extend the length
                        l += 1
                    else:  # record last successful try
                        max_len_per_pos.append((pos, l-1))
                        print "\t %d, %d" % (pos, l-1)
                        break
            max_len_per_pos = sorted(max_len_per_pos, key=lambda e: e[1], reverse=True)
            longest_cut = max_len_per_pos[0]
            if longest_cut[1] > 1:  # only if the length of the longest cut is > 1
                print "Split"
                print longest_cut
                split[idx] = longest_cut

    for idx, s in enumerate(seg):
        if idx in split:
            cut_begin = split[idx][0]
            cut_end = cut_begin + split[idx][1] - 1
            # cut the segment
            if cut_begin == s.begin:
                split_seg.append(PatternSegment(begin=cut_begin,
                                                end=cut_end,
                                                pattern=IpForwardingPattern(size,
                                                                            paris_id[cut_begin:cut_end + 1],
                                                                            paths[cut_begin:cut_end + 1])))
                split_seg.append(PatternSegment(begin=cut_end + 1,
                                                end=s.end,
                                                pattern=IpForwardingPattern(size,
                                                                            paris_id[cut_end + 1:s.end + 1],
                                                                            paths[cut_end + 1:s.end + 1])))
            elif cut_begin > s.begin and cut_end < s.end:
                split_seg.append(PatternSegment(begin=s.begin,
                                                end=cut_begin - 1,
                                                pattern=IpForwardingPattern(size,
                                                                            paris_id[s.begin:cut_begin],
                                                                            paths[s.begin:cut_begin])))
                split_seg.append(PatternSegment(begin=cut_begin,
                                                end=cut_end,
                                                pattern=IpForwardingPattern(size,
                                                                            paris_id[cut_begin:cut_end + 1],
                                                                            paths[cut_begin:cut_end + 1])))
                split_seg.append(PatternSegment(begin=cut_end + 1,
                                                end=s.end,
                                                pattern=IpForwardingPattern(size,
                                                                            paris_id[cut_end + 1:s.end + 1],
                                                                            paths[cut_end + 1:s.end + 1])))
            elif cut_end == s.end:
                split_seg.append(PatternSegment(begin=s.begin,
                                                end=cut_begin - 1,
                                                pattern=IpForwardingPattern(size,
                                                                            paris_id[s.begin:cut_begin],
                                                                            paths[s.begin:cut_begin])))
                split_seg.append(PatternSegment(begin=cut_begin,
                                                end=cut_end,
                                                pattern=IpForwardingPattern(size,
                                                                            paris_id[cut_begin:cut_end + 1],
                                                                            paths[cut_begin:cut_end + 1])))
        else:
            split_seg.append(s)

    return split_seg
