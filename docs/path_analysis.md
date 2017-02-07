# Traceroute Path Analysis
This documentation explains how we:
* translate IP path to ASN path;
* detect pattern change in forwarding path;

## Usage
```
$ python path_analysis.py
```
The script will read all the traceroute measurement json files in [data/](../data) and produces a
json file with the same name in the [data/path_analysis/](../data/path_analysis) 
according to dir section in [config](../config).
__path_analysis.log__ will be generated for debugging uses.

Functions are provides in [localutils/pathtools.py](../localutils/pathtools.py) to perform following tasks in a standalone
manner, and thus can be easily reused out side the scope of this project:
* query IP address info from various [auxiliary data](auxiliary_data.md) source;
* detect the presence of IXP in IPv4 IP path seen in traceroute;
* detect changes in IP forwarding pattern;

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

As a matter of fact, some IXPs use reserved IP blocks for inter-connection, these two issues are actually
mingled with each other.

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
