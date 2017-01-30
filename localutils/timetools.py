"""
timetools.py provides functions that perform conversion among these types: second since epoch, string, datetime
"""
import datetime
import pytz
from dateutil.parser import parse

epoch = datetime.datetime.utcfromtimestamp(0)
epoch = epoch.replace(tzinfo=pytz.UTC)

TIME_FORMAT = '%Y-%m-%d %H:%M:%S %z'

# TODO: take mplotlib madates conversion take into consideraiton


def string_to_datetime(str_):
    """ translate a formatted string to a datetime object

    Args:
        str_ (string): a formatted sgtring for date, time

    Return:
        datetime, a datetime object with UTC as timezone
    """
    dt = parse(str_)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt


def datetime_to_epoch(dt):
    """ translate a python datetime object to seconds since epoch

    Args:
        dt (datetime): a datetime object

    Returns:
        int, seconds since epoch
    """
    return int((dt-epoch).total_seconds())


def string_to_epoch(str_):
    """ translate an UTC time string to epoch time

    Args:
        str_ (string): a string describing a UTC time in certain format

    Returns:
        int, seconds since the epoch
    """
    return datetime_to_epoch(string_to_datetime(str_))


def datetime_to_string(dt):
    """ translate a python datetime object into a readable string
    Args:
        dt (datetime): a datetime object

    Returns:
        string, a formatted string for date, time, and time zone
    """
    return datetime.datetime.strftime(dt, TIME_FORMAT)


def epoch_to_datetime(epc):
    """ translate seconds since epoch to a datetime object, UTC as timezone

    Args:
        epc (int) : seconds since epoch

    Returns:
        datetime, a datetime object with UTC as timezone

    """
    return datetime.datetime.fromtimestamp(epc, pytz.utc)


def epoch_to_string(epc):
    """ translate seconds since epoch to a formatted string

    Args:
        epc (int) : seconds since epoch

    Returns:
        string, a formatted string for date, time
    """
    return datetime_to_string(epoch_to_datetime(epc))