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
setwd("/Users/wenqin/Documents/internet_rtt/remote_data/")

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

nrow(rtt.pingv4)
probe.meta[probe_id %in% one_probe_as, length(unique(asn_v4))]
probe.meta[probe_id %in% one_probe_as, length(unique(country_code))]
sum(rtt.pingv4$raw_length, na.rm = T)
sum(rtt.tracev4$raw_length, na.rm = T)

u_as <- read.table("unique_as_v4.txt")
u_ixp <- read.table("unique_ixp_v4.txt", sep = '|')
u_path <- read.table("unique_as_path_v4.txt", sep = '|')
# topo summary ----
topo_stat <- data.table(read.table("topo_stat_v4.csv", header = T, stringsAsFactors = F, sep=';'))

# * data length, compare raw and reached ----
# reached is the case where the rtt is valid, traceroute reaches the last hop
# * * v4 ping ----
g <- ggplot(melt(rtt.pingv4, id.vars = 'probe_id', 
                 measure.vars = c('raw_length', 'valid_length'), 
                 variable.name = 'type', value.name = 'length')) + 
  geom_density(aes(as.integer(length), col=type))
print(g)

g <- ggplot(rtt.pingv4[valid_length>30000]) + 
  geom_density(aes(as.integer(median))) +
  scale_x_continuous(breaks=c(0, 30, 50, 80, 100, 150, 200, 250, 300, 400))
print(g)


rtt.pingv4[valid_length>30000, length(probe_id)]/rtt.pingv4[,length(probe_id)]

# * * v4 trace ----
# It is very wierd to see that the valid length for most probes kind of bordered at about 2000
# A first guess is that the all pass through on common AS where traceroute get filtered, to be verified later on
g <- ggplot(melt(rtt.tracev4, id.vars = 'probe_id', 
                 measure.vars = c('raw_length', 'valid_length'), 
                 variable.name = 'type', value.name = 'length')) + 
  geom_density(aes(as.integer(length), col=type))
print(g)
quantile(rtt.tracev4$valid_length, probs = c(.05,.5,.75,.9,.95, .99), na.rm = T)
scope_by_trace <- rtt.tracev4[valid_length>1975, probe_id]
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

#  case study ----
case = 10460
# 10460 is an interesting case in the sense that:
# 1/ traceroute rtt mean << ping rtt mean
# 2/ traceroute rtt std >> ping rtt std
# It turns out to be that traceroute when through some paths will way much smaller RTT than ping does.
# One more interesting finding is that the first half of traceroute is not reachable.
case = 21600
case = 10663
case = 21328
case = 26106
case = 15902

case = 12937 # high var cpts
case = 13691 # high var cpts
case = 11650 # high var cpts
case = 26326 # large var large level cpts np
case = 10342 # large var large level cpts
case = 12385 # large var large level cpts
case = 17272 # large var large level cpts
case = 17082 # large var large level cpts
case = 21067 # large var large level cpts

case = 12833 # AS ch + precison - load balancing among three providers
case = 22292 # AS ch + precision - precense of 
case = 6129 # AS ch + precsion - load balancing between IXP
case = 24244 # AS ch + precsion - most of the time due IXP detection unknown IXP prefixes have to check IP hops

case = 27711 # AS ch - precsion +-

case = 12849 # AS ch + precision + is really frequent and regualr AS path change
case = 13427 # AS ch + precison + have re-occuring reachability issue
case = 11665 # AS ch + precison + re-occuring reachability issue

case = 26328

case = 10015 # as path ch 100 200
case = 11150 # as path ch 100 200
case = 6038 # as path ch 100 200 

case = 21625
case = 18359
case = 23998

probe.meta[probe_id==case]
rtt.pingv4[probe_id==case]
rtt.tracev4[probe_id==case]
topo_stat[probe==case]
overview_np[probe == case]
overview_poisson[probe == case]
overview_normal[probe == case]
# chunk id of the probe
chunk.id = dic.v4[probe_id == case, chunk_id]

# load the ping json file
ping_json <- fromJSON(file = sprintf('%d_1010.json', chunk.id))
trace_json <- fromJSON(file=sprintf('%d_5010.json', chunk.id))

# plot the ping rtt time series
ts.pingv4 <- data.frame(epoch = ping_json[[as.character(case)]]$epoch, 
                        rtt = ping_json[[as.character(case)]]$min_rtt,
                        cp = ping_json[[as.character(case)]]$`cpt_poisson&MBIC`, 
                        cp_np = ping_json[[as.character(case)]]$`cpt_np&MBIC`,
                        cp_normal = ping_json[[as.character(case)]]$`cpt_normal&MBIC`)
ts.pingv4 = data.table(ts.pingv4)

ts.tracev4 <- data.frame(epoch = trace_json[[as.character(case)]]$epoch, 
                        #asn_path = trace_json[[as.character(case)]]$asn_path,
                        as_path_change = trace_json[[as.character(case)]]$as_path_change,
                        ifp_simple = trace_json[[as.character(case)]]$ifp_simple, 
                        ifp_bck = trace_json[[as.character(case)]]$ifp_bck,
                        ifp_split = trace_json[[as.character(case)]]$ifp_split)
ts.tracev4 = data.table(ts.tracev4)
asn_path = lapply(trace_json[[as.character(case)]]$asn_path, unlist)
lapply(asn_path, write, sprintf('asn_path_%d.txt', case), append=TRUE, ncolumns=1000)
#write.table(ts.pingv4, file=sprintf('%d.csv',case), sep=';', row.names = F)

pdf(sprintf('../data/graph/case_%d.pdf', case), width = 8, height=4)
g<- ggplot(ts.pingv4[3000:5000], aes(x= anytime(epoch), y=rtt)) + 
  geom_point() +
  #geom_line(col='grey') +
  #geom_point(aes(text=paste("Index:", seq_len(nrow(ts.pingv4[1:100])))), size=.8) +
  geom_vline(xintercept = as.numeric(anytime(ts.pingv4[cp==1,epoch])), col='red', size=.6, alpha=1)+
  geom_vline(xintercept = as.numeric(anytime(ts.pingv4[cp_np==1,epoch])), col='green', size=1.5, alpha=.8, linetype=2)+
  geom_vline(xintercept = as.numeric(anytime(ts.tracev4[as_path_change==1,epoch])), col='orange', size=2.5, alpha=.5) +
  geom_vline(xintercept = as.numeric(anytime(ts.tracev4[ifp_bck==1,epoch])), col='violet', size=2.5, alpha=.5) +
  scale_color_manual(name='', values = c(Poisson='red', NP='green', AS='orange')) +
  scale_x_datetime(date_breaks = "6 hours", date_labels='%Y-%m-%d %Hh') +
  xlab('Time (UTC)')+
  ylab('RTT (ms)')+
  theme(text=element_text(size=16),
        axis.text.x=element_text(size=12,angle = 15, hjust=0.5, vjust=.5),
        legend.position='top')
print(g)
dev.off()

pdf('../data/graph/lAlV_example.pdf', width = 8, height=4)
g<- ggplot(ts.pingv4[1:100], aes(x= anytime(epoch), y=rtt)) + 
    geom_point() +
    #geom_point(aes(text=paste("Index:", seq_len(nrow(ts.pingv4[1:100])))), size=.8) +
    geom_vline(xintercept = as.numeric(anytime(ts.pingv4[cp==1,epoch])), col='red', size=.6, alpha=.8)+
    geom_vline(xintercept = as.numeric(anytime(ts.pingv4[cp_np==1,epoch])), col='green', size=.5, alpha=.6)+
    geom_vline(xintercept = as.numeric(anytime(ts.pingv4[cp_normal==1,epoch])), col='blue', size=1.5, alpha=.3)+
    scale_x_datetime(date_breaks = "1 hours", date_labels='%Y-%m-%d %Hh') +
    xlab('Time (UTC)')+
    ylab('RTT (ms)')+
    theme(text=element_text(size=16),
        axis.text.x=element_text(size=12,angle = 15, hjust=0.5, vjust=.5))
print(g)
dev.off()

#ggplotly(g)

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
g<- ggplot(ts.tracev4) + geom_point(aes(x=anytime(epoch), y=rtt, text=paste("Index:", seq_len(nrow(ts.tracev4)))))
print(g)
ggplotly(g)

# some test with changepoint ----
setwd('~/Documents/rtt_visual/Wenqin/')
ts.pingv4 <- read.table('17783.csv', header = T, sep = ';', dec='.')
ts.pingv4 <- data.frame(epoch = ping_json[[as.character(case)]]$epoch, 
                        rtt = ping_json[[as.character(case)]]$min_rtt)
g<- ggplot(ts.pingv4, aes(x= anytime(epoch), y=rtt)) + 
  geom_point(aes(text=paste("Index:", seq_len(nrow(ts.pingv4)))), size=.8)
print(g)
ggplotly(g)

# plot example artificial trace ----
trace = data.table(read.table('artificial_trace_set1/20.csv', sep=';', dec=',', header = T, stringsAsFactors = F))
number_ticks <- function(n) {function(limits) pretty(limits, n)}

pdf('graph/artificial_trace.pdf', width = 8, height=4)
g<- ggplot(trace[1:2500], aes(x=utctime(epoch), y=rtt)) + geom_line() +
  geom_vline(xintercept = as.numeric(utctime(trace$epoch[(trace$cp)==1])), col='red', size=.5, alpha=.6) +
  scale_x_datetime(date_breaks = "12 hours",date_labels='%Y-%m-%d %Hh')+
  coord_cartesian(ylim=c(150, 500)) +
  xlab('Time')+
  ylab('RTT (ms)')+
  theme(text=element_text(size=16),
        axis.text.x=element_text(angle = 30, hjust=1))
print(g)
dev.off()

nrow(trace)
length(which(trace[1:2500]$cp==1))

# changedetection eval with artificial/real trace ----
res_window <- read.table('../data/eval_antoine.csv', sep=';', header = T)
res_window <- read.table('eval_art.csv', sep=';', header = T)
res_window <- read.table('../data/cpt_eval_real_complete.csv', sep=';', header = T)
res_window$fallout <- res_window$fp / (res_window$len - res_window$changes)
res_window$f1 <- with(res_window, 2*precision*recall/(precision+recall))
res_window$f05 <- with(res_window, 1.25*precision*recall/(0.25*precision+recall))
res_window$f2 <- with(res_window, 5*precision*recall/(4*precision+recall))
res_window$f1_score <- with(res_window, 2*precision*score/(precision+score))
res_window$f05_score <- with(res_window, 1.25*precision*score/(0.25*precision+score))
res_window$f2_score <- with(res_window, 5*precision*score/(4*precision+score))
res_window <- data.table(res_window)

# * trace characters
# average length
res_window[method=='cpt_poisson' & penalty=='MBIC', length(len)]
res_window[method=='cpt_poisson' & penalty=='MBIC', mean(len)]
res_window[method=='cpt_poisson' & penalty=='MBIC', sum(changes)]
# precision
pdf('graph/antoine_precision.pdf', width = 8, height=5)
g <- ggplot(res_window) + stat_ecdf(aes(precision, 
                                        col=as.factor(method),
                                        linetype=as.factor(penalty)), 
                                        geom='step')+
  scale_color_manual(values=c('#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00'), 
                     name="Method",
                     breaks=unique(res_window$method)) +
  scale_linetype_manual(name='Penalty',
                        values = c('solid', 'dotted', 'solid', 'twodash'),
                        breaks=unique(res_window$penalty)) +
  xlab('Precision') +
  ylab('CDF') +
  theme(text=element_text(size=16))
print(g)
dev.off()

g <- ggplot(res_window) + 
  stat_ecdf(aes(precision, col=penalty)) +
  facet_wrap(~method)
g
# recall
pdf('graph/antoine_recall.pdf', width = 8, height=5)
g <- ggplot(res_window) + stat_ecdf(aes(recall, 
                                        col=as.factor(method),
                                        linetype=as.factor(penalty)), 
                                    geom='step')+
  scale_color_manual(values=c('#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00'), 
                     name="Method",
                     breaks=unique(res_window$method)) +
  scale_linetype_manual(name='Penalty',
                        values = c('solid', 'dotted', 'solid', 'twodash'),
                        breaks=unique(res_window$penalty)) +
  xlab('Precision') +
  ylab('CDF') +
  theme(text=element_text(size=16))
print(g)
dev.off()

g <- ggplot(res_window) + 
  stat_ecdf(aes(recall, col=penalty)) +
  facet_wrap(~method)
g
# distance from detection to fact
g <- ggplot(res_window) + stat_ecdf(aes(dis, 
                                        col=as.factor(paste(method, penalty)),
                                        linetype=as.factor(paste(method, penalty))), 
                                    geom='step')
g
g <- ggplot(res_window) + 
  stat_ecdf(aes(dis, col=penalty)) +
  facet_wrap(~method)
g
g <- ggplot(res_window) + geom_density(aes(dis, 
                                           col=as.factor(paste(method, penalty)),
                                           linetype=as.factor(paste(method, penalty))))
g
# score
g <- ggplot(res_window) + stat_ecdf(aes(score, 
                                        col=as.factor(paste(method, penalty)),
                                        linetype=as.factor(paste(method, penalty))), 
                                    geom='step')
g
g <- ggplot(res_window) + 
  stat_ecdf(aes(score, col=penalty)) +
  facet_wrap(~method)
g
g <- ggplot(res_window) + geom_density(aes(score, 
                                           col=as.factor(paste(method, penalty)),
                                           linetype=as.factor(paste(method, penalty))))
g
# f score
g <- ggplot(res_window[penalty %in% c('MBIC', 'human', 'AIC')]) + stat_ecdf(aes(f2, 
                                        col=as.factor(paste(method, penalty))), 
                                    geom='step')
g
g <- ggplot(res_window) + 
  stat_ecdf(aes(f2, col=penalty)) +
  facet_wrap(~method)
g
# f score with weighted recall
pdf('../data/graph/real_f2_weighted.pdf', width = 8, height=4)
g <- ggplot(res_window) + stat_ecdf(aes(f2_score, 
                                        col=as.factor(method),
                                        linetype=as.factor(penalty)), 
                                    geom='step')+
  scale_color_manual(values=c('#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00'), 
                     name="Method",
                     breaks=unique(res_window$method)) +
  scale_linetype_manual(name='Penalty',
                        #values = c('longdash', 'solid','solid', 'dotdash'),
                        values = c('longdash', 'solid','dotted', 'dotdash'),
                        breaks=unique(res_window$penalty)) +
  coord_cartesian(xlim=c(0,1)) +
  xlab('F2 score with weighted recall') +
  ylab('CDF') +
  theme(text=element_text(size=16))
print(g)
dev.off()

g <- ggplot(res_window) + 
  stat_ecdf(aes(f2_score, col=penalty)) +
  facet_wrap(~method)
g



# rtt path change correlation ----

overview_poisson = data.table(read.table("cor_overview_v4_cpt_poisson.csv", sep=';', header = T, stringsAsFactors = F))
overview_np = data.table(read.table("cor_overview_v4_cpt_np.csv", sep=';', header = T, stringsAsFactors = F))
overview_normal = data.table(read.table("cor_overview_v4_cpt_normal.csv", sep=';', header = T, stringsAsFactors = F))

rtt_view = data.table(read.table("cor_rtt_ch_v4_cpt_poisson.csv", sep=';', header=T, stringsAsFactors = F))
path_view = data.table(read.table("cor_path_ch_v4.csv", sep=';', header=T, stringsAsFactors = F))

# one probe per as with max traceroute valide length
rtt.tracev4 <- merge(rtt.tracev4, probe.meta[, probe_id, asn_v4], by='probe_id', all=TRUE)
one_probe_as <- rtt.tracev4[, .SD[which.max(valid_length)], by=asn_v4][,probe_id]
one_probe_as <- intersect(one_probe_as, probe.meta[!address_v4=='None', probe_id])

length(one_probe_as)

write.table(rtt.tracev4[, .SD[which.max(valid_length)], by=asn_v4][,.(probe_id, asn_v4)], file = 'one_probe_per_as.csv', sep=';',
            row.names = F)

# * rtt change NUMBER distribution of three detection method ----
overview_m = rbind(overview_poisson, overview_np, overview_normal)
bks = c(10, 50, 100, 200, 500, 1000, 2000, 8000)
pdf('../data/graph/rtt_ch_count_cdf_cmp.pdf', width = 4, height=4)
g <- ggplot(overview_m[pch_method=='ifp_bck' & trace_len > 30000]) + 
  #stat_ecdf(aes(log_mod(cpt_count), col=cpt_method))+
  geom_density(aes(log_mod(cpt_count), col=cpt_method)) +
  scale_x_continuous(breaks=log_mod(bks), labels = bks) +
  coord_cartesian(xlim = log_mod(c(10, 8000))) +
  scale_color_discrete(name='', breaks=c('cpt_normal&MBIC', 'cpt_np&MBIC', 'cpt_poisson&MBIC'),
                       labels=c('Normal', 'NP', 'Poisson')) +
  xlab('Number of RTT changes per probe') +
  #ylab('Density estimation') +
  ylab('CDF')+
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 20, hjust=0.5, vjust=.5))
print(g)
dev.off()

# * path change NUMBER distribution ----
bks = c(0, 2, 10, 20, 50, 100, 200, 500, 1000, 4000)
pdf('../data/graph/path_ch_count_density_cmp.pdf', width = 4, height=4)
g <- ggplot(overview_np[pch_method %in% c('as_path_change', 'ifp_bck') & probe %in% one_probe_as]) + 
  #stat_ecdf(aes(log_mod(as.numeric(tp)+as.numeric(fp)), col=pch_method)) +
  geom_density(aes(log_mod(as.numeric(tp)+as.numeric(fp)), col=pch_method)) +
  scale_x_continuous(breaks=log_mod(bks), labels = bks) +
  #coord_cartesian(xlim=c(0, 400)) +
  scale_color_discrete(name='', breaks=c('as_path_change', 'ifp_bck'), labels=c('AS path', 'IFP')) +
  xlab('Number of path changes per probe') +
  ylab('Density') +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 25, hjust=0.5, vjust=.5),
        legend.text=element_text(size=12))
print(g)
dev.off()

overview_np[pch_method =='as_path_change' & probe %in% one_probe_as & as.numeric(tp)+as.numeric(fp) > 500, length(probe)]
quantile(overview_np[pch_method =='ifp_bck' & probe %in% one_probe_as, as.numeric(tp)+as.numeric(fp)])

# * AS path change NUMBER and PRECISION ----
bks = c(0, 2, 10, 20, 50, 100, 200, 500, 1000, 4000)
pdf('../data/graph/as_path_ch_precision_np.pdf', width = 4, height=4)
g <- ggplot(overview_poisson[pch_method == 'as_path_change' & trace_len > 30000 & probe %in% one_probe_as],
            aes(x=(as.numeric(tp)+as.numeric(fp)), y=as.numeric(precision))) + 
  geom_point(aes(text=paste("Probe:", probe)), size=1, alpha=.3, col='#e41a1c') +
  #geom_smooth() +
  geom_density2d()+
  scale_x_continuous(trans = log10_trans(), breaks = bks) +
  #coord_cartesian(xlim=c(0, 200)) +
  #coord_cartesian(xlim=c(0, 4000)) +
  #scale_color_discrete(name='Patch change method') +
  xlab('Number of AS path changes') +
  ylab('Precision') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 25, hjust=0.5, vjust=.5))
print(g)
dev.off()
ggplotly(g)


# * Find probes have AS change number between 100 200 and precision < 0.1 ----
temp <- overview_poisson[pch_method == 'as_path_change' & 
                   trace_len > 30000 & probe %in% one_probe_as & 
                   as.numeric(tp)+as.numeric(fp) > 100 &
                   as.numeric(tp)+as.numeric(fp) < 200 &
                   precision < 0.1]
temp1 <- probe.meta[probe_id %in% temp$probe]
temp2 <- probe.meta[probe_id %in% one_probe_as & country_code == 'NL']
temp3 <- overview_poisson[probe %in% temp2$probe_id & pch_method == 'as_path_change']


# * IFP change NUMBER and PRECISION ----
bks = c(0, 20, 50, 80, 100, 150, 200, 250, 300, 350)
pdf('../data/graph/ifp_ch_precision_poisson.pdf', width = 4, height=4)
g <- ggplot(overview_poisson[pch_method == 'ifp_bck' & trace_len > 30000 & probe %in% one_probe_as],
            aes(x=(as.numeric(tp)+as.numeric(fp)), y=as.numeric(precision))) + 
  geom_point(aes(text=paste("Probe:", probe)), size=1, alpha=.3, col='#e41a1c') +
  #geom_smooth() +
  geom_density2d()+
  scale_x_continuous(breaks = bks) +
  coord_cartesian(ylim=c(0, 1)) +
  xlab('Number of IFP changes') +
  ylab('Precision') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 25, hjust=0.5, vjust=.5))
print(g)
dev.off()
ggplotly(g)

pdf('../data/graph/ifp_ch_vs_ip_path.pdf', width = 4, height=4)
g <- ggplot(merge(overview_poisson[pch_method == 'ifp_bck' & probe %in% one_probe_as & trace_len > 30000],
                  topo_stat, by='probe'),
            aes(y=as.numeric(tp) + as.numeric(fp), x=ip_path_count)) +
  geom_point(alpha=.2, col='#e41a1c') +
  geom_density2d()+
  scale_x_continuous(trans = log10_trans(), breaks = c(2, 16, 50, 100, 200, 500, 1000)) +
  scale_y_continuous(breaks = c(0, 20, 50, 80, 100, 150, 200, 250, 300, 350)) +
  xlab('IP paths per probe') +
  ylab('Number of IFP changes') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 25, hjust=0.5, vjust=.5))
print(g)
dev.off()

pdf('../data/graph/ifp_ch_precision_vs_ip_path.pdf', width = 4, height=4)
g <- ggplot(merge(overview_np[pch_method == 'ifp_bck' & probe %in% one_probe_as & trace_len > 30000],
                  topo_stat, by='probe'),
            aes(y=as.numeric(precision), x=ip_path_count)) +
  geom_point(alpha=.2, col='#e41a1c') +
  geom_density2d()+
  scale_x_continuous(trans = log10_trans(), breaks = c(2, 16, 50, 100, 200, 500, 1000)) +
  coord_cartesian(ylim=c(0,1)) +
  xlab('IP paths per probe') +
  ylab('Precision') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 25, hjust=0.5, vjust=.5))
print(g)
dev.off()

topo_stat[probe %in% one_probe_as & ip_path_count > 16, length(probe)] /topo_stat[probe %in% one_probe_as, length(probe)]

quantile(topo_stat[probe %in% one_probe_as, ip_path_count], prob = c(.05, .1, .25, .5, .75, .95, 1), type=8)

g <- ggplot(merge(overview_np[pch_method == 'ifp_bck' & probe %in% one_probe_as & trace_len > 30000],
                  topo_stat, by='probe')) +
  geom_point(aes(y=(as.numeric(tp)+as.numeric(fp)), x=ip_path_count, col=as.numeric(precision), text=paste("Probe:", probe)), alpha=.3) +
  scale_x_continuous(trans = log10_trans(), breaks = c(16, 50, 100, 200, 500, 1000))
g
ggplotly(g)

# * IFP change precision gain with BCK and SPLIT ----
# the precision gain of split is very marginal. should skip it in paper
bck_gain_poisson <- overview_poisson[pch_method=='ifp_bck', as.numeric(precision)]/overview_poisson[pch_method=='ifp_simple', as.numeric(precision)]
bck_gain_np <- overview_np[pch_method=='ifp_bck', as.numeric(precision)]/overview_np[pch_method=='ifp_simple', as.numeric(precision)]
ifp_gain <- data.table(probe = overview_poisson[pch_method=='ifp_split',probe], 
                       trace_len = overview_np[pch_method=='ifp_split',trace_len],
                       Poisson=bck_gain_poisson, NP=bck_gain_np)
ifp_gain <- melt(ifp_gain, measure.vars = c('Poisson', 'NP'), variable.name = 'method', value.name = "precision_gain")

pdf('../data/graph/ifp_bck_ch_precision_gain_cdf.pdf', width = 6, height=3)
g <- ggplot(ifp_gain[trace_len > 30000 & probe %in% one_probe_as]) + 
  stat_ecdf(aes(precision_gain, col=method)) +
  scale_color_discrete(name='') +
  xlab('Precision ratio: IFP bck/IFP fwd') +
  ylab('CDF') +
  theme(text=element_text(size=16), legend.position='top')
print(g)
dev.off()

# * compare the RTT change CHARACTER discovered by the three method ----
write.table(rtt_view[pch_method=='ifp_bck',.(cpt_method, delta_median, delta_std)], file = 'cpt_chara_np.csv', sep = ';', row.names = F)
write.table(rtt_view[pch_method=='ifp_bck',.(cpt_method, delta_median, delta_std)], file = 'cpt_chara_normal.csv', sep = ';', row.names = F)
write.table(rtt_view[pch_method=='ifp_bck',.(cpt_method, delta_median, delta_std)], file = 'cpt_chara_poisson.csv', sep = ';', row.names = F)

rtt_np = read.table('cpt_chara_np.csv', sep = ';', header = T, stringsAsFactors = F)
rtt_poisson = read.table('cpt_chara_poisson.csv', sep = ';', header = T, stringsAsFactors = F)
rtt_normal = read.table('cpt_chara_normal.csv', sep = ';', header = T, stringsAsFactors = F)
rtt_bind = data.table(rbind(rtt_np, rtt_poisson, rtt_normal))

pdf('../data/graph/rtt_ch_chara_cmp.pdf', width = 12, height=4)
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_bind[delta_median < 1000 & delta_std < 500], 
            aes(x=delta_median, y=delta_std)) +
  scale_x_continuous(trans = log2_trans(), breaks=xbk) +
  scale_y_continuous(trans = log2_trans(), breaks=ybk) +
  geom_density2d() +
  facet_wrap(~cpt_method, ncol = 3)+
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)
dev.off()


# * lAlV, lAhV, hAlV, hAhV ----
cpt_m = 'cpt_poisson&MBIC'
rtt_bind[cpt_method==cpt_m & delta_median < 5 & delta_std < 5, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]
rtt_bind[cpt_method==cpt_m & delta_median < 5 & delta_std > 50, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]
rtt_bind[cpt_method==cpt_m & delta_median > 100 & delta_std < 5, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]
rtt_bind[cpt_method==cpt_m & delta_median > 100 & delta_std > 50, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]


# * how to find RTT changepoint not matched to ifp nor to AS path changes ----
# add cpt identifier
rtt_view[,ch_id := paste(probe, i, sep='_')]
# merge based on identifier
rtt_m = merge(rtt_view[pch_method=='ifp_split', .(ch_id, probe, delta_median, delta_std, matched)], 
              rtt_view[pch_method=='as_path_change', .(ch_id, matched)],
              by='ch_id', suffixes = c('_ifp', '_as'))
rtt_m[, path_ch_m := as.logical(matched_ifp) | as.logical(matched_as)]

path_view[,ch_id := paste(probe, pch_idx, sep='_')]
path_m = merge(path_view[pch_method=='ifp_split', .(ch_id, probe, pch_method, matched, delta_median, delta_std)],
               path_view[pch_method=='as_path_change', .(ch_id, pch_method, probe, matched, delta_median, delta_std)],
               all = TRUE, by='ch_id', suffixes=c('_ifp', '_as'))
path_m[,':=' (type= ifelse(!is.na(pch_method_as), 'AS path', 'IFP'))]

# portion of AS path change is important
path_m[type=='AS path', length(ch_id)]/path_m[,length(ch_id)]


rtt_m[delta_median < 1000 & delta_std < 500, length(ch_id)]/nrow(rtt_m)
rtt_m[delta_median < 1000 & delta_std < 500 & path_ch_m == TRUE, length(ch_id)]/rtt_m[delta_median < 1000 & delta_std < 500, length(ch_id)]
rtt_m[delta_median < 1000 & delta_std < 500 & path_ch_m == FALSE, length(ch_id)]/rtt_m[delta_median < 1000 & delta_std < 500, length(ch_id)]
rtt_m[delta_median < 1000 & delta_std < 500 & path_ch_m == TRUE & matched_as == 'True', length(ch_id)]/rtt_m[delta_median < 1000 & delta_std < 500 & path_ch_m == TRUE, length(ch_id)]

rtt_m[path_ch_m == TRUE & matched_as == 'True', length(ch_id)]/nrow(rtt_m)
rtt_m[path_ch_m == TRUE & ! matched_as == 'True', length(ch_id)]/nrow(rtt_m)
rtt_m[!path_ch_m == TRUE,  length(ch_id)]/nrow(rtt_m)

# the proportion of RTT changes matched to AS path change is kind of high, find out why

# * where does cpt low level high variance change come from ----
rtt_m[delta_median < 5 & delta_std > 50, length(ch_id)]/nrow(rtt_m)
# how many such changes each probe trace have, the distribution is highly skewed
# only few probes have many of them, find what are they
g <- ggplot(rtt_m[delta_median < 5 & delta_std > 50, .(count=length(ch_id)), by=probe]) + stat_ecdf(aes(count))
g
high.var <- rtt_m[delta_median < 5 & delta_std > 50, .(count=length(ch_id)), by=probe][order(count, decreasing = T)]
quantile(high.var$count, probs = c(.10,.25,.5,.75,.9,.95, .99), type = 8)
# plot the rtt trace of these probes
# investigated 12937 the measurment is frequent dotted as timeout

# * where does cpt median [100, 200], std [50, 100] come from ----
rtt_m[delta_median > 100 & delta_std >50 , length(ch_id)]/nrow(rtt_m)
g <- ggplot(rtt_m[delta_median > 100 & delta_std >50, .(count=length(ch_id)), by=probe]) + stat_ecdf(aes(count))
g
both.high <- rtt_m[delta_median > 100 & delta_std >50, .(count=length(ch_id)), by=probe][order(count, decreasing = T)]
quantile(both.high$count, probs = .95)
# investigated 10342, 17272, periodic long lasting congestion, cpt_poisson over sensitive, cpt_np is great
# investigated 12385, many timeout measurements
# investigated 26326 with np, many timeout segment, when with valid value, the variance is big


# * find probes potentially with large amplitude congestions ----
rtt_m[delta_median > 30 & delta_median < 150 & delta_std > 5 & delta_std < 50 & path_ch_m == FALSE, .(count=length(ch_id)), by=probe][order(count, decreasing = T)][20:30]

# * cleaning criteria ----
# valide data length > 30000
# top 5% probe with most high variance change
# top 5% probe with most high level and high variance change
a <- as.numeric(rtt.pingv4[valid_length> 30000, probe_id]) 
b <- as.numeric(high.var[count < 100, probe]) 
c <- as.numeric(both.high[count < 100, probe]) 

scope <- intersect(a, intersect(b, c))

# * median RTT distribution per probe ----
pdf('../data/graph/rtt_median_density.pdf', width = 6, height=3)
g <- ggplot(rtt.pingv4[valid_length>30000]) + 
  geom_density(aes(as.integer(median))) +
  scale_x_continuous(breaks=c(0, 30, 50, 80, 100, 150, 200, 250, 300, 400, 800, 100)) + 
  xlab('Median RTT per probe') +
  ylab('Density estimation') +
  theme(text=element_text(size=16),
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)
dev.off()


# * median diff ~ std diff ----
pdf('../data/graph/rtt_ch_median_vs_std_np_scope.pdf', width = 8, height=4)
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_m[delta_median < 1000 & delta_std < 500 & probe %in% one_probe_as], 
            aes(x=delta_median, y=delta_std)) +
  scale_x_continuous(trans = log2_trans(), breaks=xbk) +
  scale_y_continuous(trans = log2_trans(), breaks=ybk) +
  geom_density2d() +
  facet_wrap(~path_ch_m, ncol = 2)+
  scale_color_discrete(name='Matched to path change') +
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)
dev.off()

# * median vs std for matched ones ----

pdf('../data/graph/rtt_ch_matched_median_vs_std_np_scope.pdf', width = 8, height=4)
facet_labeller <- function(variable,value){
  return(list('True'='AS path', 'False'='IFP')[value])
}
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_m[path_ch_m == TRUE & delta_median < 1000 & delta_std < 500 & probe %in% one_probe_as], 
            aes(x=delta_median, y=delta_std, 50)) +
  scale_x_continuous(trans = log2_trans(), breaks=xbk) +
  scale_y_continuous(trans = log2_trans(), breaks=ybk) +
  geom_density2d() +
  facet_wrap(~matched_as, ncol = 2, labeller = facet_labeller)+
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)
dev.off()


# * median diff distribution Matched or not matched ----
pdf('graph/rtt_ch_delta_median_cdf.pdf', width = 8, height=4)
g <- ggplot(rtt_m[delta_median<1000 & probe %in% scope_pb]) + 
  stat_ecdf(aes(delta_median, col=as.factor(path_ch_m))) +
  scale_color_discrete(name='Matched to path change') +
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('CDF') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()

pdf('graph/rtt_ch_delta_median_density.pdf', width = 8, height=4)
g <- ggplot(rtt_m[delta_median<1000 & probe %in% scope_pb]) + 
  geom_density(aes(delta_median, col=as.factor(path_ch_m))) +
  scale_x_continuous(trans = log2_trans(), breaks = c(5, 10, 20, 50, 100, 200, 500, 1000)) +
  coord_cartesian(xlim=c(1,1000)) +
  scale_color_discrete(name='Matched to path change') +
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('Density estimation') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()

# * std diff distribution matched or not matched ----
pdf('graph/rtt_ch_delta_std_cdf.pdf', width = 8, height=4)
g <- ggplot(rtt_m[delta_std<500 & probe %in% scope_pb]) + 
  stat_ecdf(aes(delta_std, col=as.factor(path_ch_m))) +
  scale_color_discrete(name='Matched to path change') +
  xlab('RTT std difference across changepoints (ms)') +
  ylab('CDF') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()

pdf('graph/rtt_ch_delta_std_density.pdf', width = 8, height=4)
g <- ggplot(rtt_m[delta_std<500 & probe %in% scope_pb]) + 
  geom_density(aes(delta_std, col=as.factor(path_ch_m))) +
  scale_x_continuous(trans = log2_trans(), breaks = c(5, 10, 20, 50, 100, 200, 500)) +
  coord_cartesian(xlim=c(1,500)) +
  scale_color_discrete(name='Matched to path change') +
  xlab('RTT std difference across changepoints (ms)') +
  ylab('Density estimation') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()

# * median difference bettwen IFP and AS matched ----
pdf('graph/rtt_ch_matched_cmp_median.pdf', width = 8, height=4)
g <- ggplot(rtt_m[path_ch_m==TRUE & delta_median < 1000]) + 
  stat_ecdf(aes(delta_median, col=as.factor(matched_as))) +
  scale_color_discrete(name='Path change type', breaks=c('True', 'False'),
                       labels=c('AS path', 'IFP')) +
  xlab('Median RTT difference across matched changepoints (ms)') +
  ylab('CDF') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()

pdf('graph/rtt_ch_matched_cmp_median_density.pdf', width = 8, height=4)
g <- ggplot(rtt_m[path_ch_m==TRUE & delta_median < 1000]) + 
  geom_density(aes(delta_median, col=as.factor(matched_as))) +
  scale_x_continuous(trans = log2_trans(), breaks = c(5, 10, 20, 50, 100, 200, 500, 1000)) +
  coord_cartesian(xlim=c(1,1000)) +
  scale_color_discrete(name='Path change type', breaks=c('True', 'False'),
                       labels=c('AS path', 'IFP')) +
  xlab('Median RTT difference across matched changepoints (ms)') +
  ylab('Density estimation') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()

# * std difference bettwen IFP and AS matched ----
pdf('graph/rtt_ch_matched_cmp_std.pdf', width = 8, height=4)
g <- ggplot(rtt_m[path_ch_m==TRUE & delta_std < 500]) + 
  stat_ecdf(aes(delta_std, col=as.factor(matched_as))) +
  scale_color_discrete(name='Path change type', breaks=c('True', 'False'),
                       labels=c('AS path', 'IFP')) +
  xlab('RTT std difference across matched changepoints (ms)') +
  ylab('CDF') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()

pdf('graph/rtt_ch_matched_cmp_std_density.pdf', width = 8, height=4)
g <- ggplot(rtt_m[path_ch_m==TRUE & delta_std < 500]) + 
  geom_density(aes(delta_std, col=as.factor(matched_as))) +
  scale_x_continuous(trans = log2_trans(), breaks = c(5, 10, 20, 50, 100, 200, 500)) +
  coord_cartesian(xlim=c(1,500)) +
  scale_color_discrete(name='Path change type', breaks=c('True', 'False'),
                       labels=c('AS path', 'IFP')) +
  xlab('RTT std difference across matched changepoints (ms)') +
  ylab('Density estimation') +
  theme(text=element_text(size=16), legend.position="top")
print(g)
dev.off()


g <- ggplot(overview[pch_method=='ifp_split' & precision != 'None']) + stat_ecdf(aes(as.numeric(precision)), geom = 'step')
g

g <- ggplot(rtt_view[pch_method=='ifp_split' & matched == 'False' & delta_std<1000]) +
  geom_density(aes(as.numeric(delta_std))) +
  scale_x_continuous(trans = log10_trans())
g


