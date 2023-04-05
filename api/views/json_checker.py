from werkzeug.exceptions import abort


class Union:
    def __init__(self, *args):
        self.members = tuple(args)

    def __repr__(self):
        return ' | '.join(str(m) for m in self.members)

    __str__ = __repr__


class JsonCheckerException(Exception):
    ...


class MissingField(JsonCheckerException):
    def __init__(self, path):
        self.path = path


class IncorrectShape(JsonCheckerException):
    def __init__(self, correct, path):
        self.correct = correct
        self.path = path


def check(shape, data):
    match shape:
        case dict():
            if not isinstance(data, dict):
                raise IncorrectShape(dict, '')
            for key, component in shape.items():
                if key not in data:
                    raise MissingField(f'["{key}"]')
                try:
                    check(component, data[key])
                except MissingField as m:
                    raise MissingField(f'["{key}"]{m.path}')
                except IncorrectShape as e:
                    raise IncorrectShape(e.correct, f'["{key}"]{e.path}')
        case [shape_element]:
            if not isinstance(data, list):
                raise IncorrectShape(list, '')
            for i, data_element in enumerate(data):
                try:
                    check(shape_element, data_element)
                except MissingField as m:
                    raise MissingField(f'[{i}]{m.path}')
                except IncorrectShape as e:
                    raise IncorrectShape(e.correct, f'[{i}]{e.path}')
        case Union(members=members):
            exceptions = []
            for member in members:
                try:
                    check(member, data)
                    break
                except JsonCheckerException as e:
                    exceptions.append(e)
            else:
                error_strings = []
                for e in exceptions:
                    match e:
                        case MissingField(path=path):
                            error_strings.append(f'missing {path}')
                        case IncorrectShape(correct=correct, path=path):
                            error_strings.append(f'{correct} at {path}')
                raise IncorrectShape(f'one of ({" | ".join(error_strings)})', '')

        case type():
            if not isinstance(data, shape):
                raise IncorrectShape(shape, '')
    return True


def check_error(shape, data) -> None | str:
    try:
        check(shape, data)
    except MissingField as e:
        return f'Missing field at data{e.path}'
    except IncorrectShape as e:
        return f'Incorrect shape at data{e.path}. Expected {e.correct}.'


def abort_with_error(error: None | str):
    if error is None:
        return
    abort(400, description=error)
