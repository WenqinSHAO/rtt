# Correlation between RTT change and path change
This document explains how we find correlation between the two types of changes.

## Usage
```bash
$ python correlation.py
```
The script will read RTT changes in [data/rtt_analysis/](../data/rtt_analysis/)
and path changes for the corresponding probe trace in [data/path_analysis](../data/path_analysis/).
Then, correlation based on temporal locality between the two types of change is calculated and stored to files in [data/](../data/).
For each measurement configured in [config](config), i.e. msmv4 and msmv6 in this project, 
two files will be produced for each changepoint method used in detection.
The reason for splitting output by changepoint method is that otherwise the output file could be too large to
get loaded in memory when exploring using R.

### Overview file
cor_overview_<task_name>_<cpt_method>.csv
```bash
probe  trace_len  cpt_method   cpt_count  pch_method      pch_count  tp  fp   fn  precision        recall          dis
10048  33116      cpt_np&MBIC  109        as_path_change  31         19  12   90  0.612903225806   0.174311926606  714.736842105
10048  33116      cpt_np&MBIC  109        ifp_simple      245        16  229  93  0.065306122449   0.146788990826  727.75
10048  33116      cpt_np&MBIC  109        ifp_bck         245        17  228  92  0.069387755102   0.155963302752  789.588235294
10048  33116      cpt_np&MBIC  109        ifp_split       252        20  232  89  0.0793650793651  0.183486238532  831.55
...
```
**probe** is the ID of Atlas probe.
**trance_len** is the length of RTT time series.
**cpt_method** is the method used in detecting RTT changes.
**cpt_count** is the number of detected RTT changes.
**pch_method** indicates the type of path changes.
**pch_count** tells the number of detected path changes.
**tp** is the number of path changes correlate with RTT changes.
**fp** is the number of path changes not correlated with RTT changes.
**fn** is the number of RTT change not correlated with path changes.
**precision** is the fraction of path changes correlated with RTT changes.
**recall** is the faction of RTT changes correlated with path changes.
*dis* is the average distance in sec between correlated RTT and path changes.

### View from RTT changes
cor_rtt_ch_<task_name>_<cpt_method>.csv
```bash
probe  i  cpt_idx  delta_median  delta_std       seg_len  seg_median   seg_std         as_path_change_match  as_path_change_dis  as_path_change_ixp_match  as_path_change_ixp_dis  ifp_simple_match  ifp_simple_dis  ifp_bck_match  ifp_bck_dis
10048  0  435      5.12148       0.645336912178  85       161.710395   0.192036196103  False                 None                False                     None                    True              927             True           927
10048  1  520      2.5296825     7.34415060162   1310     164.2400775  7.53618679772   False                 None                False                     None                    False             None            False          None
10048  2  1830     167.2400775   7.53618679772   4        -3.0         0.0             False                 None                False                     None                    True              926             True           926
10048  3  1834     150.6778      1.24072676882   281      147.6778     1.24072676882   False                 None                False                     None                    False             None            False          None
10048  4  2115     0.6643525     0.743676778306  310      148.3421525  0.497049990514  False                 None                False                     None                    False             None            False          None
10048  5  2425     50.7908325    4.05170844303   5        199.132985   4.54875843354   False                 None                False                     None                    False             None            False          None
10048  6  2430     52.72956      4.3469726122    16       146.403425   0.201785821341  False                 None                False                     None                    False             None            False          None
10048  7  2446     45.517185     6.65412320405   11       191.92061    6.85590902539   False                 None                False                     None                    False             None            False          None
10048  8  2457     44.32654      5.15389010125   377      147.59407    1.70201892414   False                 None                False                     None                    False             None            False          None

```
Each line describes an RTT change detected by the method in the file name.
The index of **i**th change in **probe** is at **cpt_idx**.
The median difference accross this changepoint is **delta_median**, and the std difference is **delta_std**.
**seg_len** tells the RTT segment length following the changepoint.
The median RTT of the segment following the changepoint is **seg_median**, and the std is **seg_std**.
Then the line tells whether this change matches with AS path changes(**as_path_change_match**), 
IXP changes(**as_path_change_ixp_match**) or IFP changes (**ifp_simple_match** and **ifp_bck_match**).

## Correlation method
Ping and traceroute measurements from a same probe are asynchronous and performed at different intervals.
Therefore strict correlation between RTT and path changes with same timestamp is not practical.
We borrow the min cost maximum matching concept in [changepoint evaluation](eval_cpt.md) to find the most appropriate approximate matching
bounded by a window. The window is set to the interval of traceroute measurement, i.e. 30min.
__evaluation_window_adp()__ in [localuils/benchmark.py](../localutils/benchmark.py) is used.
It is a specially optimized version of __evaluation_window()__ for sparse cost matrix in this case.