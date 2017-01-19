lm_eqn <- function(df){
  # genenrate linear regress expression
  #
  # Args:
  #  df (data.frame): contains two columns x and y that are to be linearlly fitted
  #
  # Returns:
  #  a string representing the fitting function
  m <- lm(y ~ x, df);
  eq <- substitute(italic(y) == a + b %.% italic(x)*","~~italic(r)^2~"="~r2, 
                   list(a = format(coef(m)[1], digits = 2), 
                        b = format(coef(m)[2], digits = 2), 
                        r2 = format(summary(m)$r.squared, digits = 3)))
  as.character(as.expression(eq));                 
}

log_mod <- function(x, center=0){
  # log mod transformation
  return(sign(x-center) * log10((abs(x-center)+1)))
}

