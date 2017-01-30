"""
misc.py provides unclassified functions used in the project
"""
from ast import literal_eval


def read_probe(f):
    """ read data/pb.csv file

    Args:
        f (string): path to file, normally should be data/pb.csv

    Returns:
        probes (list of tuple): compatible format as the return of get_probe in localutils.atlas
    """
    probes = []
    with open(f, 'r') as fp:
        for i, line in enumerate(fp):
            if i > 0:
                probes.append(tuple([type_convert(i) for i in line.split(";")]))
    return probes


def type_convert(s):
    """ convert string in data/pb.csv to corresponding types

    Args:
        s (string): could be "1124", "US", "None", "True", "12.12.34.56/24", "('da', 'cd', 'ef')"

    Returns:
        "1124" -> 1124; "None" -> None; "US" -> US; "('da', 'cd', 'ef')" -> ('da', 'cd', 'ef')
    """
    try:
        return literal_eval(s)
    except (SyntaxError, ValueError):
        return s


def get_chunk_count(f):
    """" return the chunk number given a probe to chunk id indexing file

    Args:
        f(string): path to probe to chunk id indexing file

    Returns:
        chunk_count (int)
    """
    chunk_count = 0
    with open(f, 'r') as fp:
        for idx, line in enumerate(fp):
            if idx > 0:
                chunk_count = max(chunk_count, type_convert(line.split(";")[1].strip()))
    return chunk_count
