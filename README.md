# What is it about
To be filled...

# Requirements
python packages
R, R packages
other projects

# How to use it? 
* [Collect measurement from RIPE Atlas](docs/data_collection.md)
* [Summarize RTT characters for each Atlas Probe](docs/rtt_summary.md)
* [Translate IP hops to ASN paths](docs/ip2asn.md)
* [Detect path changes with changing Paris ID](docs/path_change.md)
* [Detect changes in RTT time series](docs/rtt_cpt.md)


# What we collect?
What are collected, how/where are they stored?
## RIPE measurements
* v4 and v6 builtin measurement toward b-root; chunk and probe id to chunk index;
* probe meta;
## Auxiliary data
* IXP membership and subnet from [traIXroute](https://github.com/gnomikos/traIXroute.git); How to get the cleaned data;
* Routeview BGP archive for IP to ASN translation with [pyasn](https://github.com/hadiasghari/pyasn.git);
* CAIDA [AS relationship inference](http://data.caida.org/datasets/as-relationships/serial-2/)

# What we produce?
* per probe RTT trace summary;
* RTT trace change detection;
* AS-level path change detection;
* IP-level path change detection;
* Root cause RTT changes;