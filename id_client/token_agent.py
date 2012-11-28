

class TokenAgent:
    def __init__(self, event_callback_routine):
        """event_callback_routine should be a callable object
        and expect (event, data) arguments"""
        self.event_callback_routine = event_callback_routine

    def stop(self):
        pass
