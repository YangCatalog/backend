class NullJsonEncoder(json.JSONEncoder):

    def encode(self, o):
        ret_obj = self.__remove_null_dict(o)
        return super().encode(ret_obj)

    def __remove_null_dict(self, obj):
        ret_obj = {}
        for key, val in obj.items():
            if isinstance(val, dict):
                temp_obj =  self.__remove_null_dict(val)
                if len(temp_obj) > 0:
                    ret_obj[key] = temp_obj
            elif isinstance(val, list):
                temp_obj = self.__remove_null_list(val)
                if len(temp_obj) > 0:
                    ret_obj[key] = temp_obj
            else:
                if val is not None:
                    ret_obj[key] = val
        return ret_obj

    def __remove_null_list(self, obj):
        ret_obj = []
        for val in obj:
            if isinstance(val, dict):
                temp_obj = self.__remove_null_dict(val)
                if len(temp_obj) > 0:
                    ret_obj.append(temp_obj)
            else:
                if val is not None:
                    ret_obj.append(val)
        return ret_obj