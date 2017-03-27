# RTT change detection
This document explains how we detect RTT changes for the ping measurements collected in this work.
## Usage
```
$ python rtt_analysis.py
```
The script will read all the ping measurement json files in [data/](../data) and produces
json files with the same names in the [data/rtt_analysis/](../data/rtt_analysis) folder
according to the __dir__ section in [config](../config).
__path_analysis.log__ will be generated for debugging uses.

Four functions are provides in [localutils/changedetect.py](../localutils/changedetect.py) to perform changepoint detection
for time series in a standalone manner.
The implementation is basically a wrapper of its original R functions provided in [changepoint](https://cran.r-project.org/web/packages/changepoint/changepoint.pdf) 
and [changepoint.np](https://cran.r-project.org/web/packages/changepoint.np/changepoint.np.pdf) packages.
For more details of each function, please check the docstring.

One difference with the original R implementation is that the output is the beginning indexes of the segments following changepoints,
instead of the index before the new segment.

## Output
Each json file in [data/rtt_analysis/](../data/rtt_analysis) follows the following structure:
```
{
    probe id (int):{
        "epoch": list of int; timestamps for each measurement,
        "cpt_normal&MBIC": list of int; same length as "epoch" list, 1 for momement of change, otherwise 0,
        "cpt_np&MBIC": list of int; same length as "epoch" list, 1 for momement of change, otherwise 0,
        "cpt_poissom&MBIC": list of int; same length as "epoch" list, 1 for momement of change, otherwise 0,
        "min_rtt": list of float, same length as "epoch" list, rtt values of the ping measurement
    }
}
```