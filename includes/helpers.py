# Functions that multiple plugins should use


def time_string(tdel):
    if tdel.days > 14:
        return "{}w ago".format(tdel.days//7)
    elif tdel.days > 1:
        return "{}d ago".format(tdel.days)
    elif tdel.seconds > 7200:
        return "{}h ago".format((tdel.days*24)+(tdel.seconds//3600))
    elif tdel.seconds > 120:
        return "{}m ago".format(tdel.seconds//60)
    else:
        return "{}s ago".format(tdel.seconds)
