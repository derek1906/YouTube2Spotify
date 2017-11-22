class UnauthorizedError(Exception):
	"""HTTP 401, 403"""

class BadRequest(Exception):
	"""HTTP 400"""

class UnexpectedError(Exception):
	pass