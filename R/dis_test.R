## code for distribution test
library(vcd)
library(ggplot2)
library(anytime)
library(changepoint.np)
library(reshape2)
library(plotly)
library(scales)
library(nortest)
library(MASS)

# data representation formatter
subMin <- function(x) {
  x <-round(x)
  bsl <- min(x[x>0])
  return(ifelse(x>0, x-bsl, 1000))
}

subMinFloat <- function(x){
  bsl <- min(x[x>0])
  return(ifelse(x>0, x-bsl, 1000))
}

subMinFloat01 <- function(x){
  bsl <- min(x[x>0])
  return(ifelse(x>0, x-bsl+0.1, 1000))
}

# function for testing distribution type for each change segement in input trace
# input trace is a data.frame with rtt and cp columns
# rtt contains the value of timesereis
# cp set to 1 is then a changepoint
dis.test <- function(trace) {
  tau <- c(1, which(trace$cp==1), nrow(trace)+1)
  idx <- c()
  len <- c()
  poisson.p <- c()
  normal.p <- c()
  #normal.pearson.p <- c()
  exp.p <- c()
  gamma.p <- c()
  for (i in seq_len(length(tau)-1)){
    seg <- c(tau[i], (tau[i+1]-1))
    seglen <- seg[2]-seg[1]+1
    if (seglen > 20){ # do distribution test only for those segments with > 20 datapoints
      len <- append(len, seglen)
      idx <- append(idx, i)
      rtt <- trace[seg[1]:seg[2], submin]
      if (all(rtt==rtt[1])) {
        poisson.p <- append(poisson.p, 0)
      } else{
        test.res <- goodfit(rtt, type = 'poisson', method = 'MinChisq')
        test.res <- invisible(summary(test.res))
        poisson.p <- append(poisson.p, ifelse(is.na(test.res[3]), 0, test.res[3]))
      }
      rtt <- trace[seg[1]:seg[2], rtt]
      if (all(rtt==rtt[1])) {
        normal.p <- append(normal.p, 0)
      } else{
        if (seglen > 5000) {rtt <- sample(rtt, 5000)}
        test.res <- shapiro.test(rtt)
        normal.p <- append(normal.p, test.res$p.value)
      }
      rtt <-  trace[seg[1]:seg[2], submin.float]
      if (all(rtt==rtt[1])) {
        exp.p <- append(exp.p, 0)
      } else{
        parmfit <- fitdistr(rtt, 'exponential')
        test.res <- ks.test(rtt, 'pexp', parmfit$estimate)
        exp.p <- append(exp.p, test.res$p.value)
      }
      rtt <-  trace[seg[1]:seg[2], submin.float01]
      if (all(rtt==rtt[1])) {
        gamma.p <- append(gamma.p, 0)
      } else{
        parmfit <- fitdistr(rtt, 'gamma')
        test.res <- ks.test(rtt, 'pgamma', parmfit$estimate[1], parmfit$estimate[2])
        gamma.p <- append(gamma.p, test.res$p.value)
      }
    }
  }
  return(data.table(segidx = idx, seglen = len, poisson.p = poisson.p, normal.p = normal.p, exp.p = exp.p, gamma.p = gamma.p))
}

# understand parameters of gamma fitting
param.gamma <- function(trace){
  tau <- c(1, which(trace$cp==1), nrow(trace)+1)
  idx <- c()
  len <- c()
  shape.ini <- c()
  rate.ini <- c()
  shape.bl <- c()
  rate.bl <- c()
  for (i in seq_len(length(tau)-1)){
    seg <- c(tau[i], (tau[i+1]-1))
    seglen <- seg[2]-seg[1]+1
    if (seglen > 20){ # do distribution test only for those segments with > 20 datapoints
      len <- append(len, seglen)
      idx <- append(idx, i)
      rtt <-  trace[seg[1]:seg[2], submin.float01]
      if (all(rtt==rtt[1])) {
        shape.bl <- append(shape.bl, NA)
        rate.bl <- append(rate.bl, NA)
      } else{
        parmfit <- fitdistr(rtt, 'gamma')
        shape.bl <- append(shape.bl, parmfit$estimate[1])
        rate.bl <- append(rate.bl, parmfit$estimate[2])
      }
      rtt <-  trace[seg[1]:seg[2], rtt]
      if (all(rtt==rtt[1])) {
        shape.ini <- append(shape.ini, NA)
        rate.ini <- append(rate.ini, NA)
      } else{
        parmfit <- fitdistr(rtt, 'gamma')
        shape.ini <- append(shape.ini, parmfit$estimate[1])
        rate.ini <- append(rate.ini, parmfit$estimate[2])
      }
    }
  }
  return(data.table(segidx = idx, seglen = len, shape.ini = shape.ini, rate.ini = rate.ini, shape.bl = shape.bl, rate.bl = rate.bl))
}


trace.dir = '../dataset/real_trace_labelled'
files = file.path(trace.dir, list.files(trace.dir))

# distributiob test for normal, poisson, exponential, gamma
distest.res <- data.table()
for (f in files) {
  #trace <- data.table(read.table(f, sep=';', header = T, stringsAsFactors = F, na.strings = 'None', dec = ','))
  trace <- data.table(read.table(f, sep=';', header = T, stringsAsFactors = F, na.strings = 'None'))
  trace[, ':='(submin = subMin(rtt))]
  trace[, ':='(submin.float = subMinFloat(rtt))]
  trace[, ':='(submin.float01 = subMinFloat01(rtt))]
  res <- dis.test(trace)
  res[, ':='(file=basename(f))]
  distest.res <- rbind(distest.res, res)
}

distest.res[normal.p > 0.05, length(segidx)]
distest.res[poisson.p > 0.05, length(segidx)]
distest.res[exp.p > 0.05, length(segidx)]
distest.res[gamma.p > 0.05, length(segidx)]
distest.res[normal.p > 0.05 & gamma.p > 0.05, length(segidx)]

# parameters of gamma fitting
gamma.fit <- data.table()
for (f in files) {
  #trace <- data.table(read.table(f, sep=';', header = T, stringsAsFactors = F, na.strings = 'None', dec = ','))
  trace <- data.table(read.table(f, sep=';', header = T, stringsAsFactors = F, na.strings = 'None'))
  trace[, ':='(submin.float01 = subMinFloat01(rtt))]
  trace[, ':='(rtt = ifelse(rtt<0, 1000, rtt))]
  res <- param.gamma(trace)
  res[, ':='(file=basename(f))]
  gamma.fit <- rbind(gamma.fit, res)
}

plot(gamma.fit$shape.ini, gamma.fit$rate.ini, log='xy')
plot(gamma.fit[, shape.ini/rate.ini], gamma.fit[, shape.ini/(rate.ini^2)], log='xy')

plot(gamma.fit$shape.bl, gamma.fit$rate.bl, log='xy')
plot(gamma.fit[, shape.bl/rate.bl], gamma.fit[, shape.bl/(rate.bl^2)], log='xy')

plot(gamma.fit[, shape.ini/(rate.ini^2)], gamma.fit[, shape.bl/(rate.bl^2)], log='xy')

plot(gamma.fit[, shape.ini-shape.bl], gamma.fit[, rate.ini-rate.bl], log='xy')

# gamma distribution with varying rate
gamma.gen <- data.table()
for(i in c(1, 20, 50, 100, 200, 500, 1000)) {
  gamma.gen <- rbind(gamma.gen, data.table(rate=as.character(eval(i)), value=rgamma(500, i*20, i)))
}
g <- ggplot(gamma.gen, aes(value, col=rate)) + geom_density() +
  scale_x_continuous(trans = log_trans())
g
