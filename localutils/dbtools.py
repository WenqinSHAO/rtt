"""
dbtools.py provides class definitions to handle CAIDA AS relationship inference and
IXP related output from traIXroute database merge
"""
import SubnetTree
import logging


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


class AsRelation:
    """
    AsRelation describes the relation between ASes

    Attributes:
        P2C (int): -1, class attribute, provider to customer
        PEER (int): 0, class attribute, peer
        C2P (int): 1, class attrubute, customer to provider
        coder (dict): int to above attributes mapping
    """
    P2C, PEER, C2P = range(-1,2,1)
    coder = {-1: AsRelation.P2C,
             0: AsRelation.PEER,
             1: AsRelation.C2P}

    @staticmethod
    def encode(number):
        """Encode a given number to one of the defined relationship

        Args:
            number (int): relation readings from CAIDA AS relationship inference

        Returns:
            int, one of the defined relationship or None
        """
        return AsRelation.coder.get(number)

    @staticmethod
    def flip(relation):
        """Change C2P to P2C, while PEER remain the same

        Args:
            relation (int): one of the defined relationship

        Returns:
            int: one of the defined relationship, or None
        """
        try:
            return AsRelation.coder.get(int(relation)*-1)
        except TypeError:
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


class InterCo:
    """InterCo describes an IP address used for IXP interconnection

    Attributes:
        addr (string): IP address in string
        asn (int): AS that uses this interconnection IP address
        ixp (IXP): the IXP that attributes the IP address
    """
    def __init__(self, addr, asn, ixp):
        self.addr = addr
        self.asn = asn
        self.ixp = ixp

    def __repr__(self):
        return "InterCo(addr=%r, asn=%r, ixp=%r)" % (self.addr, self.asn, self.ixp)

    def __eq__(self, other):
        return self.__repr__() == other.__repr__()

    def __hash__(self):
        return hash(self.__repr__())


class IxpMemberDB:
    """IxpMemberDB provides search facilities for IXP interconnection IP addresses and IXP membership

    Attributes:
        _interco (dict): IP address to InterCo object mapping
        _memebership (dict): IXP to member ASN (int) set mapping
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
                            self._interco.update({addr: InterCo(addr=addr, asn=asn, ixp=ixp)})
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

