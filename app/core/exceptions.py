class InvalidPasswordException(Exception):
    """
    Exception raised when the old password is incorrect
    """
    def __init__(self, message: str = "Old password is incorrect"):
        self.message = message
        super().__init__(self.message)