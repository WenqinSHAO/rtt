## code for exploratory analysis
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
# since all the data cannot be stored locally, data on the server can be store in a specific folder
setwd(data.dir)
#setwd("/Users/wenqin/Documents/internet_rtt/remote_data/")

# Probe meta; the information concerning the probe
probe.meta <- data.table(read.csv2("pb.csv", sep=';', dec='.', stringsAsFactors = F))

# Probe to chunk idx
dic.v4 <- data.table(read.csv2('pb_chunk_index_v4.csv', stringsAsFactors = F))
dic.v6 <- data.table(read.csv2('pb_chunk_index_v6.csv', stringsAsFactors = F))

# Basics ----
# * probe with system-ipv4/6-works tag
probe.v4.work <- probe.meta[grepl('ipv4-works', system_tags), probe_id]
probe.v6.work <- probe.meta[grepl('ipv6-works', system_tags), probe_id]

# * AS coverage by probes with v4/v6 working probes
asnv4.v4works <- probe.meta[grepl('ipv4-works', system_tags), .(probe_count=length(probe_id)), by=asn_v4][order(probe_count, decreasing = T)]
asnv6.v6works <- probe.meta[grepl('ipv6-works', system_tags), .(probe_count=length(probe_id)), by=asn_v4][order(probe_count, decreasing = T)]

# * RTT summary
rtt.pingv4 <- data.table(read.csv2("rtt_summary_1010_of_v4.csv", header = T, stringsAsFactors = F, na.strings = "None"))
rtt.tracev4 <- data.table(read.csv2("rtt_summary_5010_of_v4.csv", header = T, stringsAsFactors = F, na.strings = "None"))
rtt.pingv6 <- data.table(read.csv2("rtt_summary_2010_of_v6.csv", header = T, stringsAsFactors = F, na.strings = "None"))
rtt.tracev6 <- data.table(read.csv2("rtt_summary_6010_of_v6.csv", header = T, stringsAsFactors = F, na.strings = "None"))


# One probe per as with max traceroute valide length
rtt.tracev4 <- merge(rtt.tracev4, probe.meta[, probe_id, asn_v4], by='probe_id', all=TRUE)
one_probe_as <- rtt.tracev4[, .SD[which.max(valid_length)], by=asn_v4][,probe_id]
one_probe_as <- intersect(one_probe_as, probe.meta[!address_v4=='None', probe_id])

length(one_probe_as)

write.table(rtt.tracev4[, .SD[which.max(valid_length)], by=asn_v4][,.(probe_id, asn_v4)], file = 'one_probe_per_as.csv', sep=';',
            row.names = F)

nrow(rtt.pingv4)
probe.meta[probe_id %in% one_probe_as, length(unique(asn_v4))]
probe.meta[probe_id %in% one_probe_as, length(unique(country_code))]
sum(rtt.pingv4$raw_length, na.rm = T)
sum(rtt.tracev4$raw_length, na.rm = T)

u_as <- read.table("unique_as_v4.txt")
u_ixp <- read.table("unique_ixp_v4.txt", sep = '|')
u_path <- read.table("unique_as_path_v4.txt", sep = '|')

# * topo summary
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
case = 21600
case = 10663
case = 21328
case = 26106
case = 15902

case = 12937 # high var cpts
case = 13691 # high var cpts
case = 11650 # high var cpts
case = 12385 #
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
case = 28002

case = 10015 # as path ch 100 200
case = 11150 # as path ch 100 200
case = 6038 # as path ch 100 200 

case = 21625
case = 18359
case = 23998

# case clean as path change realted to timeout?
case = 20119 # frequent as path change that matters

# case AS path match with np poisson big difference
# poisson better precision than NP
case = 12833 # frequent as LB
case = 24900 # frequent provider LB, even more frequent and large value RTT change
case = 21600 # noisy RTT trace, a few path change easily matched with Poisson change tend to be overly sensitive in this case
case = 23167 # RTT trace not very noisy, oscialtes frequently betwen two values 10ms difference; much more AS path change than RTT changs
case = 11037 # RTT not very noisy; have very good ex of congestion; as path change with timeout but not level diff; poisson detects timeout while NP ignores.
case = 20854 # Frequent timeouts -> much more poisson cpt than np; not really as path change non responding hop

# np matches better with as path change
case = 6032 # much more as path change than rtt change; more np cpt than poisson cpt; thus np matches better; as path change no consequence
case = 18917 # not so noisy RTT trace; more as path change than rtt change; as path change due to no responding as; some have consequence congestion like form
case = 18494 # as path change on rtt small;

# ixp change
case = 28761
case = 6064
case = 20899
case = 28801
  
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
                        as_path_change_ixp = trace_json[[as.character(case)]]$as_path_change_ixp,
                        ifp_simple = trace_json[[as.character(case)]]$ifp_simple, 
                        ifp_bck = trace_json[[as.character(case)]]$ifp_bck,
                        ifp_split = trace_json[[as.character(case)]]$ifp_split)
ts.tracev4 = data.table(ts.tracev4)
asn_path = lapply(trace_json[[as.character(case)]]$asn_path, unlist)
empty = lapply(asn_path, write, sprintf('asn_path_%d.txt', case), append=TRUE, ncolumns=1000)
#write.table(ts.pingv4, file=sprintf('%d.csv',case), sep=';', row.names = F)

pdf(sprintf('../data/graph/case_%d.pdf', case), width = 8, height=2.5)
g<- ggplot(ts.pingv4[200:1000], aes(x= anytime(epoch), y=rtt)) + 
  geom_point() +
  #geom_line(col='grey') +
  #geom_point(aes(text=paste("Index:", seq_len(nrow(ts.pingv4[1:100])))), size=.8) +
  geom_vline(xintercept = as.numeric(anytime(ts.pingv4[cp==1,epoch])), col='red', size=.9, alpha=1)+
  geom_vline(xintercept = as.numeric(anytime(ts.pingv4[cp_np==1,epoch])), col='green', size=1.5, alpha=.8, linetype=2)+
  geom_vline(xintercept = as.numeric(anytime(ts.tracev4[as_path_change==1,epoch])), col='orange', size=2.5, alpha=.5) +
  #geom_vline(xintercept = as.numeric(anytime(ts.tracev4[ifp_bck==1,epoch])), col='violet', size=2.5, alpha=.5) +
  geom_vline(xintercept = as.numeric(anytime(ts.tracev4[as_path_change_ixp==1,epoch])), col='#08519c', size=2.5, alpha=.5) +
  #scale_color_manual(name='', values = c(Poisson='red', NP='green', AS='orange')) +
  scale_x_datetime(date_breaks = "6 hours", date_labels='%Y-%m-%d %Hh') +
  xlab('Time (UTC)')+
  ylab('RTT (ms)')+
  theme(text=element_text(size=16),
        axis.text.x=element_text(size=12,angle = 15, hjust=0.5, vjust=.5),
        legend.position='top')
print(g)
dev.off()

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

# plot example artificial trace ----
trace = data.table(read.table('../data/artificial_trace_set1_ground_fact/20.csv', sep=';', dec=',', header = T, stringsAsFactors = F))
number_ticks <- function(n) {function(limits) pretty(limits, n)}

pdf('../data/graph/artificial_trace.pdf', width = 8, height=3)
g<- ggplot(trace[1:2500], aes(x=utctime(epoch), y=rtt)) + geom_line() +
  geom_vline(xintercept = as.numeric(utctime(trace$epoch[(trace$cp)==1])), col='red', size=.5, alpha=.6) +
  scale_x_datetime(date_breaks = "12 hours",date_labels='%Y-%m-%d %Hh')+
  coord_cartesian(ylim=c(150, 500)) +
  xlab('Time')+
  ylab('RTT (ms)')+
  theme_bw()+
  theme(text=element_text(size=16),
        axis.text.x=element_text(angle = 30, hjust=1))
print(g)
dev.off()

nrow(trace)
length(which(trace[1:2500]$cp==1))

# Evaluation of changepoint method ----
# human labeller score
res_window <- read.table('../data/eval_antoine.csv', sep=';', header = T, na.strings = 'None', stringsAsFactors = F)
# method eval on a large artifical dataset
res_window <- read.table('eval_art.csv', sep=';', header = T)
# method eval on human labeled real traces
res_window <- read.table('../data/cpt_eval_real.csv', sep=';', header = T, na.strings = 'None', stringsAsFactors = F)
# the following can be simplified with data.table gramma;
res_window <- read.table('../data/eval_real_gamma.csv', sep=';', header = T, na.strings = 'None', stringsAsFactors = F)

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

# * graph for evaluation on artificial trace ----
pdf('../data/graph/antoine_eval.pdf', width = 6, height=3)
g <- ggplot(melt(res_window[method=='human', .(file, precision, score, f2_score)], id.vars = 'file')) +
  stat_ecdf(aes(value, col=variable)) +
  coord_cartesian(xlim=c(0,1))+
  scale_color_discrete(name='', breaks=c('precision', 'score', 'f2_score'), labels=c('Precision', 'Recall_w', 'F2'))+
  xlab('Value') +
  ylab('CDF')+
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top', legend.text=element_text(size=12), legend.key=element_blank())
print(g)
dev.off()

# * graph for method evaluationon real rtt traces ----
lab = c('precision' = 'Precision', 'recall'='Recall', 'score'='Recall_w', 'f2'='F2', 'f2_score'='F2')
res_window[,':='(setting = paste(method, penalty, sep = '&'))]
res_window[tp==0, ':=' (precision=0, recall=0, score=0, f2=0, f2_score=0, setting=0)]
pdf('../data/graph/real_eval.pdf', width = 12, height=4)
g <- ggplot(melt(res_window[setting %in% c('cpt_normal&MBIC', 'cpt_poisson&MBIC', 'cpt_poisson_naive&AIC',
                                      'cpt_exp&AIC', 'cpt_gamma&AIC', 'cpt_np&MBIC'), .(file, precision, recall, score, f2, f2_score, setting)], 
                 id.vars = c('file', 'setting'), measure.vars = c('precision', 'score', 'f2_score'))) + 
  stat_ecdf(aes(value, col=setting)) +
  #scale_color_brewer(type='qual') +
  scale_color_manual(name='', values = c('#7fc97f','#beaed4','#fdc086','#666666','#386cb0','#f0027f')) +
  guides(colour = guide_legend(nrow=1, override.aes = list(size=3))) +
  coord_cartesian(xlim=c(0,1)) +
  facet_wrap(~variable, nrow=1, labeller = as_labeller(lab)) +
  xlab('Values') +
  ylab('CDF') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top', legend.key=element_blank(), legend.text = element_text(size=12) )
print(g)
dev.off()


lab = c('precision' = 'Precision', 'recall'='Recall', 'score'='Recall_w', 'f2'='F2', 'f2_score'='F2')
res_window[,':='(setting = paste(method, penalty, sep = '&'))]
res_window[tp==0, ':=' (precision=0, recall=0, score=0, f2=0, f2_score=0, setting=0)]
pdf('../data/graph/real_eval.pdf', width = 12, height=4)
g <- ggplot(melt(res_window[setting %in% c('cpt_normal&MBIC', 'cpt_poisson&MBIC', 'cpt_poisson_naive&AIC',
                                           'cpt_exp&AIC', 'cpt_np&MBIC'), .(file, precision, recall, score, f2, f2_score, setting)], 
                 id.vars = c('file', 'setting'), measure.vars = c('precision', 'score', 'f2_score'))) + 
  stat_ecdf(aes(value, col=setting)) +
  #scale_color_brewer(type='qual') +
  scale_color_manual(name='', values = c('#7fc97f','#fdc086','#666666','#386cb0','#f0027f')) +
  guides(colour = guide_legend(nrow=1, override.aes = list(size=3))) +
  coord_cartesian(xlim=c(0,1)) +
  facet_wrap(~variable, nrow=1, labeller = as_labeller(lab)) +
  xlab('Values') +
  ylab('CDF') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top', legend.key=element_blank(), legend.text = element_text(size=12) )
print(g)
dev.off()


g <- ggplot(res_window) + 
  stat_ecdf(aes(f2_score, col=penalty)) +
  facet_wrap(~method)
g

g <- ggplot(melt(res_window[setting %in% c('cpt_gamma%1&AIC', 'cpt_gamma%10&MBIC', 'cpt_gamma%20&MBIC',
                                           'cpt_gamma%30&MBIC', 'cpt_gamma%50&MBIC',
                                           'cpt_gamma%adpt&MBIC', 'cpt_np&MBIC', 'cpt_poisson&MBIC'), 
                            .(file, precision, recall, score, f2, f2_score, setting)], 
                 id.vars = c('file', 'setting'), measure.vars = c('precision', 'score', 'f2_score'))) + 
  stat_ecdf(aes(value, col=setting)) +
  scale_color_brewer(type='qual') +
  guides(colour = guide_legend(nrow=1, override.aes = list(size=3))) +
  coord_cartesian(xlim=c(0,1)) +
  facet_wrap(~variable, nrow=1, labeller = as_labeller(lab)) +
  xlab('Values') +
  ylab('CDF') +
  theme(text=element_text(size=16), legend.position='top', legend.key=element_blank(), legend.text = element_text(size=12) )
print(g)


# RTT and path change and correlation ----
overview_poisson = data.table(read.table("cor_overview_v4_cpt_poisson.csv", sep=';', header = T, stringsAsFactors = F))
overview_np = data.table(read.table("cor_overview_v4_cpt_np.csv", sep=';', header = T, stringsAsFactors = F))

# * rtt change NUMBER distribution of three detection method ----
overview_m = rbind(overview_poisson, overview_np)
bks = c(10, 50, 100, 200, 500, 1000, 2000, 8000)
pdf('../data/graph/rtt_ch_count_density_cmp.pdf', width = 4, height=3)
g <- ggplot(overview_m[pch_method=='ifp_bck' & trace_len > 30000]) + 
  #stat_ecdf(aes(log_mod(cpt_count), col=cpt_method))+
  geom_density(aes(log_mod(cpt_count), col=cpt_method)) +
  scale_x_continuous(breaks=log_mod(bks), labels = bks) +
  coord_cartesian(xlim = log_mod(c(10, 8000))) +
  scale_color_discrete(name='', breaks=c('cpt_normal&MBIC', 'cpt_np&MBIC', 'cpt_poisson&MBIC'),
                       labels=c('Normal', 'NP', 'Poisson')) +
  xlab('Number of RTT changes per probe') +
  ylab('Density estimation') +
  #ylab('CDF') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 20, hjust=0.5, vjust=.5), legend.key=element_blank())
print(g)
dev.off()

overview_np[trace_len > 3000 & pch_method =='ifp_bck', sum(cpt_count)]
overview_np[trace_len > 3000 & pch_method =='ifp_bck', median(cpt_count)]
overview_poisson[trace_len > 3000 & pch_method =='ifp_bck', sum(cpt_count)]
overview_poisson[trace_len > 3000 & pch_method =='ifp_bck', median(cpt_count)]

overview_poisson[trace_len > 3000 & pch_method =='ifp_bck' & cpt_count > 500, length(probe)]/overview_poisson[trace_len > 3000 & pch_method =='ifp_bck', length(probe)]
overview_np[trace_len > 3000 & pch_method =='ifp_bck' & cpt_count > 500, length(probe)]/overview_np[trace_len > 3000 & pch_method =='ifp_bck', length(probe)]

# * compare the RTT change CHARACTER discovered by the three method ----
rtt_view = data.table(read.table("cor_rtt_ch_v4_cpt_np.csv", sep=';', header=T, stringsAsFactors = F))
rtt_view = data.table(read.table("cor_rtt_ch_v4_cpt_poisson.csv", sep=';', header=T, stringsAsFactors = F))

write.table(rtt_view[,.(cpt_method='np', delta_median, delta_std)], file = 'cpt_chara_np.csv', sep = ';', row.names = F)
write.table(rtt_view[,.(cpt_method='poisson', delta_median, delta_std)], file = 'cpt_chara_poisson.csv', sep = ';', row.names = F)

rtt_np = read.table('cpt_chara_np.csv', sep = ';', header = T, stringsAsFactors = F)
rtt_poisson = read.table('cpt_chara_poisson.csv', sep = ';', header = T, stringsAsFactors = F)
rtt_bind = data.table(rbind(rtt_np, rtt_poisson))

lbs = c('np'='cpt_np', 'poisson'='cpt_poisson')
pdf('../data/graph/rtt_ch_chara_cmp.pdf', width = 8, height=4)
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(5, 10, 20, 50, 100, 200, 500)
#g <- ggplot(rtt_bind[, .SD[sample(.N, 500)], by=cpt_method],
g <- ggplot(rtt_bind[delta_median < 1000 & delta_std < 500], 
            aes(x=delta_median, y=delta_std)) +
  scale_x_continuous(trans = log2_trans(), breaks=xbk) +
  scale_y_continuous(trans = log2_trans(), breaks=ybk) +
  geom_density2d() +
  facet_wrap(~cpt_method, ncol = 2, labeller = as_labeller(lbs))+
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('RTT std difference (ms)') +
  theme_bw()+
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)
dev.off()


# * path change NUMBER distribution ----
bks = c(0, 2, 10, 20, 50, 100, 200, 500, 1000, 4000)
pdf('../data/graph/path_ch_count_cdf_cmp.pdf', width = 4, height=3)
g <- ggplot(overview_np[pch_method %in% c('as_path_change', 'as_path_change_ixp','ifp_bck') & probe %in% one_probe_as]) + 
  stat_ecdf(aes(log_mod(as.numeric(tp)+as.numeric(fp)), col=pch_method)) +
  #geom_density(aes(log_mod(as.numeric(tp)+as.numeric(fp)), col=pch_method)) +
  scale_x_continuous(breaks=log_mod(bks), labels = bks) +
  #coord_cartesian(xlim=c(0, 400)) +
  scale_color_discrete(name='', breaks=c('as_path_change', 'as_path_change_ixp','ifp_bck'), labels=c('AS path', 'IXP change','IFP')) +
  xlab('Number of path changes per probe') +
  #ylab('Density') +
  ylab('CDF') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 25, hjust=0.5, vjust=.5),
        legend.text=element_text(size=12), legend.key=element_blank())
print(g)
dev.off()

overview_np[pch_method=='as_path_change' & pch_count >100 & probe %in% one_probe_as, length(probe)]
topo_stat[probe %in% one_probe_as & ixp_count == 0, length(probe)]
overview_np[pch_method=='as_path_change' & pch_count == 0 & probe %in% one_probe_as, length(probe)]

# over all matching rate ----
overview_np[pch_method == 'as_path_change' & probe %in% one_probe_as, sum(as.numeric(tp))]
overview_poisson[pch_method == 'as_path_change' & probe %in% one_probe_as, sum(as.numeric(tp))]
overview_np[pch_method == 'as_path_change' & probe %in% one_probe_as, sum(pch_count)]

overview_np[pch_method == 'as_path_change_ixp' & probe %in% one_probe_as, sum(as.numeric(tp))]
overview_poisson[pch_method == 'as_path_change_ixp' & probe %in% one_probe_as, sum(as.numeric(tp))]
overview_np[pch_method == 'as_path_change_ixp' & probe %in% one_probe_as, sum(pch_count)]

overview_np[pch_method == 'ifp_bck' & probe %in% one_probe_as, sum(as.numeric(tp))]
overview_poisson[pch_method == 'ifp_bck' & probe %in% one_probe_as, sum(as.numeric(tp))]
overview_np[pch_method == 'ifp_bck' & probe %in% one_probe_as, sum(pch_count)]

overview_np[pch_method == 'ifp_bck' & probe %in% one_probe_as, sum(cpt_count)]
overview_poisson[pch_method == 'ifp_bck' & probe %in% one_probe_as, sum(cpt_count)]

# * path change NUMBER and PRECISION ----
bks = c(0, 2, 10, 20, 50, 100, 200, 500, 1000, 4000)
pdf('../data/graph/as_path_ch_precision_poisson.pdf', width = 4, height=4)
g <- ggplot(overview_poisson[pch_method == 'as_path_change_ixp' & probe %in% one_probe_as],
            aes(x=as.numeric(pch_count), y=as.numeric(precision))) + 
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


# * why poisson and np correlation with AS path change is very different ----
as_tp_cmp = merge(overview_np[pch_method=='as_path_change',.(probe, pch_count, cpt_count, tp, precision)],
                  overview_poisson[pch_method == 'as_path_change', .(probe, cpt_count, tp, precision)],
                  by='probe', suffixes = c('_np', '_poisson'))

as_tp_cmp[, ':='(diff_tp=as.numeric(tp_poisson)-as.numeric(tp_np), 
                 diff_precision = as.numeric(precision_poisson)-as.numeric(precision_np),
                 diff_cpt = as.numeric(cpt_count_poisson)-as.numeric(cpt_count_np))]
as_tp_cmp = merge(as_tp_cmp, rtt.pingv4[,.(probe_id, std)], by.x = 'probe', by.y = 'probe_id')
as_tp_cmp[, ':='(diff_tp_sign = sign(diff_tp), 
                 diff_tp_level = cut(abs(diff_tp), 
                                     breaks = c(0, 2, 50, 100, 500, 2000)))]

# * * How Poisson and NP differs in chang detectiom ----
as_tp_cmp[probe %in% one_probe_as & pch_count > 0, length(probe), by=diff_tp_sign]
as_tp_cmp[probe %in% one_probe_as & pch_count == 0, length(probe)]
as_tp_cmp[probe %in% one_probe_as & pch_count > 0 & abs(diff_tp) > 0 & abs(diff_tp) < 10, length(probe)]

g <- ggplot(as_tp_cmp[pch_count > 0 & probe %in%  one_probe_as], aes(log_mod(abs(diff_tp)))) + 
  stat_ecdf() +
  scale_x_continuous(breaks = log_mod(c(-50, -20, -10, 0, 10 ,50, 100, 200, 500, 100)), labels = c(-50, -20, -10, 0, 10 ,50, 100, 200, 500, 100))
g

pdf('../data/graph/as_match_diff.pdf', width = 8, height=4)
facet_label <- c('-1' = 'Matched change NP > Poisson', '0' = 'NP = Poisson', '1'='NP < Poisson')
bxs = c(-500, -100, -50, -10, 0, 10, 50, 100, 500, 1000)
bks = c(0, 2, 10, 20, 50, 100, 200, 500, 1000, 4000)
g <- ggplot(as_tp_cmp[probe %in% one_probe_as & diff_tp !=0 ], 
            aes(x=log_mod(diff_cpt), y=log_mod(pch_count))) + 
  geom_point(colour='grey50', size=2, alpha=.5) +
  geom_point(aes(text=paste("Probe:", probe), col=diff_tp_level), alpha=0.6) +
  scale_color_manual(name='Difference of mathced change', 
                     values = c('#c7e9b4','#7fcdbb','#feb24c','#fb6a4a','#bd0026')) +
  scale_x_continuous(breaks=log_mod(bxs), labels = bxs) +
  scale_y_continuous(breaks = log_mod(bks), labels = bks) +
  facet_wrap(~diff_tp_sign, labeller = as_labeller(facet_label)) +
  xlab('RTT change number difference (Poisson - NP)') +
  ylab('AS path change') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='top',
        axis.text.x=element_text(size=12, angle = 45, hjust=0.5, vjust=.5),
        legend.key = element_blank(),
        legend.text = element_text(size=10),
        legend.title = element_text(size=12))
print(g)
dev.off()

# * * How RTT detection sensitivity changes with different overall RTT std ----
pdf('../data/graph/cpt_diff_vs_std.pdf', width = 6.5, height=3.5)
bxs = c(-500, -100, -50, -10, 0, 10, 50, 100, 500, 2000, 4000)
g <- ggplot(as_tp_cmp[probe %in% one_probe_as], aes(y=log_mod(diff_cpt), x=as.numeric(std))) + 
  geom_point(aes(text=paste("Probe:", probe)), alpha =.4, col='#fb6a4a') + 
  geom_density2d() +
  scale_y_continuous(breaks = log_mod(bxs), labels=bxs)+
  scale_x_continuous(trans=log_trans(), breaks= c(1, 3, 5, 10, 20, 50, 100, 200))+
  ylab('RTT cpt number diff\n (Poisson - NP)') +
  xlab('RTT std') +
  theme_bw() +
  theme(text=element_text(size=16))
print(g)
dev.off()

bck = c(-50, -20, -10, -5, -2, -1 , 0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)
g <- ggplot(as_tp_cmp[pch_count>0], aes(x=log_mod(diff_cpt), y=diff_precision)) + 
  geom_point(aes(text=paste("Probe:", probe))) + 
  geom_density2d() +
  scale_x_continuous(breaks = log_mod(bck), labels=bck) 
#scale_y_continuous(breaks = log_mod(bck), labels=bck)
g


g <- ggplot(as_tp_cmp[pch_count>0], aes(y=log_mod(diff_tp), x=as.numeric(pch_count), col=as.numeric(precision_np))) + 
  geom_point(aes(text=paste("Probe:", probe))) + geom_density2d() +
  scale_y_continuous(breaks = log_mod(bck), labels=bck)+
  scale_x_continuous(trans=log_trans())
g
ggplotly(g)

# * compare RTT change characters across different category----
# path_ch whether matched with any path change
# as_ch whether matched with AS path change
rtt_view[,':='(path_ch = (as.logical(as_path_change_match) | as.logical(as_path_change_ixp_match) | as.logical(ifp_bck_match)),
               as_ch = (as.logical(as_path_change_match) | as.logical(as_path_change_ixp_match)))]

# * * whether is a path change -----
# delta_median ~ delta_std
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_view[delta_median < 1000 & delta_std < 500 & probe %in% one_probe_as & seg_len > 10], 
            aes(x=delta_median, y=delta_std)) +
  scale_x_continuous(trans = log2_trans(), breaks=xbk) +
  scale_y_continuous(trans = log2_trans(), breaks=ybk) +
  geom_density2d() +
  facet_wrap(~path_ch, ncol = 2)+
  scale_color_discrete(name='Matched to path change') +
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)

# seg_std
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(0, 1, 2,5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_view[delta_median < 1000 & delta_std < 500 & probe %in% one_probe_as & seg_len > 10], 
            aes(log_mod(seg_std), col=path_ch)) +
  geom_density() +
  scale_x_continuous(breaks = log_mod(ybk), labels=ybk) +
  scale_color_discrete(name='Matched to path change') +
  #xlab('Median RTT difference across changepoints (ms)') +
  #ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)

# * * whether is an AS path change ----
# delta_median ~ delta_std
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_view[delta_median < 1000 & delta_std < 500 & probe %in% one_probe_as & path_ch == TRUE & seg_len > 10], 
            aes(x=delta_median, y=delta_std)) +
  scale_x_continuous(trans = log2_trans(), breaks=xbk) +
  scale_y_continuous(trans = log2_trans(), breaks=ybk) +
  geom_density2d() +
  facet_wrap(~as_ch, ncol = 2)+
  scale_color_discrete(name='Matched to path change') +
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)

# seg_std
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(0, 1, 2,5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_view[delta_median < 1000 & delta_std < 500 & probe %in% one_probe_as & seg_len > 10 & path_ch == TRUE], 
            aes(log_mod(seg_std), col=as_ch)) +
  geom_density() +
  scale_x_continuous(breaks = log_mod(ybk), labels=ybk) +
  scale_color_discrete(name='Matched to path change') +
  #xlab('Median RTT difference across changepoints (ms)') +
  #ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)

# * *  whether is AS change or IXP change ----
# delta_median ~ delta_std
xbk = c(5, 10, 20, 50, 100, 200, 500, 1000)
ybk = c(5, 10, 20, 50, 100, 200, 500)
g <- ggplot(rtt_view[delta_median < 1000 & delta_std < 500 & probe %in% one_probe_as & as_ch == TRUE & seg_len > 10], 
            aes(x=delta_median, y=delta_std)) +
  scale_x_continuous(trans = log2_trans(), breaks=xbk) +
  scale_y_continuous(trans = log2_trans(), breaks=ybk) +
  geom_density2d() +
  facet_wrap(~as_path_change_match, ncol = 2)+
  scale_color_discrete(name='Matched to path change') +
  xlab('Median RTT difference across changepoints (ms)') +
  ylab('RTT std difference (ms)') +
  theme(text=element_text(size=16), legend.position="top",
        axis.text.x=element_text(angle = 90, hjust=0))
print(g)


rtt_view[delta_median> 80 & delta_std > 40 & as_path_change_match == 'True', .(count=sum(i)), by=probe][order(count, decreasing = T)][1:10]
rtt_view[seg_len > 5 & as_path_change_ixp_match == 'True' & delta_median < 100][order(delta_median, decreasing = T)][1:10]


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

# * IP path number ~ IFP change number ----
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

g <- ggplot(merge(overview_np[pch_method == 'ifp_bck' & probe %in% one_probe_as & trace_len > 30000],
                  topo_stat, by='probe')) +
  geom_point(aes(y=(as.numeric(tp)+as.numeric(fp)), x=ip_path_count, col=as.numeric(precision), text=paste("Probe:", probe)), alpha=.3) +
  scale_x_continuous(trans = log10_trans(), breaks = c(16, 50, 100, 200, 500, 1000))
g
ggplotly(g)


# * IP path number ~ IFP change precision ----
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

# fraction of probes with more than 16 IP paths
topo_stat[probe %in% one_probe_as & ip_path_count > 16, length(probe)] /topo_stat[probe %in% one_probe_as, length(probe)]

quantile(topo_stat[probe %in% one_probe_as, ip_path_count], prob = c(.05, .1, .25, .5, .75, .95, 1), type=8)

# * IFP change precision gain with BCK and SPLIT ----
# the precision gain of split is very marginal. should skip it in paper
bck_gain_poisson <- overview_poisson[pch_method=='ifp_bck', as.numeric(precision)]/overview_poisson[pch_method=='ifp_simple', as.numeric(precision)]
bck_gain_np <- overview_np[pch_method=='ifp_bck', as.numeric(precision)]/overview_np[pch_method=='ifp_simple', as.numeric(precision)]
ifp_gain <- data.table(probe = overview_poisson[pch_method=='ifp_bck',probe], 
                       trace_len = overview_np[pch_method=='ifp_bck',trace_len],
                       Poisson=bck_gain_poisson, NP=bck_gain_np)
ifp_gain <- melt(ifp_gain, measure.vars = c('Poisson', 'NP'), variable.name = 'method', value.name = "precision_gain")

pdf('../data/graph/ifp_bck_ch_precision_gain_cdf.pdf', width = 6, height=2.5)
g <- ggplot(ifp_gain[trace_len > 30000 & probe %in% one_probe_as]) + 
  stat_ecdf(aes(precision_gain, col=method)) +
  scale_color_discrete(name='') +
  xlab('Precision ratio: IFP bck/IFP fwd') +
  ylab('CDF') +
  theme_bw() +
  theme(text=element_text(size=16), legend.position='right', legend.key=element_blank())
print(g)
dev.off()



# * lAlV, lAhV, hAlV, hAhV ----
cpt_m = 'poisson'
cpt_m = 'np'
rtt_bind[cpt_method==cpt_m & delta_median < 5 & delta_std < 5, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]
rtt_bind[cpt_method==cpt_m & delta_median < 5 & delta_std > 50, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]
rtt_bind[cpt_method==cpt_m & delta_median > 100 & delta_std < 5, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]
rtt_bind[cpt_method==cpt_m & delta_median > 100 & delta_std > 50, length(delta_std)]/rtt_bind[cpt_method==cpt_m, length(delta_std)]


# Obsolete code from here on ----
# how to find RTT changepoint not matched to ifp nor to AS path changes
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

quantile(rtt_m[path_ch_m == F & delta_median < 1000 & delta_std < 500, delta_median])
quantile(rtt_m[path_ch_m == T & delta_median < 1000 & delta_std < 500, delta_median])

# the proportion of RTT changes matched to AS path change is kind of high, find out why

# * where does cpt low level high variance change come from
rtt_m[delta_median < 5 & delta_std > 50, length(ch_id)]/nrow(rtt_m)
# how many such changes each probe trace have, the distribution is highly skewed
# only few probes have many of them, find what are they
g <- ggplot(rtt_m[delta_median < 5 & delta_std > 50, .(count=length(ch_id)), by=probe]) + stat_ecdf(aes(count))
g
high.var <- rtt_m[delta_median < 5 & delta_std > 50, .(count=length(ch_id)), by=probe][order(count, decreasing = T)]
quantile(high.var$count, probs = c(.10,.25,.5,.75,.9,.95, .99), type = 8)
# plot the rtt trace of these probes
# investigated 12937 the measurment is frequent dotted as timeout
# find ones with many path changes
temp <- merge(high.var, overview_np[pch_method=='as_path_change', .(probe, pch_count = as.numeric(tp) + as.numeric(fp))], by='probe')[order(count, pch_count, decreasing = T)]

# * where does cpt median [100, 200], std [50, 100] come from
rtt_m[delta_median > 100 & delta_std >50 , length(ch_id)]/nrow(rtt_m)
g <- ggplot(rtt_m[delta_median > 100 & delta_std >50, .(count=length(ch_id)), by=probe]) + stat_ecdf(aes(count))
g
both.high <- rtt_m[delta_median > 100 & delta_std >50, .(count=length(ch_id)), by=probe][order(count, decreasing = T)]
quantile(both.high$count, probs = .95)
# investigated 10342, 17272, periodic long lasting congestion, cpt_poisson over sensitive, cpt_np is great
# investigated 12385, many timeout measurements
# investigated 26326 with np, many timeout segment, when with valid value, the variance is big


# * find probes potentially with large amplitude congestions
rtt_m[delta_median > 30 & delta_median < 150 & delta_std > 5 & delta_std < 50 & path_ch_m == FALSE, .(count=length(ch_id)), by=probe][order(count, decreasing = T)][20:30]

# * cleaning criteria
# valide data length > 30000
# top 5% probe with most high variance change
# top 5% probe with most high level and high variance change
a <- as.numeric(rtt.pingv4[valid_length> 30000, probe_id]) 
b <- as.numeric(high.var[count < 100, probe]) 
c <- as.numeric(both.high[count < 100, probe]) 

scope <- intersect(a, intersect(b, c))