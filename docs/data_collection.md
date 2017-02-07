# Data collection
This document explains how measurements from [RIPE Atlas](https://atlas.ripe.net) are collected in this project.
## Usage
```
$ python data_collection.py --help
usage: data_collection.py [-h] [-f]

optional arguments:
  -h, --help      show this help message and exit
  -f, --fromfile  read ./data/pb.csv for probes and only fetch measurements
                  not yet present in the repository.

```
With [data_collection.py](../data_collection.py), measurements from RIPE Atlas are collected.
The script has one optional flag --fromfile.  
With this flag set, the script will look in the [data/](../data/) for existing data.
The option is quite handy when the previous collection is interrupted by network issue, undiscovered bug, etc.
When the flag is set, previously downloaded data is not downloaded again.

## Configuration
The data collection is configured in a [config](../config) along with other settings for the project.
```
[collection]
start = 2016-10-01 00:00:00 +0000
end = 2017-01-01 00:00:00 +0000
msmv4 = 1010, 5010
msmv6 = 2010, 6010
```
Four parameters are needed for data collection.
__start__ specifies the beginning of collection time window, while __end__ defines the end.
They shall follow the format '%Y-%m-%d %H:%M:%S %z'.
__msmv4__ takes the IPv4 measurements IDs that are meant to be collected.
__msmv6__ takes IPv6 measurements.
Measurement IDs shall be separated by a comma.

## What does the script actually do?
The script first learns all v3 Atlas probes and anchors.
Then it collects configured v4/v6 measurements for all probes and anchors with system-ipv4/ipv6-works tag.
Probes are cut into smaller chunks. Multiple processes handle these chunks in parallel.

## How collected data is stored?
### Probe meta info
The script first creates __pb.csv__ in [data/](../data/) storing the meta data associated to each probe.
It is as comma ';' separated csv file. Unable cell is filled with 'None'. 
Here below is part of the file in a human readable way.
```
probe_id  address_v4      prefix_v4      asn_v4  address_v6                             prefix_v6          asn_v6  is_anchor  country_code  system_tags
10001     193.0.21.22     193.0.20.0/23  3333    2001:67c:2e8:110:fad1:11ff:fea9:f090   2001:67c:2e8::/48  3333    False      NL            ('system-v3', 'system-ipv4-capable', 'system-ipv6-capable')
...
10014     None             None          None    None                                   None               None    False      NL            ('system-v3',)
...
```
### Probe id to chunk id mapping
For each measurement configured in [config](../config), i.e. 1010, 5010, 2010, 6010, a series of json file storing Atlas measurements are generated.
They are named following this pattern: __chunkid_msmid.json__. Each file contains alone the entire trace of several probes.
In order to know the file, i.e. chunk id for a given probe, two index file is as well generated, one for IPv4 measurements, the other for IPv6.
They are [pb_chunk_index_v4.csv](../data/pb_chunk_index_v4.csv) and [pb_chunk_index_v6.csv](../data/pb_chunk_index_v6.csv) in [data/](../data/) folder.

### Ping measurement
Each json file for ping measurement is of following structure:
```
{
    probe id (string): {
        "epoch": list of int; timestamps for each measurement,
        "all_rtt": list of list of int; [[rtt, rtt, rtt],...],
        "min_rtt": list of int; the minimum rtt in msec among the 3 try
    }
}
```
### Traceroute measurement
Each json file for traceroute measurement is of following structure:
```
{
    probe id (string):{
        "epoch": list of int; timestamps for each measurement,
        "path": list of list of mixed type; [[#hop, IP address, min_rtt],...],
        "paris_id": list of int; Paris ID used for each traceroute measurement
    }
}
```

## Monitoring and troubleshooting
The script will create data_collection.log in the same folder and logs events and progresses in it.
For example:
```
2017-01-11 18:06:25 +0000 - INFO - Probe query finished in 176 sec.
2017-01-11 18:06:25 +0000 - INFO - 11815/15633 probes with not-None v4 ASN and prefixes.
2017-01-11 18:06:25 +0000 - INFO - 6072/15633 probes with system-ipv4-works.
2017-01-11 18:06:25 +0000 - INFO - 3566/15633 probes with not-None v6 ASN and prefixes.
2017-01-11 18:06:25 +0000 - INFO - 1949/15633 probes with system-ipv6-works.
2017-01-11 18:06:25 +0000 - INFO - 6061 v4 net & tag
2017-01-11 18:06:25 +0000 - INFO - 5754 v4 net - tag
2017-01-11 18:06:25 +0000 - INFO - 11 v4 tag - net
2017-01-11 18:06:25 +0000 - INFO - 1928 v6 net & tag
2017-01-11 18:06:25 +0000 - INFO - 1638 v6 net - tag
2017-01-11 18:06:25 +0000 - INFO - 21 v6 tag - net
2017-01-11 18:23:02 +0000 - INFO - Chunk 0 of measurement 1010 fetched in 997.082475901 sec.
2017-01-11 18:23:23 +0000 - INFO - Chunk 40 of measurement 1010 fetched in 1018.05344796 sec.
2017-01-11 18:23:27 +0000 - INFO - Chunk 28 of measurement 1010 fetched in 1022.03208208 sec.
```
