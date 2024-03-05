from werkzeug.exceptions import abort

TYPE_MAP: dict[type, str] = {dict: 'object', list: 'array', str: 'string', int: 'number (int)', type(None): 'null'}


class Union:
    def __init__(self, *members):
        self.members = members

    def __repr__(self):
        return ' | '.join(str(m) for m in self.members)


class JsonCheckerException(Exception): ...  # noqa: E701


class MissingField(JsonCheckerException):
    def __init__(self, path: str):
        self.path = path


class IncorrectShape(JsonCheckerException):
    def __init__(self, correct: str, path: str):
        self.correct = correct
        self.path = path


def check_error(shape, data) -> None | str:
    """Check the data and abort the current request with code 400 and a formatted error string in the description."""
    try:
        check(shape, data)
    except MissingField as e:
        abort(400, description=f'Missing field at data{e.path}')
    except IncorrectShape as e:
        abort(400, description=f'Incorrect shape at data{e.path}. Expected {e.correct}.')


def check(shape, data):
    """Check the data and raise an exception in case of a mismatch."""
    match shape:
        case dict():
            if not isinstance(data, dict):
                raise IncorrectShape(TYPE_MAP[dict], '')
            for key, component in shape.items():
                if key not in data:
                    raise MissingField(f'["{key}"]')
                try:
                    check(component, data[key])
                except MissingField as m:
                    raise MissingField(f'["{key}"]{m.path}')
                except IncorrectShape as e:
                    raise IncorrectShape(e.correct, f'["{key}"]{e.path}')
        case [element_shape]:
            if not isinstance(data, list):
                raise IncorrectShape(TYPE_MAP[list], '')
            for i, data_element in enumerate(data):
                try:
                    check(element_shape, data_element)
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
                raise IncorrectShape(TYPE_MAP[shape], '')
    return True
