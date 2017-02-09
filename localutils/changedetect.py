"""
changedetect.py provides tools for detecting changes in RTT time series
"""
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import IntVector, FloatVector
changepoint = importr('changepoint')
changepoint_np = importr('changepoint.np')


def cpt_normal(x, penalty='MBIC'):
    """changepoint detection with Normal distribution as test statistic

    Args:
        x (list of numeric type): timeseries to be handled
        penalty (string): possible choices "None", "SIC", "BIC", "MBIC", AIC", "Hannan-Quinn"

    Returns:
        list of int: beginning of new segment in python index, that is starting from 0;
        the actually return from R changepoint detection is the last index of a segment.
        since the R indexing starts from 1, the return naturally become the beginning of segment.
    """
    return [int(i) for i in changepoint.cpts(changepoint.cpt_meanvar(FloatVector(x),
                                                                     test_stat='Normal', method='PELT',
                                                                     penalty=penalty))]


def cpt_np(x, penalty='MBIC'):
    """changepoint detection with non-parametric method, empirical distribution is the only choice now

        Args:
            x (list of numeric type): timeseries to be handled
            penalty (string): possible choices "None", "SIC", "BIC", "MBIC", AIC", "Hannan-Quinn"

        Returns:
            list of int: beginning of new segment in python index, that is starting from 0;
            the actually return from R changepoint detection is the last index of a segment.
            since the R indexing starts from 1, the return naturally become the beginning of segment.
    """
    return [int(i) for i in changepoint.cpts(changepoint_np.cpt_np(FloatVector(x), penalty=penalty))]
