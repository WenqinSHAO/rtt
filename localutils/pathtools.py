import dbtools as db
import os

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

