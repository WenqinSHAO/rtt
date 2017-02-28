# Correlation between RTT change and path change
This document explains how we find correlation between the type of changes.

## Usage
```bash
$ python correlation.py
```
The script will read RTT changes in [data/rtt_analysis/](../data/rtt_analysis/)
and path changes for the corresponding probe trace in [data/path_analysis](../data/path_analysis/).
Then, correlation based on temporal locality between the two types of change is calcuated and stored to files in [data/](../data/).
For each measurement configured in [config](config), i.e. msmv4 and msmv6 in this project, 
three files will be produced for each changepoint method used in detection.
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
probe  cpt_method   pch_method      i   cpt_idx  delta_median  delta_std       matched  dis
10048  cpt_np&MBIC  as_path_change  0   1232     22.695055     5.42387911352   False    None
10048  cpt_np&MBIC  as_path_change  1   1242     21.41923      5.31926637074   False    None
10048  cpt_np&MBIC  as_path_change  2   1549     9.523485      1.61541060437   False    None
10048  cpt_np&MBIC  as_path_change  3   1558     11.39508      20.7770457971   False    None
10048  cpt_np&MBIC  as_path_change  4   1618     14.763455     18.537139784    False    None
10048  cpt_np&MBIC  as_path_change  5   1830     180.382095    2.79326058587   False    None
10048  cpt_np&MBIC  as_path_change  6   1834     151.07135     0.981558484615  False    None
10048  cpt_np&MBIC  as_path_change  7   2425     51.061635     3.56719994893   False    None
10048  cpt_np&MBIC  as_path_change  8   2430     52.72956      4.3469726122    False    None
10048  cpt_np&MBIC  as_path_change  9   2446     45.517185     6.65412320405   False    None
10048  cpt_np&MBIC  as_path_change  10  2457     44.32654      5.15389010125   False    None
10048  cpt_np&MBIC  as_path_change  11  2834     150.59407     1.70201892414   True     1112
10048  cpt_np&MBIC  as_path_change  12  2845     162.846765    11.978801123    True     274

```
Each line tells what are the characters, **delta_median** and **delta_std**, of the **ith** RTT change detected with 
**cpt_method** happened on RTT measurement **cpt_idx** of the given **probe**; and whether this RTT change
is **matched** to a path change of type **pch_method**. If **matched**, what is the distance in second toward the path change.

### View from path changes
cor_path_ch_<task_name>_<cpt_method>.csv
```bash
probe  cpt_method   pch_method      i   pch_idx  matched  dis   delta_median  delta_std
10048  cpt_np&MBIC  as_path_change  0   378      True     1112  150.59407     1.70201892414
10048  cpt_np&MBIC  as_path_change  1   379      True     274   162.846765    11.978801123
10048  cpt_np&MBIC  as_path_change  2   406      True     1112  149.033975    44.7257540578
10048  cpt_np&MBIC  as_path_change  3   448      True     396   173.2571075   1.65819498975
10048  cpt_np&MBIC  as_path_change  4   620      True     1111  176.270205    2.03042458462
10048  cpt_np&MBIC  as_path_change  5   688      True     395   170.273945    2.5240053939
10048  cpt_np&MBIC  as_path_change  6   954      True     991   0.232715      46.9301693257
10048  cpt_np&MBIC  as_path_change  7   955      False    None  None          None

```
Each line tells whether **ith** path change of type **pch_method** happend at **pch_idx** of traceroute measurement
is matched to an RTT change by **cpt_method**; if yes, what are the *dis* to that RTT change, and what are
the characters of the RTT change, in terms of **delta_median** and **delta_std**.

## Correlation method
Ping and traceroute measurements from a same probe are asynchronous and performed at different intervals.
Therefore strict correlation between RTT and path changes with same timestamp is not practical.
We borrow the min cost maximum matching concept in [changepoint evaluation](eval_cpt.md) to find the most appropriate approximate matching
bounded by a window. The window is set to the interval of traceroute measurement, 30min being much larger than the ping interval 4min.
__evaluation_window_adp()__ in [localuils/benchmark.py](../localutils/benchmark.py) is used.
It is a specially optimized version of __evaluation_window()__ for sparse cost matrix in this case.