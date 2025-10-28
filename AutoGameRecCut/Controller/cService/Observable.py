class Observable:
    def __init__(self):
        self._observers = []

    def subscribe(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event_name, data=None):
        # Iterate over a copy so observers can unsubscribe during 
        for obs in list(self._observers):
            try:
                if hasattr(obs, "update") and callable(obs.update):
                    obs.update(event_name, data)
                elif callable(obs):
                    obs(event_name, data)
            except Exception as e:
                print(f"Observable.notify: Observer Error: {e}")