from PySide6.QtCore import QObject, Signal, QThread


class StreamToSignal(QObject):
    text_written = Signal(str)

    def __init__(self, original_stream):
        super().__init__()
        self.original_stream = original_stream

    def write(self, text):
        self.original_stream.write(text)
        cleaned = text.strip()
        if cleaned:
            self.text_written.emit(cleaned.split('\n')[-1].strip())

    def flush(self):
        self.original_stream.flush()


class GenericTaskWorker(QThread):
    task_finished = Signal(bool)

    def __init__(self, target_func, *args, **kwargs):
        super().__init__()
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.target_func(*self.args, **self.kwargs)
            self.task_finished.emit(True)
        except Exception as e:
            print(f"\n[ERROR] {e}")
            self.task_finished.emit(False)


