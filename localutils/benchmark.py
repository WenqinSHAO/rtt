"""
benchmark.py provides functions for various evaluation tasks in this work
"""
import collections
import sys
import munkres
import numpy as np
import logging


def evaluation(fact, detection):
    """classify the detections into true positive, true negative, false positive and false negative

    Args:
        fact (list of int): ground fact, should only contain only 0, 1; 1 for events meant to be detected;
        detection (list of int): results to be tested against ground fact; 1 for detected events;

    Returns:
        dict: {'tp':int, 'fp':int, 'fn':int, 'tn':int, 'precision':float, 'recall':float}
    """
    if len(fact) != len(detection):
        raise ValueError('fact and prediction are not of same length.')
    if not (set(fact) == set(detection) == set([0, 1])):
        raise ValueError('fact or/and prediction contain other value than 0/1.')
    tp, fp, fn, tn = [0] * 4
    for f, p in zip(fact, detection):
        if f == p:
            if f == 1:
                tp += 1
            else:
                tn += 1
        else:
            if f == 1:
                fn += 1
            else:
                fp += 1
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=float(tp)/(tp+fp), recall=float(tp)/(tp+fn))


def evaluation_window(fact, detection, window=0, return_match=False):
    """classify the detections with window option

    We construct a bipartite graph G = (V + W, E), where V is fact and W is detection.
    e = (v, w), e in G, if distance(v, w) <= window.
    cost(e) = distance(v, w)
    We find the minimum-cost maximum matching M of G.

    tp = |M|
    fp = |W| - |M|
    fn = |V| - |M|
    dis = C(M)/|M| average distance between fact and detection in mapping

    Args:
        fact (list of int): the index or timestamp of facts/events to be detected
        detection (list of int): index or timestamp of detected events
        window (int): maximum distance for the correlation between fact and detection
        return_match (bool): returns the matching tuple idx [(fact_idx, detection_idx),...] if set true

    Returns:
        dict: {'tp':int, 'fp':int, 'fn':int, 'precision':float, 'recall':float, 'dis':float, 'match': list of tuple}

    """
    if len(fact) == 0:
        summary = dict(tp=None, fp=len(detection), fn=None,
                       precision=None, recall=None,
                       dis=None, match=[])
        return summary
    elif len(detection) == 0:
        summary = dict(tp=0, fp=0, fn=len(fact),
                       precision=None, recall=0,
                       dis=None, match=[])
        return summary

    cost_matrix = make_cost_matrix(fact, detection, window)  # construct the cost matrix of bipartite graph

    # handle the case there is actually no edges between fact and detection
    if all([cost_matrix[i][j] == sys.maxint for i in range(len(fact)) for j in range(len(detection))]):
        summary = dict(tp=0, fp=len(detection), fn=len(fact),
                       precision=0, recall=0,
                       dis=None, match=[])
        return summary

    match = munkres.Munkres().compute(cost_matrix)  # calculate the matching
    match = [(i, j) for i, j in match if cost_matrix[i][j] <= window]  # remove dummy edges
    # i and j here are the indices of fact and detection, i.e. ist value in fact and jst value in detection matches

    tp = len(match)
    fp = len(detection) - tp
    fn = len(fact) - tp

    summary = dict(tp=tp, fp=fp, fn=fn,
                   precision=float(tp) / (tp + fp) if len(detection) > 0 else None,
                   recall=float(tp) / (tp + fn) if len(fact) > 0 else None,
                   dis=sum([cost_matrix[i][j] for i, j in match]) / float(tp) if tp > 0 else None)

    if return_match:
        summary['match'] = match

    return summary


def evaluation_window_adp(fact, detection, window=0, return_match=False):
    # if the input fact is very long, segment it to accelerate the calculation
    if len(fact) == 0 or len(detection) == 0:
        return evaluation_window(fact, detection, window, return_match)

    cost_matrix = make_cost_matrix(fact, detection, window)
    # handle the case there is actually no edges between fact and detection
    if all([cost_matrix[i][j] == sys.maxint for i in range(len(fact)) for j in range(len(detection))]):
        summary = dict(tp=0, fp=len(detection), fn=len(fact),
                       precision=0, recall=0,
                       dis=None, match=[])
        return summary

    cut = cut_matrix(cost_matrix, sys.maxint)
    match_cut = [evaluation_window(fact[i[0][0]:i[0][1]], detection[i[1][0]:i[1][1]], window, True) for i in cut]

    tp = sum([i['tp'] for i in match_cut])
    fp = len(detection) - tp
    fn = len(fact) - tp

    match = []
    for i, res in enumerate(match_cut):
        match.extend([(f+cut[i][0][0], d+cut[i][1][0]) for f, d in res['match']])

    summary = dict(tp=tp, fp=fp, fn=fn,
                   precision=float(tp) / (tp + fp) if len(detection) > 0 else None,
                   recall=float(tp) / (tp + fn) if len(fact) > 0 else None,
                   dis=sum([abs(fact[i]-detection[j]) for i, j in match]) / float(tp) if tp > 0 else None)

    if return_match:
        summary['match'] = match

    return summary


def cut_matrix(mat, no_edge=0):

    def cutter(mat, righter, downer):
        righter_set = set()
        res = []
        while righter[1] <= len(mat[0]):
            righter_set.add(righter)
            if righter[0] == len(mat) or (righter[1]+1 < len(mat[0]) and mat[righter[0]][righter[1]+1] == no_edge):
                righter = (righter[0], righter[1]+1)
            else:
                righter = (righter[0]+1, righter[1])

        while downer[0] <= len(mat):
            if (downer[0]+1, downer[1]-1) in righter_set:
                res.append(downer)
                if len(res) == 2:
                    break

            if downer[1] == len(mat[0]) or (downer[0] + 1 < len(mat) and mat[downer[0]+1][downer[1]] == no_edge):
                downer = (downer[0]+1, downer[1])
            else:
                downer = (downer[0], downer[1]+1)
        return res[-1][0]+1, res[-1][1]

    line_start = 0
    column_start = 0
    res = []
    while line_start < len(mat) and column_start < len(mat[0]):
        righter = None
        downer = None
        for i in range(line_start, len(mat)):
            row = mat[i]
            if any([v != no_edge for v in row]):
                # upper of the most left edge in first non-empty line
                downer = (i-1, [j for j, v in enumerate(row) if v != no_edge][0])
                break

        for i in range(column_start, len(mat[0])):
            column = [row[i] for row in mat]
            if any([v != no_edge for v in column]):
                # the upper tp the first edge in the first non-empty column
                righter = ([j for j, v in enumerate(column) if v != no_edge][0], i-1)
                break

        if righter is None or downer is None:
            break
        line_start, column_start = cutter(mat, righter, downer)
        # ((row index range), (column index range))
        res.append(((min(righter[0], downer[0]+1), line_start), (min(righter[1]+1, downer[1]), column_start)))

    return res


def evaluation_window_weighted(trace, fact, detection, window=0, return_match=False):
    """ score the event according to its importance

    Each event to detect in fact is associated with a weight/score.
    the score characterise the importance of each event.

    score = score sum of detected events/total sum; a more nuanced version of recall

    Args:
        trace (list of numeric): the initial time series to be detected
        fact (list of int): the index or timestamp of facts/events to be detected
        detection (list of int): index or timestamp of detected events
        window (int): maximum distance for the correlation between fact and detection
        return_match (bool): returns the matching tuple idx [(fact_idx, detection_idx),...] if set true

    Returns:
        dict: {'tp':int, 'fp':int, 'fn':int, 'precision':float, 'recall':float, 'dis':float, 'score':float, 'match':list of tuple}

    """
    if len(fact) == 0:
        summary = dict(tp=None, fp=len(detection), fn=None,
                       precision=None, recall=None,
                       dis=None, score=None, match=[])
        return summary
    elif len(detection) == 0:
        summary = dict(tp=0, fp=0, fn=len(fact),
                       precision=None, recall=0,
                       dis=None, score=None, match=[])
        return summary

    cost_matrix = make_cost_matrix(fact, detection, window)  # construct the cost matrix of bipartite graph
    match = munkres.Munkres().compute(cost_matrix)  # calculate the matching
    match = [(i, j) for i, j in match if cost_matrix[i][j] <= window]  # remove dummy edges

    weight = weighting(trace, fact)

    tp = len(match)
    fp = len(detection) - tp
    fn = len(fact) - tp

    summary = dict(tp=tp, fp=fp, fn=fn,
                   precision=float(tp) / (tp + fp) if len(detection) > 0 else None,
                   recall=float(tp) / (tp + fn) if len(fact) > 0 else None,
                   dis=sum([cost_matrix[i][j] for i, j in match]) / float(tp) if tp > 0 else None,
                   score=sum([weight[i] for i, _ in match]) / float(sum(weight)) if sum(weight) > 0 else None)

    if return_match:
        summary['match'] = match

    return summary


def character(trace, fact):
    """ calculate the character of changepoints

    for each index in fact as a changepoint, calculate the median difference and std difference

    Args:
        trace (list of numeric): the initial time series
        fact (list of int): index of trace for events to be detected

    Return:
        list of tuple [(delta median, delta std ),...]
    """
    fact = [0] + fact + [len(trace)]
    seg = [(fact[i], fact[i + 1]) for i in range(len(fact) - 1)]
    seg_median = [np.median(trace[i[0]:i[1]]) for i in seg]
    seg_median_diff = np.abs(np.array(seg_median[1:]) - np.array(seg_median[:-1]))
    seg_std = [np.std(trace[i[0]:i[1]]) for i in seg]
    seg_std_diff = np.abs(np.array(seg_std[1:]) - np.array(seg_std[:-1]))
    return zip(seg_median_diff, seg_std_diff)


def weighting(trace, fact):
    """ weight fact/events

    weight for each fact w = MAX(log10(seg_len/3), 0) * (median_diff + sqrt(std_diff))

    Args:
        trace (list of numeric): the initial time series
        fact (list of int): index of trace for events to be detected

    Returns:
        numpy.array
    """
    fact = [0] + fact + [len(trace)]
    seg = [(fact[i], fact[i+1]) for i in range(len(fact)-1)]
    seg_len = np.array([i[1]-i[0] for i in seg])
    seg_median = [np.median(trace[i[0]:i[1]]) for i in seg]
    seg_median_diff = np.abs(np.array(seg_median[1:])-np.array(seg_median[:-1]))
    seg_std = [np.std(trace[i[0]:i[1]]) for i in seg]
    seg_std_diff = np.abs(np.array(seg_std[1:])-np.array(seg_std[:-1]))
    return np.maximum(np.log2(np.array(seg_len[1:])/3.0), 0) * (seg_median_diff + seg_std_diff)


def min_cost_maximum_match(g):
    """ find the minimum cost maximum matching for bipartite graph g

    Args:
        g (list of list): [[v, w, cost],....]

    Returns:
        list of int; index of edge in g that belong the the matching
    """
    res = collections.defaultdict(list)  # where matching is store when get to the end of one branch

    def dfs(edges, v_nodes, w_nodes):
        """ the dfs recursive search

        Args:
            edges (list of int): the indexes of already visited/included edges
            v_nodes (set of int): the v nodes involved by visited/included edges
            w_nodes (set of int): the w nodes involved by visited/included edges
        nodes is a set of vertices in added edges
        """
        idx = edges[-1]+1 if edges else 0  # starting from the next edge of last visited/included one
        complete = True  # complete condition is no edge can be further added
        for i, e in enumerate(g[idx:]):
            if e[0] not in v_nodes and e[1] not in w_nodes:
                # if the edge can be added, add it and start search from the next one by calling gfs
                edges.append(i+idx)
                v_nodes.add(e[0])
                w_nodes.add(e[1])
                dfs(edges, v_nodes, w_nodes)
                # continue with the branch that the edge e is not added
                edges.pop()
                v_nodes.remove(e[0])
                w_nodes.remove(e[1])
                complete = False
        if complete:
            res[len(edges)].append(list(edges))  # need to make of copy of edges

    dfs([], set(), set())

    # return the maximum matching with smallest total cost
    return sorted(res[max(res.keys())], key=lambda s: sum([g[i][2] for i in s]))[0] if res else []


def make_cost_matrix(x, y, window):
    """ make cost matrix for bipartite graph x, y"""
    return [[abs(x[i] - y[j]) if abs(x[i]-y[j]) <= window else sys.maxint for j in range(len(y))] for i in range(len(x))]




