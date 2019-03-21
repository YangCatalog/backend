class ParseException(Exception):

    def __init__(self, path):
        self.msg = "Failed to parse module on path {}".format(path)
