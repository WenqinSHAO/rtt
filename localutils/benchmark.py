"""
benchmark.py provides functions for various evaluation tasks in this work
"""
import collections
import sys
import munkres
import numpy as np


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
    """ a variation of evaluation_window() which is adapted to sparse cost matrix generated from fact and detection.

    If fact or detection contain many elements, say more than one hundred. It will take a significant amount of time,
    even with hungarian algo, to compute the min cost maximum matching.
    In our specific case, since the cost matrix is very specific, and can only have values at limited places.
    It is thus possible to cut the initial cost matrix into several non-connecting ones. For example:
    cost_matrix = [[62, 0,  0,  0, 0,  0, 0],
                   [11, 11, 82, 0, 0,  0, 0],
                   [0,  0, 81, 12, 0,  0, 0],
                   [0,  0,  0,  0, 12, 0, 0],
                   [0,  0,  0,  0, 0,  0, 0],
                   [0,  0,  0,  0, 0,  0, 12],
                   [0,  0,  0,  0, 0,  0, 12]]
    The given cost matrix is composed of three separate parts:
    cost_matrix[0:4][0:5], cost_matrix[3:4][4:5] and cost_matrix[5:end][6:end].
    Calculating the matching separately for the two sub-matrices will be faster.

    Args:
        fact (list of int): the index or timestamp of facts/events to be detected
        detection (list of int): index or timestamp of detected events
        window (int): maximum distance for the correlation between fact and detection
        return_match (bool): returns the matching tuple idx [(fact_idx, detection_idx),...] if set true

    Returns:
        dict: {'tp':int, 'fp':int, 'fn':int, 'precision':float, 'recall':float, 'dis':float, 'match': list of tuple}
    """
    if len(fact) == 0 or len(detection) == 0:
        return evaluation_window(fact, detection, window, return_match)

    cost_matrix = make_cost_matrix(fact, detection, window)
    # handle the case there is actually no edges between fact and detection
    if all([cost_matrix[i][j] == sys.maxint for i in range(len(fact)) for j in range(len(detection))]):
        summary = dict(tp=0, fp=len(detection), fn=len(fact),
                       precision=0, recall=0,
                       dis=None, match=[])
        return summary

    cut = cut_matrix(cost_matrix, sys.maxint)  # [((fact/line range), (detect/column range)),...]
    match_cut = [evaluation_window(fact[i[0][0]:i[0][1]], detection[i[1][0]:i[1][1]], window, True) for i in cut]

    tp = sum([i['tp'] for i in match_cut if i['tp']])  # in general is not possible to have i['tp'] is None
    fp = len(detection) - tp
    fn = len(fact) - tp

    match = []
    for i, res in enumerate(match_cut):
        match.extend([(f+cut[i][0][0], d+cut[i][1][0]) for f, d in res['match']])  # adjust index according to starting

    summary = dict(tp=tp, fp=fp, fn=fn,
                   precision=float(tp) / (tp + fp) if len(detection) > 0 else None,
                   recall=float(tp) / (tp + fn) if len(fact) > 0 else None,
                   dis=sum([abs(fact[i]-detection[j]) for i, j in match]) / float(tp) if tp > 0 else None)

    if return_match:
        summary['match'] = match

    return summary


def cut_matrix(mat, no_edge=0):
    """ given a cost matrix, cut it into non-connecting parts

    For example:
    cost_matrix = [[62, 0,  0,  0, 0,  0, 0],
                   [11, 11, 82, 0, 0,  0, 0],
                   [0,  0, 81, 12, 0,  0, 0],
                   [0,  0,  0,  0, 12, 0, 0],
                   [0,  0,  0,  0, 0,  0, 0],
                   [0,  0,  0,  0, 0,  0, 12],
                   [0,  0,  0,  0, 0,  0, 12]]
    expect return: [((0, 4), (0, 5)), ((3, 4), (4, 5)), ((5,7),(6,7))]
    Input like this is as well acceptable, though such case is not possible in the usage of this project.
    cost_matrix = [[62, 0,  0,  0, 0,  0, 0],
                   [11, 11, 82, 0, 0,  0, 0],
                   [0,  0, 81, 12, 0,  0, 0],
                   [0,  0, 12,  0, 0,  0, 0],
                   [0,  0,  0,  0, 0,  0, 12],
                   [0,  0,  0,  0, 0, 11, 12],
                   [0,  0,  0,  0, 0,  0, 12]]
    the lower-righter sub-matrix doesn't have edge as the top left corner.

    Args:
        mat (list of list of equal length): the cost matrix
        no_edge (int): the value in matrix meaning the the two nodes are not connected, thus no_edge

    Return:
        list of tuple: [((row from, to), (column from, to)), (another sub-matrix)...]
    """
    def cutter(mat, righter, downer):
        """ given the matrix and the two outer surrounding coordinates of the top left corner of a submatrix

        righter and downer traces the outer contour of a submatrix and verifies where it ends.
        righter goes right (increment in column index) when the value to its right is not an edge, else goes downwards.
        downer goes downside (increment in row index) when the value beneath it is not an edge, else goes right.
        righter and downer cuts a sub-matrix if they are in a diagonal position, corner touch corner.

        Args:
            mat (list of list of equal length): the cost matrix
            righter (tuple of two int): coordinate of righter
            downer (tuple of two int): coordinate of downer

        Returns:
            cut (tuple of two int): the row and column index the cuts (outer border) the sub-matrix beginning from the point
            surrounded by the input righter and downer
        """
        righter_copy = righter  # save the initial righter
        righter_set = set()  # the righter position ever visited
        cut = (len(mat), len(mat[0]))  # the default return value, if not cut, righter downer matches there, outside matrix
        # trace the righter first, to the very end
        # the stop condition is when the column index reaches the column number of the matrix + 1
        while righter[1] <= len(mat[0]):
            righter_set.add(righter)
            # righter can move right if it is already out side the matrix or next value is not an edge
            if righter[0] == len(mat) or (righter[1]+1 < len(mat[0]) and mat[righter[0]][righter[1]+1] == no_edge):
                righter = (righter[0], righter[1]+1)
            else:
                # otherwise move downwards
                righter = (righter[0]+1, righter[1])
        righter_set.remove(righter_copy)  # remove the initial righter so that it won't match up with first downer
        # then move the downer, the stop condition its row index is matrix row number + 1
        while downer[0] <= len(mat):
            # in general initial downer always matches with the initial righter, why removing the initial righter
            if (downer[0]+1, downer[1]-1) in righter_set:  # test diagonal position
                cut = (downer[0]+1, downer[1])
                break
            # can move down if already outside matrix or next value is not an edge
            if downer[1] == len(mat[0]) or (downer[0] + 1 < len(mat) and mat[downer[0]+1][downer[1]] == no_edge):
                downer = (downer[0]+1, downer[1])
            else:  # other wise move right
                downer = (downer[0], downer[1]+1)
        # if not cut righter surely contain (len(mat), len(mat[0]-1))
        # then downer matches righter at (len(mat)-1, len(mat[0]))
        # which makes the default cut that is (len(mat), len(mat[0]))
        return cut

    # the crossing point (inclusive) of line_start and column start is the top left corner of sub-matrix
    line_start = 0
    column_start = 0
    res = []  # row and column index range for each submatrix
    while line_start < len(mat) and column_start < len(mat[0]):

        righter = None
        downer = None
        for i in range(line_start, len(mat)):
            # the righter is the position left to the top element in the first non-empty column
            row = mat[i]
            if any([v != no_edge for v in row]):
                downer = (i-1, [j for j, v in enumerate(row) if v != no_edge][0])
                break

        for i in range(column_start, len(mat[0])):
            # the downer is the position upper to the first element in the first non-empty row
            column = [row[i] for row in mat]
            if any([v != no_edge for v in column]):

                righter = ([j for j, v in enumerate(column) if v != no_edge][0], i-1)
                break
        # if can not be found means from line_start, column_start, there is no edge left
        if righter is None or downer is None:
            break

        line_start, column_start = cutter(mat, righter, downer)  # update starting point with the last cut
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
        list of tuple [(delta median, delta std, seg_len, seg_med, seg_std),...]
    """
    fact = [0] + fact + [len(trace)]
    seg = [(fact[i], fact[i + 1]) for i in range(len(fact) - 1)]
    seg_len = np.array([i[1]-i[0] for i in seg])
    seg_median = [np.median(trace[i[0]:i[1]]) for i in seg]
    seg_median_diff = np.abs(np.array(seg_median[1:]) - np.array(seg_median[:-1]))
    seg_std = [np.std(trace[i[0]:i[1]]) for i in seg]
    seg_std_diff = np.abs(np.array(seg_std[1:]) - np.array(seg_std[:-1]))
    return zip(seg_median_diff, seg_std_diff, seg_len[1:], seg_median[1:], seg_std[1:])


def weighting(trace, fact):
    """ weight fact/events

    weight for each fact w = MAX(log2(seg_len/3), 0) * (median_diff + std_diff)

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




