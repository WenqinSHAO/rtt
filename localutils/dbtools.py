"""
dbtools.py provides class definitions to handle CAIDA AS relationship inference and
IXP related output from traIXroute database merge
"""
import SubnetTree
import logging
import pyasn


class IXP:
    """ IXP is a class that describes IXP

    Attributes:
        short (string): short name for IXP
        long (string): long name for IXP
        country (string): country code, for US may contain state name
        city (string): name of the city
    """

    def __init__(self, short_name, long_name, country, city):
        self.short = short_name
        self.long = long_name
        self.country = country
        self.city = city

    def __repr__(self):
        return "IXP(short=%r, long=%r, country=%r, city=%r)" % \
               (self.short, self.long, self.country, self.city)

    def __eq__(self, other):
        return self.__repr__() == other.__repr__()

    def __hash__(self):
        return hash(self.__repr__())


class AsRelation:
    """
    AsRelation describes the relation between ASes

    Attributes:
        P2C (int): -1, class attribute, provider to customer
        PEER (int): 0, class attribute, peer
        C2P (int): 1, class attrubute, customer to provider
        coder (dict): int to above attributes mapping
    """
    P2C, PEER, C2P = range(-1, 2, 1)

    @staticmethod
    def encode(number):
        """Encode a given number to one of the defined relationship

        Args:
            number (int): relation readings from CAIDA AS relationship inference

        Returns:
            int, one of the defined relationship or None
        """
        return number if number in range(-1, 2, 1) else None

    @staticmethod
    def flip(relation):
        """Change C2P to P2C, while PEER remain the same

        Args:
            relation (int): one of the defined relationship

        Returns:
            int: one of the defined relationship, or None
        """
        try:
            return AsRelation.encode(int(relation)*-1)
        except TypeError:
            return None


class AddrType:
    """AddrType enumerates the type of IP addresses

    Attributes:
        Normal (int): 100, IP address attributed to an AS by Internet Register, thus seen in routeview BGP feeds
        InterCo (int): 101, IP address attributed to an AS by IXP for interconnection in the IXP
        IxpPref (int): 102, IP address seen in the prefixes belong to certain IXP, but not clear which client ASN uses it
        Virtual (int): 103, virtual hop take by IXP insertion
        Others (int): 104, Other types, say private ones, *, or ones not seen in BGP feeds
    """
    Normal, InterCo, IxpPref, Virtual, Others = range(100, 105, 1)


class Addr:
    """Addr describes an IP address

    Attributes:
        addr (string): IP address in string, e.g. '129.250.66.33'
        type (AddrType): the type of IP address
        asn (int): AS that uses this interconnection IP address
        ixp (IXP): the IXP that attributes the IP address
    """
    def __init__(self, addr, addr_type=None, asn=None, ixp=None, desc=None):
        self.addr = addr
        self.type = addr_type
        self.asn = asn
        self.ixp = ixp
        self.desc = desc

    def __repr__(self):
        return "Addr(addr=%r, type=%r, asn=%r, ixp=%r, desc=%r)" % (self.addr, self.type, self.asn, self.ixp, self.desc)

    def __eq__(self, other):
        return self.__repr__() == other.__repr__()

    def __hash__(self):
        return hash(self.__repr__())

    def get_asn(self):
        """get the ASN or other info according to the address type

        Return:
            int, None, string
        """
        if self.type == AddrType.Normal or self.type == AddrType.InterCo:
            return self.asn
        elif self.type == AddrType.IxpPref:
            return None
        elif self.type == AddrType.Virtual:
            try:
                return self.asn if self.asn is not None else self.ixp.short
            except AttributeError as e:
                logging.warning("IXP not set for %r : %r" % (self, e))
                return None
        else:  # for reserved IP
            return self.desc


class AsnDB:
    """AsnDB provides facility to query the ASN of a given IP address

    Attributes:
        _main (pyasn): stores the IP to ASN mapping parsed by pyasn from routeview BGP feeds
            pyasn_util_download.py --latest
            pyasn_util_convert.py --single <Downloaded RIB File> <ipasn_db_file_name>
        _reserved (SubnetTree or None): stores the reserved IP blocks
    """
    def __init__(self, main, reserved=None):
        """load from file

        Args:
            main (string): path to the conversion out put of pyasn
            reserved (string): path to file recording reserved IP blocks
        """
        try:
            self._main = pyasn.pyasn(main)
        except (IOError, RuntimeError) as e:
            logging.critical("Encountered error when initializing IP to ASN DB: %s" % e)

        if reserved is not None:
            self._reserved = SubnetTree.SubnetTree()
            try:
                with open(reserved, 'r') as fp:
                    for line in fp:
                        if not line.startswith('#') and len(line.split()) >= 2:
                            pref, desc = [i.strip() for i in line.split()]
                            self._reserved.insert(pref, desc)
            except IOError as e:
                logging.critical("Encountered error when initializing IP to ASN DB: %s" % e)
        else:
            self._reserved = None

    def lookup(self, addr):
        """look up the ASN or description of given IP address

        Args:
            addr (string): IP address, e.g. e.g. '129.250.66.33'

        Return:
            string if reserved or invalid IP address, int if an ASN is retrieved
        """
        try:
            return self._reserved[addr]
        except (TypeError, KeyError):
            try:
                return self._main.lookup(addr)[0]
            except ValueError:
                return 'Invalid IP address'


class IxpPrefixDB:
    """
    IxpPerfixDB provides searching facilities for IP prefixes belonging to IXPs

    Attributes:
        _pt (SubnetTree): prefix as key, IXP instance as value
    """
    def __init__(self, fn):
        """Initializes from traIXroute database merge output ixp_prefixes.txt

        Args:
            fn (string): path to the traIXroute db merge output ixp_prefixes.txt
        """
        self._pt = SubnetTree.SubnetTree()
        try:
            with open(fn, 'r') as fp:
                for line in fp:
                    # only read line with ! flags
                    if len(line.split(',')) == 7:
                        _, flag, pref, short_name, long_name, country, city = [i.strip() for i in line.split(',')]
                        if flag == '!':
                            self._pt.insert(pref,
                                            IXP(short_name=short_name, long_name=long_name, country=country, city=city))
        except IOError as e:
            logging.critical("Encountered error when initializing IXP prefix DB: %s" % e)

    def lookup(self, addr):
        """Lookup a given IP address if it belongs to an IXP

        Args:
            addr (string): IP address

        Returns:
            IXP or None if no IXP contains the queried IP address
        """
        try:
            return self._pt[addr]
        except KeyError:
            return None


class AsRelationDB:
    """AsRelationDB provides searching facilities for CAIDA AS relationship inference

    Attributes:
        _relation (dict): asn pair tuple to int, i.e. relationships defined in AsRelation class
    """
    def __init__(self, fn):
        """Initializes from the CAIDA AS relationship inference *.as-rel2.txt

        Args:
            fn (string): path to CAIDA AS relationship inference file
        """
        self._relation = dict()
        try:
            with open(fn, 'r') as fp:
                for line in fp:
                    # skip line begin with '#'
                    if not line.startswith('#'):
                        rel = [i.strip() for i in line.split('|')]
                        left_as = int(rel[0])
                        right_as = int(rel[1])
                        relation = AsRelation.encode(int(rel[2]))
                        self._relation.update({(left_as, right_as): relation,
                                               (right_as, left_as): AsRelation.flip(relation)})
        except (IOError, TypeError) as e:
            logging.critical("Encountered error when initializing AS relationship DB: %s" % e)

    def has_relation(self, tup):
        """Check if the two AS in the input tuple have certain relationship

        Args:
            tup (tuple): tuple of two ASN in int

        Returns:
            one of the relationships defined in AsRelation or None
        """
        try:
            return self._relation[tup]
        except KeyError:
            return None


class IxpMemberDB:
    """IxpMemberDB provides search facilities for IXP interconnection IP addresses and IXP membership

    Attributes:
        _interco (dict): IP address to InterCo object mapping
        _membership (dict): IXP to member ASN (int) set mapping
        _presence (dict): ASN (int) to IXPs that it is present
    """
    def __init__(self, fn):
        """Initializes from traIXroute database merge output ixp_membership.txt

        Args:
            fn (string): path to traIXroute database merge output ixp_membership.txt
        """
        self._interco = dict()
        self._membership = dict()
        self._presence = dict()
        try:
            with open(fn, 'r') as fp:
                for line in fp:
                    # only read line with ! flags
                    if len(line.split(',')) == 8:
                        _, flag, addr, asn, short_name, long_name, country, city = [i.strip() for i in line.split(',')]
                        if flag == '!':
                            ixp = IXP(short_name=short_name, long_name=long_name, country=country, city=city)
                            asn = int(asn[2:])
                            # update IXP membership
                            if ixp in self._membership:
                                self._membership[ixp].add(asn)
                            else:
                                self._membership[ixp] = set([asn])
                            # update AS presences at IXPs
                            if asn in self._presence:
                                self._presence[asn].add(ixp)
                            else:
                                self._presence[asn] = set([ixp])
                            # update interconnection ip
                            self._interco.update({addr: Addr(addr=addr, addr_type=AddrType.InterCo, asn=asn, ixp=ixp)})
        except (IOError, ValueError) as e:
            logging.critical("Encountered error when initializing IXP membership DB: %s" % e)

    def lookup_interco(self, addr):
        """Lookup IXP interconnection IP address

        Args:
            addr (string): IP address

        Returns:
            InterCo if queried IP address is an IXP interconnection IP otherwise None
        """
        try:
            return self._interco[addr]
        except KeyError:
            return None

    def common_ixp(self, as_list):
        """Find out the IXPs that ASNs in given list are all present at

        Args:
            as_list (list of int): a list of ASN (int); order doesn't matter

        Return:
            set of IXP or empty set
        """
        return set.intersection(*[self._presence.get(i, set()) for i in as_list])

    def is_member(self, ixp, asn):
        """Check if given ASN is a member of the given IXP:

        Args:
            ixp (IXP): an IXP object
            asn (int): ASN in int

        Returns:
            boolean
        """
        try:
            return asn in self._membership[ixp]
        except KeyError:
            return False