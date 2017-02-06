"""
pathtools.py provides functions handling IP hops, IXP detection and ASN information.
"""
import dbtools as db
import os
import copy
import logging

# load database from the local folder
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
    """find the beginning and end of continuous None in the given iterator

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
    """IpForwardingPattern describes the forwarding paths for all the paris-id in joining one destination

    Attributes:
        pattern (list of path): index of the list is the paris id; the element is a path composed of hops
    """
    # TODO: specify the data type for path; make sure that it can be compared to each other
    def __init__(self, size, paris_id=None, paths=None):
        """Initialize with size that the number of different paris id and optionally with paths taken by paris id

        Args:
            size (int): number of different paris id, in the case of RIPE Atlas, it is 16
            paris_id (list of int): sequence of paris id
            paths (list of path): path taken when the corresponding paris id in the paris_id list is used
        """
        self.pattern = [None] * size
        if paris_id is not None and paths is not None:
            # NOTE: if a paris_id have different paths is not checked here
            assert len(paris_id) == len(paths)
            for pid, path in zip(paris_id, paths):
                    self.pattern[pid] = path

    def update(self, paris_id, path):
        """update/complete the current pattern with new paris id and path taken

        Return True if the input can be integrated into the existing pattern; False otherwise

        Args:
            paris_id (int): one single paris id
            path (a path): a path taken by the paris id

        Returns:
            boolean
        """
        assert paris_id < len(self.pattern)
        # if the paris id has not yet path set, the input can always be integrated into existing pattern
        if self.pattern[paris_id] is None:
            self.pattern[paris_id] = path
            return True
        elif self.pattern[paris_id] == path:
            return True
        else:
            return False

    def is_complete(self):
        """test if the pattern has path set for each paris id"""
        return None not in self.pattern

    def is_match(self, paris_id, paths):
        """test if the input paris ids and paths are compatible with existing pattern

        the difference with self.update() is that, is_match won't modify self.pattern is a paris id is not yet set

        Args:
            paris_id (list of int)
            paths (list of path)

        Returns:
            boolean
        """
        for pid, path in zip(paris_id, paths):
            if self.pattern[pid] is not None and path is not None and self.pattern[pid] != path:
                return False
        return True

    def is_match_pattern(self, pattern):
        """test if the input IpForwarding pattern is compatible with existing pattern

        a variation of self.is_match()

        Returns:
            boolean
        """
        if len(pattern.pattern) != len(self.pattern):
            return False
        else:
            return self.is_match(range(len(pattern.pattern)), pattern.pattern)

    def __repr__(self):
        return "IpForwardingPattern(%r)" % dict(enumerate(self.pattern))

    def __str__(self):
        return "%s" % dict(enumerate(self.pattern))

    def __hash__(self):
        return hash(self.__repr__())

    def __eq__(self, other):
        return self.__repr__() == other.__repr__()


class PatternSegment:
    """PatternsSegment describes a subsequence of paths following a same IpFowardingPattern

    Attributes:
        begin (int): the beginning index of the path segment;
                     only meaningful when you know the sequence of paris_id and paths; the same for end
        end (int): the index if last path of the segment, thus inclusive
        pattern (IpForwardingPattern): the pattern followed by this segment
    """
    def __init__(self, begin, end, pattern):
        self.begin = begin
        self.end = end
        self.pattern = pattern

    def get_len(self):
        """return the length of the segment"""
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
    """given a sequence paris_id and path, detect when a different path is take for a same paris id

    the functions cuts the given paths sequence into segments where each following a same IpForwardingPattern

    Args:
        paris_id (list of int): Paris ID used when tracerouting
        paths (list of path): path is composed of ip hops
        size (int): number of different paris_ids

    Returns:
        list of PatternSegment
    """
    assert (len(paris_id) == len(paths))
    seg = []
    cur_seg = PatternSegment(begin=0, end=0, pattern=IpForwardingPattern(size))
    for idx, (pid, path) in enumerate(zip(paris_id, paths)):
        if cur_seg.pattern.update(pid, path):
            cur_seg.end = idx
        else:
            # once a paris id and the path take is not longer compatible with the current segment
            # start a new segment
            seg.append(cur_seg)
            cur_seg = PatternSegment(begin=idx, end=idx, pattern=IpForwardingPattern(size))
            cur_seg.pattern.update(pid, path)
    # store the last segment
    if cur_seg not in seg:
        seg.append(cur_seg)
    return seg


def ip_path_change_bck_ext(paris_id, paths, size=16):
    """ maximize longest path segment with backward extension

    after the ip_path_change_simple() extends segment in -> direction;
    this function further checks if the longer segment of the two neighbouring ones
    can be further extended in <- direction

    the intuition behind is that most time measurement flows on dominant patterns

    Args:
        paris_id (list of int): Paris ID used when tracerouting
        paths (list of path): path is composed of ip hops
        size (int): number of different paris_ids

    Returns:
        list of PatternSegment
    """

    seg = ip_path_change_simple(paris_id, paths, size)  # simple segmentation

    for idx, s in enumerate(seg[:-1]):
        next_s = seg[idx + 1]
        # | cur seg |<-  next seg  | extend later
        # |  cur seg ->|  next seg | is already done with simple segmentation
        # next segment can only be backwardly extended if:
        # it's pattern is complete
        # it's pattern has been repeated twice so that we are sure that it is a stable pattern
        # it is longer than the previous pattern so that we maximizes the longest pattern
        if next_s.pattern.is_complete() and next_s.get_len() >= 2 * size and next_s.get_len() > s.get_len():
            next_s_cp = copy.deepcopy(next_s)
            cur_s_cp = copy.deepcopy(s)
            pos = cur_s_cp.end
            while True:
                # test if can be backwardly extended
                if next_s.pattern.update(paris_id[pos], paths[pos]):
                    cur_s_cp.end = pos - 1
                    cur_s_cp.pattern = IpForwardingPattern(size,
                                                           paris_id[cur_s_cp.begin:cur_s_cp.end+1],
                                                           paths[cur_s_cp.begin:cur_s_cp.end+1])
                    next_s_cp.begin = pos
                    pos -= 1
                else:
                    break
            # if extended, change the both segments
            if cur_s_cp != s:
                seg[idx] = cur_s_cp
                seg[idx+1] = next_s_cp
    return seg


def ip_path_change_split(paris_id, paths, size):
    """pattern change detection with finer granilarity

    for segments with short length, < 2 * size, chances are that there is a short deviation inside
    while backward extension might find the end of the short deviation but not necessary the beginning,
    thus the need for further finer split.

    the intuition is that if a short segment have a sub-segment at 2 in length that matches with same popular patterns
    we further split the short segment

    Args:
        paris_id (list of int): Paris ID used when tracerouting
        paths (list of path): path is composed of ip hops
        size (int): number of different paris_ids

    Returns:
        list of PatternSegment
    """

    seg = ip_path_change_bck_ext(paris_id, paths, size)
    # find relatively popular IpForwarding pattern: any patter that ever lasts more than 2 paris id iteration
    # not different segment can have same pattern at different places in the path sequences
    long_pat = set([s.pattern for s in seg if s.get_len() > 2*size])
    # {idx:(position, length)}
    # idx: the idx of seg to be split
    # position and length of the longest sub-segment that matches popular patterns
    split = dict()
    # new segmentation after split
    split_seg = []

    # try to further split short segments by finding the longest sub-segment that matches with popular patterns
    for idx, s in enumerate(seg):
        # the segment should at least 3 in length and it's pattern has not been repeated
        # and it's pattern doesn't match with any of the popular ones
        if 2 < s.get_len() < 2 * size:
            any_match = False
            for lp in long_pat:
                if lp.is_match_pattern(s.pattern):
                    any_match = True
            if not any_match:
                max_len_per_pos = []
                # iterate over all the idx from the begining to one before last of the short segment
                # and store the longest match with popular patterns for each position
                for pos in range(s.begin, s.end):
                    l = 2  # starting from match length 2
                    while pos+l <= s.end+1:  # iterate till the end of current segment
                        any_match = False  # the number of  matched long pattern
                        for lp in long_pat:
                            if lp.is_match(paris_id[pos:pos+l], paths[pos:pos+l]):
                                any_match = True
                                break
                        if any_match:  # if pos:pos+l matches at least one long pattern, further extend the length
                            l += 1
                        else:  # record last successful try
                            max_len_per_pos.append((pos, l-1))
                            break
                # this is case when the end of sub-segment reaches the end of the short segment
                if (pos, l-1) not in max_len_per_pos:
                        max_len_per_pos.append((pos, l-1))

                max_len_per_pos = sorted(max_len_per_pos, key=lambda e: e[1], reverse=True)
                longest_cut = max_len_per_pos[0]
                if longest_cut[1] > 1:  # further split only if the length of the longest match > 1 in length
                    split[idx] = longest_cut

    # split the segments
    for idx, s in enumerate(seg):
        if idx in split:
            cut_begin = split[idx][0]
            cut_end = cut_begin + split[idx][1] - 1
            # three possible cases: 1/ at match at beginning; 2/ the match in the middle; 3/ the match at the end
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

    # after the above split, the new neighbouring segments could again math popular pattern, merge them
    # {idx: new segment}
    # idx: the first idx of the two neighbour segment in split_seg that meant to be merged
    # maps to the new merged segment
    merge = dict()
    for idx, s in enumerate(split_seg[:-1]):
        next_s = split_seg[idx+1]
        # if the two neighbour segments are short test if them can be merged
        if s.get_len() < 2 * size or next_s.get_len() < 2 * size:
            # if the neighbouring seg matches with each other then test if merged seg matches with popular pattern
            if s.pattern.is_match_pattern(next_s.pattern):
                merge_pat = IpForwardingPattern(size, paris_id[s.begin:next_s.end+1], paths[s.begin:next_s.end+1])
                any_match = False
                for lp in long_pat:
                    if lp.is_match_pattern(merge_pat):
                        any_match = True
                        break
                if any_match:
                    merge[idx] = PatternSegment(begin=s.begin, end=next_s.end, pattern=merge_pat)

    # in general consecutive merge, e.g. 1 merge 2 and 2 merge 3,  is not possible
    # log it when happens
    for i in merge:
        if i+1 in merge:
            logging.error("IP change split: consecutive merge possible: %r, %r" % (paris_id, paths))
            return split_seg

    mg_seg = []
    for idx, seg in enumerate(split_seg):
        if idx in merge:
            mg_seg.append(merge[idx])
        elif idx not in merge and idx-1 not in merge:
            mg_seg.append(seg)
    return mg_seg


def ifp_change(seg, seq_len):
    """ mark the idx at which IpForwardingPattern changes, i.e. the beginning of a new segment

        Args:
            seg (list of PatternSegment): the out put of ifp change detection algos
            seq_len: the total length of the path sequence

        Returns:
            list of int, index of change is set to 1, otherwise 0
        """
    change = [0] * seq_len
    if len(seg) > 1:
        for s in seg[1:]:
            change[s.begin] = 1
    return change
