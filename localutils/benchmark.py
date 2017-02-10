"""
benchmark.py provides functions for various evaluation tasks in this work
"""


def evaluation(fact, prediction):
    """classify the prediction into true positive, true negative, false positive and false negative

    Args:
        fact (list of int): ground fact, should only contain only 0, 1; 1 for events meant to be detected;
        prediction (list of int): results to be tested against ground fact; 1 for detected events;

    Returns:
        dict: {'tp':int, 'fp':int, 'fn':int, 'tn':int, 'precision':float, 'recall':float}
    """
    if len(fact) != len(prediction):
        raise ValueError('fact and prediction are not of same length.')
    if not (set(fact) == set(prediction) == set([0, 1])):
        raise ValueError('fact or/and prediction contain other value than 0/1.')
    tp, fp, fn, tn = [0] * 4
    for f, p in zip(fact, prediction):
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


def evaluation_window(fact, prediction, window=0):
    """classify the predictions into relevant and irrelevant; facts into detected and undetected

    a window surrounds each ground truth (centered at 0), [-window, window].
    if any prediction within the window, the ground truth is detected; else undetected;
    all prediction within the ground truth window is relevant; the remaining is irrelevant.

    detected/all fact -> success rate: the percentage of events are discovered;
    relevant/all prediction-> relevance rate: the percentage of detection are useful/relevant;
    detected/relevant -> compatibility: in average how many predictions needed to detected one fact;

    Args:
        fact (list of int): ground fact, should only contain only 0, 1; 1 for events meant to be detected;
        prediction (list of int): results to be tested against ground fact; 1 for detected events;
        window (int): one-sided size for search window around a given ground truth

    Returns:
        dict: {'d':int, 'ud':int, 'r':int, 'ir':int, 'success':float, 'relevance':float, 'compatibility':float, 'dis':dict}
        the dis dict store the distance from all relevant prediction to closest ground fact, {idx:dis,..}
    """
    if len(fact) != len(prediction):
        raise ValueError('fact and prediction are not of same length.')
    if not (set(fact) == set(prediction) == set([0, 1])):
        raise ValueError('fact or/and prediction contain other value than 0/1 or being empty.')
    end = len(fact)  # the farthest a window can go
    d = 0  # detected ground fact count
    rel_dis = {}  # idx of prefix: distance to nearest ground fact within window
    for i, f in enumerate(fact):
        if f:
            w = (max(i-window, 0), min(i+window+1, end))  # the search range for prediction around the ground truth i
            hit = [idx for idx, p in zip(range(w[0], w[1]), prediction[w[0]:w[1]]) if p]  # idx of predictions that fire
            if hit:
                d += 1
                for j in hit:
                    rel_dis[j] = min(abs(i-j), rel_dis.get(j, end))  # update the distance

    ud = sum(fact) - d
    r = len(rel_dis)
    ir = sum(prediction) - r
    success = float(d)/sum(fact)
    relevance = float(r)/sum(prediction)
    compatibility = float(d)/r

    return dict(d=d, ud=ud, r=r, ir=ir, success=success, relevance=relevance, compatibility=compatibility, dis=rel_dis)
