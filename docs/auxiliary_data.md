# Auxiliary data
Apart from the RIPE Atlas measurements, we as well collected some other auxiliary data to help us interpret
the Atlas measurements, especially in translating the IP path seen in traceroute to ASN path.

There are four sources of auxiliary data:
* Routeview BGP RIBs archive for IP to ASN translation with [pyasn](https://github.com/hadiasghari/pyasn.git);
* IXP membership and subnet from [traIXroute](https://github.com/gnomikos/traIXroute.git);
* CAIDA [AS relationship inference](http://data.caida.org/datasets/as-relationships/serial-2/)
* Reserved IP blocks.

In this document, we explain how these data are collected and prepared.


## Routeview BGP RIBs
[Routeview](http://www.routeviews.org) is a well known and long-standing project that collects BGP updates and RIBs from multiple vintage points
in the internet.
With the RIBs collected, we are able to learn what prefixes are announced by what AS, thus the mapping from IP address to ASN.
The collected data are publicly available at [http://archive.routeviews.org/bgpdata/](http://archive.routeviews.org/bgpdata/).

We downloaded the BGP RIB [rib.20161201.0800.bz2](http://archive.routeviews.org/bgpdata/2017.01/RIBS/rib.20161201.0800.bz2), 
and use [pyasn](https://github.com/hadiasghari/pyasn.git) to parse the rib into prefix-to-ASN mapping.
Citing the usage from [pyasn](https://github.com/hadiasghari/pyasn.git) documentation:
```
pyasn_util_convert.py --single <Downloaded RIB File> <ipasn_db_file_name>
```
The produced file is named as __ipasn.dat__ and stored in [localutils/db/](../localutils/db/).

## CAIDA AS relationship inference
Knowing the relationship between ASes can help interpret traceroute measurements with better precision, c.f. the large 
amount of works concerning third party address detection in traceroute.
In our work, we use the inferred the AS relationship to simply remove some private addresses, timeout hops and reserved IPs
seen in the traceroute.

We downloaded from [CAIDA](http://www.caida.org/data/as-relationships/) the inferred AS relationship for Dec. 12, i.e.
__201612-1.as-rel2.txt__ and stored it as well in [localutils/db/](../localutils/db/).


## IXP related data
IP addresses belonging to IXPs can sometimes appear in the traceroute.
They are not necessarily mapped to an ASN and sometimes use reserved IP blocks.
Yet, IXP is an important and integral part of the internet path.
It is hence import to mark their presence correctly in the traceroute measurement.
[traIXroute](https://github.com/gnomikos/traIXroute.git) provides a human friendly tool for that end.
However it lacks programming interface that exposes its detection logic independent of its verbose human-friendly output formatting.
Therefore in this work, we take advantage of the IXP related database it provides alone and implemented ourselves its core detection logic.
```
$ python traIXroute.py -u -m
```
With the above two options [traIXroute](https://github.com/gnomikos/traIXroute.git) cleans and merges the data from 
[PCH](https://www.pch.net) and [PeeringDB](https://www.peeringdb.com) 
(for exact data downloading urls check the [config](https://github.com/gnomikos/traIXroute/blob/v2.1/config) of traIXroute).
Two files are produced: __ixp_membership.txt__ and __ixp_prefixes.txt__. We stored them again in [localutils/db/](../localutils/db/).

## Reserved IP blocks
Multiple ASes announces [bogon addresses](https://en.wikipedia.org/wiki/Bogon_filtering).
When looking up these reserved IPs (including private IPs) with the [Routeview](http://www.routeviews.org),
we found that they have an AS mapping, which is indeed misleading, as they can be used by various different ASes or home networks.
Therefore we manually complied a file listing all the [reserved IP blocks according to IETF standards](https://en.wikipedia.org/wiki/Reserved_IP_addresses).
The file is named __reserved_ip.txt__ and is as well stored in [localutils/db/](../localutils/db/).

