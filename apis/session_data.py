"""Session data container"""
import apis.session_data_exceptions as session_data_exceptions

class SessionDataContainer(object):
    """Container class"""

    Exceptions = session_data_exceptions

    def __init__(self):
        self.session_data = {}

    def get(self, key, *namespaces):
        """Get session data"""
        path = (key,) + namespaces
        try:
            data = self.session_data
            for name in path:
                data = data[name]

            return data
        except KeyError:
            raise SessionDataContainer.Exceptions.NamespaceNotFoundException()

    def set(self, key, *namespaces, **props):
        """Set session data"""
        if "data" not in props:
            raise TypeError("Missing \"data\"")

        path = (key,) + namespaces
        obj = self.session_data

        for name in path[:-1]:
            if name not in obj:
                obj[name] = {}
            obj = obj[name]

        obj[path[-1]] = props["data"]

    def remove(self, key, *namespaces):
        """Remove session data"""
        path = (key,) + namespaces
        try:
            obj = self.session_data
            for name in path[:-1]:
                obj = obj[name]

            del obj[path[-1]]

        except KeyError:
            raise SessionDataContainer.Exceptions.NamespaceNotFoundException()
