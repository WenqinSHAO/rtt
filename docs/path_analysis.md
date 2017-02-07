# Traceroute Path Analysis
This documentation explains how we:
* translate IP path to ASN path;
* detect change in IP Forwarding Pattern (IFP);

## Usage
```
$ python path_analysis.py
```
The script will read all the traceroute measurement json files in [data/](../data) and produces
json files with the same names in the [data/path_analysis/](../data/path_analysis) folder
according to the __dir__ section in [config](../config).
__path_analysis.log__ will be generated for debugging uses.

Functions are provides in [localutils/pathtools.py](../localutils/pathtools.py) to perform following tasks in a standalone
manner, and thus can be easily reused out side the scope of this project:
* query IP address info from various [auxiliary data](auxiliary_data.md) source;
* detect the presence of IXP in IPv4 IP path seen in traceroute;
* detect changes in IP forwarding pattern;

For example:
```python
import localutils.pathtools as pt

# example for querying IP address information
pt.get_ip_info('195.191.171.31')
# Addr(addr='195.191.171.31', type=101, asn=197345, ixp=IXP(short='EPIX.Katowice', long='Stowarzyszenie na Rzecz Rozwoju Spoleczenstwa Informacyjnego e-Poludnie', country='PL', city='Katowice Silesia'), desc=None)
pt.get_ip_info('192.168.0.1')
# Addr(addr='192.168.0.1', type=104, asn=None, ixp=None, desc='private')

# example for translating IP path to ASN path
ip_path = ["10.71.6.11", "194.109.5.175", "194.109.7.169", "194.109.5.2", 
           "80.249.209.150", "72.52.92.213", "72.52.92.166", "184.105.223.165", 
           "184.105.80.202", "72.52.92.122", "x", "216.218.223.26", "130.152.184.3", 
           "x", "x", "x", "x", "x", "x"]
enhanced_hops = [pt.get_ip_info(hop) for hop in ip_path]
asn_path = pt.remove_repeated_asn([hop.get_asn() for hop in pt.insert_ixp(pt.bridge(enhanced_hops))])
# ['private', 3265, 'AMS-IX', 6939, 226, 'Invalid IP address']

# example for detecting IFP change
def print_seg(seg):
    for i in seg:
        print i

paris_id = [2, 3, 4, 5, 6, 0, 1,
            2, 3, 4, 5, 6, 0, 1,
            2, 3, 4, 5, 6, 0, 1,
            2, 3, 4, 5, 6, 0, 1,
            2, 3, 4, 5, 6, 0, 1]
paths = ['b', 'b', 'c', 'b', 'b', 'a', 'b',
         'b', 'a', 'a', 'k', 'b', 'a', 'b',
         'b', 'a', 'a', 'b', 'b', 'a', 'b',
         'b', 'a', 'a', 'b', 'b', 'a', 'b',
         'b', 'a', 'a', 'b', 'k', 'a', 'b']  # each string stands for a IP path
seg = pt.ip_path_change_split(paris_id, paths, 7)  # 7 because 7 different Paris ID in all
print_seg(seg)
"""
Should expect:
(0, 5, pattern={0: 'a', 1: None, 2: 'b', 3: 'b', 4: 'c', 5: 'b', 6: 'b'})
(6, 9, pattern={0: None, 1: 'b', 2: 'b', 3: 'a', 4: 'a', 5: None, 6: None})
(10, 10, pattern={0: None, 1: None, 2: None, 3: None, 4: None, 5: 'k', 6: None})
(11, 31, pattern={0: 'a', 1: 'b', 2: 'b', 3: 'a', 4: 'a', 5: 'b', 6: 'b'})
(32, 32, pattern={0: None, 1: None, 2: None, 3: None, 4: None, 5: None, 6: 'k'})
(33, 34, pattern={0: 'a', 1: 'b', 2: None, 3: None, 4: None, 5: None, 6: None}
"""
pt.ifp_change(seg, len(paris_id))
# [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0]
```

## Output
Each json file in [data/path_analysis/](../data/path_analysis) follows the following structure:
```
{
    probe id (int):{
        "epoch": list of int; timestamps for each measurement,
        "ip_path": list of list of string; [[hop1, hop2,...],...],
        "asn_path": list of list of mixed type (int/string); [[ASN1, ASN2,...],...],
        "as_path_change": list of int; same length as "epoch" list, 1 for momement of change, otherwise 0,
        "ifp_simple": list of int; IP Forwarding Pattern (IFP) change detected with simple method; 0,1 as "as_path_change",
        "ifp_bck": list of int; IFP change detected with backward extension heuristic,
        "ifp_split": list of int; IFP change detected with further split on top of backward extension
    }
}
```

## IP to ASN path
Trivial as the task may sound, IP to ASN path translation requires actually quite a lot special attentions,
apart from the third-party IP. (My personal view is that third-party IP has in fact relatively limited impact since 
1/only a small portion of the traceroutes are concerned according to previous studies, reference to be added;
2/ modern equipments tend to be implemented in a way that the response IP/interface being the same as the one that receives the packet, reference to be added.)

We take care of two issues in this work:
* how to handle reserved IPs, including private IP;
* how to detect the presence of IXP.

As a matter of fact, some IXPs use reserved IP blocks for inter-connection. 
Hence these two issues are actually mingled with each other.

Our method is:

0. add the probe IP at the beginning (helps to remove private hops at the head of ip path later on);
1. get enhanced IP hop information, from [auxiliary data](auxiliary_data.md) collected in this work;
  1. check if an IP is an [IXP interconnection address](auxiliary_data.md#ixp-related-data) used by member AS; (get info on IXP, and ASN of the member);
  2. else, check if an IP belongs to one of [prefixes used by certain IXP](auxiliary_data.md#ixp-related-data); (get info on the IXP);
  3. else, check if an IP belongs to one of [reserved IP blocks](auxiliary_data.md#reserved-ip-blocks); (get on the reserved purpose);
  4. else, check if an IP is announced by certain AS according to [BGP RIBs](auxiliary_data.md#routeview-bgp-ribs); (get info on ASN);  
2. once step 1 is down for each hop of a path, we remove hops in reserved IP blocks if they are directly surrounded by ASNs with know relationship
according to [CAIDA AS relationship inference](auxiliary_data.md#caida-as-relationship-inference);
(IXP prefixes are regarded transparent while IXP interco follows the ASN of the AS that uses it) 
3. detect the presence of IXP for IPv4 traceroutes (as IXP related info is only available in IPv4) using heuristics proposed by [traIXroute](https://github.com/gnomikos/traIXroute.git);
4. removed continuous repeated ASN in path.

NOTE: [traIXroute](https://github.com/gnomikos/traIXroute.git) didn't try to remove reserved IPs even when it is possible.
This matters when such hop is next to IXP related addresses and prevents the detection.

## IP Forwarding Pattern change detection
