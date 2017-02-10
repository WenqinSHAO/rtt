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


def evaluation_window(fact, detection, window=0):
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

    Returns:
        dict: {'tp':int, 'fp':int, 'fn':int, 'precision':float, 'recall':float, 'dis':float}

    """
    cost_matrix = to_matrix(fact, detection, window)  # construct the cost matrix of bipartite graph
    match = munkres.Munkres().compute(cost_matrix)  # calculate the matching

    tp = len(match)
    fp = len(detection) - tp
    fn = len(fact) - tp

    return dict(tp=tp, fp=fp, fn=fn,
                precision=float(tp) / (tp + fp), recall=float(tp) / (tp + fn),
                dis=sum([cost_matrix[i][j]for i, j in match])/float(tp))


def evaluation_window_weighted(trace, fact, detection, window = 0):
    """ score the event according to its importance

    Each event to detect in fact is associated with a weight/score.
    the score characterise the importance of each event.

    score = score sum of detected events/total sum; a more nuanced version of recall

    Args:
        trace (list of numeric): the initial time series to be detected
        fact (list of int): the index or timestamp of facts/events to be detected
        detection (list of int): index or timestamp of detected events
        window (int): maximum distance for the correlation between fact and detection

    Returns:
        dict: {'tp':int, 'fp':int, 'fn':int, 'precision':float, 'recall':float, 'dis':float, 'score':float}

    """
    cost_matrix = make_cost_matrix(fact, detection, window)  # construct the cost matrix of bipartite graph
    match = munkres.Munkres().compute(cost_matrix)  # calculate the matching

    weight = weighting(trace, fact)

    tp = len(match)
    fp = len(detection) - tp
    fn = len(fact) - tp

    return dict(tp=tp, fp=fp, fn=fn,
                precision=float(tp) / (tp + fp), recall=float(tp) / (tp + fn),
                dis=sum([cost_matrix[i][j] for i, j in match]) / float(tp),
                score=sum([weight[i] for i, _ in match]) / float(sum(weight)))


def weighting(trace, fact):
    """ weight fact/events

    weight for each fact w = MAX(log10(seg_len/3), 0) * median_diff * sqrt(std_diff)

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
    return np.maximum(np.log2(np.array(seg_len[1:])/3), 0) * seg_median_diff * np.sqrt(seg_std_diff)


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
        nodes is a set of vertices in added edges"""
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




