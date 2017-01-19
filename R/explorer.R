library(data.table)
library(ggplot2)
library(rjson)
library(anytime)
library(changepoint.np)
library(ini)
library(reshape2)
library(plotly)
library(scales)

# Environement setting and loading backgroup files ----
# the utils.R script should sit in the same folder as this script
source('utils.R')

# relative to the folder containing this R script
# that is as well the root folder of the project
setwd('../')
main.dir = getwd()

# read project config
config <- read.ini("config")
# locate where data is stored
data.dir <- file.path(main.dir, config$dir$data)

# set to data folder
setwd(data.dir)

# Probe meta
probe.meta <- data.table(read.csv2("pb.csv", sep=';', dec='.', stringsAsFactors = F))

# Probe to chunk idx
dic.v4 <- data.table(read.csv2('pb_chunk_index_v4.csv', stringsAsFactors = F))
dic.v6 <- data.table(read.csv2('pb_chunk_index_v6.csv', stringsAsFactors = F))

# Basics ----
# probe with system-ipv4/6-works tag
probe.v4.work <- probe.meta[grepl('ipv4-works', system_tags), probe_id]
probe.v6.work <- probe.meta[grepl('ipv6-works', system_tags), probe_id]

# AS coverage by probes with v4/v6 working probes
asnv4.v4works <- probe.meta[grepl('ipv4-works', system_tags), .(probe_count=length(probe_id)), by=asn_v4][order(probe_count, decreasing = T)]
asnv6.v6works <- probe.meta[grepl('ipv6-works', system_tags), .(probe_count=length(probe_id)), by=asn_v4][order(probe_count, decreasing = T)]

# RTT summary ----
rtt.pingv4 <- data.table(read.csv2("rtt_summary_1010_of_v4.csv", header = T, stringsAsFactors = F, na.strings = "None"))
rtt.tracev4 <- data.table(read.csv2("rtt_summary_5010_of_v4.csv", header = T, stringsAsFactors = F, na.strings = "None"))
rtt.pingv6 <- data.table(read.csv2("rtt_summary_2010_of_v6.csv", header = T, stringsAsFactors = F, na.strings = "None"))
rtt.tracev6 <- data.table(read.csv2("rtt_summary_6010_of_v6.csv", header = T, stringsAsFactors = F, na.strings = "None"))

# * data length, compare raw and reached ----
# reached is the case where the rtt is valid, traceroute reaches the last hop
# * * v4 ping ----
g <- ggplot(melt(rtt.pingv4, id.vars = 'probe_id', 
                 measure.vars = c('raw_length', 'valid_length'), 
                 variable.name = 'type', value.name = 'length')) + 
  geom_density(aes(as.integer(length), col=type))
print(g)

# * * v4 trace ----
# It is very wierd to see that the valid length for most probes kind of bordered at about 2000
# A first guess is that the all pass through on common AS where traceroute get filtered, to be verified later on
g <- ggplot(melt(rtt.tracev4, id.vars = 'probe_id', 
                 measure.vars = c('raw_length', 'valid_length'), 
                 variable.name = 'type', value.name = 'length')) + 
  geom_density(aes(as.integer(length), col=type))
print(g)

# * * v6 ping ----
g <- ggplot(melt(rtt.pingv6, id.vars = 'probe_id', 
                 measure.vars = c('raw_length', 'valid_length'), 
                 variable.name = 'type', value.name = 'length')) + 
  geom_density(aes(as.integer(length), col=type))
print(g)

# * * v6 trace ----
# similar phenomenon is as well with IPv6 traceroute
# but the valide length is even smaller
g <- ggplot(melt(rtt.tracev6, id.vars = 'probe_id', 
                 measure.vars = c('raw_length', 'valid_length'), 
                 variable.name = 'type', value.name = 'length')) + 
  geom_density(aes(as.integer(length), col=type))
print(g)

# * how many probes have raw length within 0.5% incompletness ----
# ideal length
start <- config$collection$start
end <- config$collection$end
duration <- (as.integer(anytime(end, asUTC = T)) - as.integer(anytime(start, asUTC = T)))
ping_length <- duration/240
trace_length <- duration/1800
# count the probes with enough length
tau = 0.005
rtt.pingv4[raw_length > (1-tau)*ping_length, length(probe_id)]
rtt.pingv6[raw_length > (1-tau)*ping_length, length(probe_id)]
rtt.tracev4[raw_length > (1-tau)*trace_length, length(probe_id)]
rtt.tracev6[raw_length > (1-tau)*trace_length, length(probe_id)]

# Compare RTT by ping and traceroute ----
# * v4 ----
# select probes with enough valid data length
pb_id <- intersect(rtt.pingv4[as.integer(valid_length) > 0.8*ping_length, probe_id], 
                   rtt.tracev4[as.integer(valid_length) > 0.4*trace_length, probe_id])
# merge ping and trace rtt summarys together
rtt.cp.v4 <- merge(rtt.pingv4[probe_id %in% pb_id, .(probe_id, ping.mean = mean, ping.std = std)],
                   rtt.tracev4[probe_id %in% pb_id, .(probe_id, trace.mean = mean, trace.std = std)],
                   by = 'probe_id')
# * mean comparison ----
# strong leaner correleation
# some outliers, will investigate individually
g <- ggplot(rtt.cp.v4, aes(x=as.numeric(ping.mean), y=as.numeric(trace.mean))) +
  geom_point(aes(text=paste("Probe_id:", probe_id)), shape = 21, col = NA, fill='black', size=2, alpha=0.4) +
  geom_text(data=data.frame(x =400, y = 600), 
            aes(x,y,label = lm_eqn(rtt.cp.v4[,.(x=as.numeric(ping.mean), y=as.numeric(trace.mean))])), 
            parse = TRUE, size=7, col='blue') +
  geom_line(data=data.frame(x=0:800, y=0:800), aes(x,y), col='red') +
  geom_smooth(method = 'lm')+
  theme(text = element_text(size=20))
print(g)
# with ggplotly, you can get the probe_id when hovering the cursoir over the data point, handy
ggplotly(g)

# quantify the mean RTT difference with CDF or density estimation
# highly concentrated near one
g <- ggplot(rtt.cp.v4, aes(log_mod(as.numeric(trace.mean)/as.numeric(ping.mean), 1))) +
  geom_density() +
  scale_x_continuous(breaks = log_mod(c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10), 1), 
                     labels = c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10))
print(g)

# * std comparison ----
# not really linear
# even the std of traceroute tend to be smaller compared to ping
g <- ggplot(rtt.cp.v4, aes(x=as.numeric(ping.std), y=as.numeric(trace.std))) +
  geom_point(aes(text=paste("Probe_id:", probe_id)), shape = 21, col = NA, fill='black', size=2, alpha=0.4) +
  geom_text(data=data.frame(x = 50, y = 180), 
            aes(x,y,label = lm_eqn(rtt.cp.v4[,.(x=as.numeric(ping.std), y=as.numeric(trace.std))])), 
            parse = TRUE, size=7, col='blue') +
  geom_line(data=data.frame(x=0:200, y=0:200), aes(x,y), col='red') +
  geom_smooth()+
  scale_x_continuous(trans = log10_trans())+
  scale_y_continuous(trans = log10_trans())+
  theme(text = element_text(size=20))
print(g)
ggplotly(g)

# quantify the difference with desntiy or CDF
g <- ggplot(rtt.cp.v4, aes(log_mod(as.numeric(trace.std)/as.numeric(ping.std), 1))) +
  geom_density() +
  scale_x_continuous(breaks = log_mod(c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10), 1), 
                     labels = c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10))
g


# * mean and std together ----
g <- ggplot(rtt.cp.v4, aes(x = log_mod(as.numeric(trace.mean)/as.numeric(ping.mean), 1),
                           y = log_mod(as.numeric(trace.std)/as.numeric(ping.std), 1))) +
  geom_point(aes(text=paste("Probe_id:", probe_id)), shape = 21, col = NA, fill='black', size=2, alpha=0.2) +
  #geom_text(data=data.frame(x = 50, y = 180), 
  #          aes(x,y,label = lm_eqn(rtt.cp.v4[,.(x=as.numeric(ping.std), y=as.numeric(trace.std))])), 
  #          parse = TRUE, size=7, col='blue') +
  #geom_line(data=data.frame(x=0:200, y=0:200), aes(x,y), col='red') +
  geom_density2d(col='green', size=.3) +
  scale_x_continuous(breaks = log_mod(c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10), 1), 
                     labels = c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10)) + 
  scale_y_continuous(breaks = log_mod(c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10), 1), 
                   labels = c(0, 0.2, 0.6, 0.8, 1, 1.5, 2, 10)) +
  #coord_cartesian(xlim=log_mod(c(0, 2),1), ylim=log_mod(c(0,20), 1)) +
  theme(text = element_text(size=20))
print(g)
ggplotly(g)

# * case study ----
case = 10460

probe.meta[probe_id==case]
rtt.pingv4[probe_id==case]
rtt.tracev4[probe_id==case]

# chunk id of the probe
chunk.id = dic.v4[probe_id == case, chunk_id]

# load the ping json file
ping_json <- fromJSON(file = sprintf('%d_1010.json', chunk.id))

# plot the ping rtt time series
ts.pingv4 <- data.frame(epoch = ping_json[[as.character(case)]]$epoch, 
                        rtt = ping_json[[as.character(case)]]$min_rtt)
g<- ggplot(ts.pingv4, aes(x= anytime(epoch), y=rtt)) + 
    geom_point(aes(text=paste("Index:", seq_len(nrow(ts.pingv4)))), size=.8)
print(g)
ggplotly(g)

# load the traceroute json file
trace_json <- fromJSON(file=sprintf('%d_5010.json', chunk.id))

# plot the traceroute last hop rtt time series
probe_trace <- trace_json[[as.character(case)]]$path
# [[1, IP, RTT],[...],...]
last_hop <- unlist(lapply(probe_trace, function(x) x[[length(x)]][[2]]))
last_rtt <- unlist(lapply(probe_trace, function(x) x[[length(x)]][[3]]))
reach_idx <- grepl('192.228.79.201', last_hop)

ts.tracev4 <- data.frame(epoch = trace_json[[as.character(case)]]$epoch, 
                         rtt = last_rtt,
                         hop = last_hop,
                         reach_idx = reach_idx)
g<- ggplot(ts.tracev4) + geom_point(aes(x=epoch, y=rtt, text=paste("Index:", seq_len(nrow(ts.pingv4)))))
print(g)
ggplotly(g)


