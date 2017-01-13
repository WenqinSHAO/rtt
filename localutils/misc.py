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
